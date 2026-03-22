import asyncio
import websockets
import threading
import socket
import struct
import numpy as np
import pyaudio
import audioop
import time

class ESP32WebSocket:
    def __init__(self, onConnect=None, onMessage=None, onImage=None, onStats=None):
        self.espIP = "192.168.68.107"
        self.espWsPort = 9000
        self.espUDPport = 9001

        self.imageReceivingPort = 5005
        self.micSampleReceivingPort = 5006
        self.statsReceivingPort = 5007

        self.wsAddress = f"ws://{self.espIP}:{self.espWsPort}"

        self.websocketConnected = False
        self.udpConnected = False

        self.audioStream = None
        self.audioRunning = False

        self.onMessage = onMessage
        self.onImage = onImage
        self.onConnect = onConnect
        self.onStats = onStats

        self.ws = None
        self.imgUDP = None
        self.statsUDP = None

        self.loop = None  

    async def connect(self):
        self.loop = asyncio.get_running_loop() 

        try:
            async with websockets.connect(self.wsAddress, open_timeout=300, close_timeout=300) as ws:
                self.ws = ws
                
                self.websocketConnected = True

                if self.onConnect:
                    self.onConnect()

                async for message in ws:
                    if isinstance(message, bytes):
                        if self.onImage:
                            self.onImage(message)
                    else:
                        if self.onMessage:
                            self.onMessage(message)
        except Exception as e:
            print("Error:", e)

    def requestCapture(self, capture_mode):
        if self.websocketConnected and self.ws is not None and self.loop:
            asyncio.run_coroutine_threadsafe(
                self.ws.send(capture_mode),
                self.loop
            )
            return True
        print("Connection not ready for capture request.")
        return False
    
    def imgListener(self):
        self.imgUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.imgUDP.bind(("0.0.0.0", self.imageReceivingPort))

        buffers = {} # structure: {frameID: bytearray(), frameID: bytearray(), ...}

        while True:
            data, addr = self.imgUDP.recvfrom(1500)

            # get valid data packets only [(6B header) & jpg chunk]
            if len(data) >= 6:
                frameID, offset = struct.unpack("<HI", data[:6]) # fetch header (2B for frameID and 4B for offset)
                payload = data[6:] # jpg chunk

                if frameID not in buffers:
                    buffers[frameID] = bytearray(200000)

                buffers[frameID][offset:offset+len(payload)] = payload # insert jpg chunk into correct location

                # end of a full jpg image
                if payload[-2:] == b'\xff\xd9':
                    image = buffers[frameID][:offset+len(payload)]

                    if self.onImage:
                        self.onImage(image)

                    del buffers[frameID]
    
    def statsUDPlistener(self):
        self.statsUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.statsUDP.bind(("0.0.0.0", self.statsReceivingPort))

        while True:
            data, addr = self.statsUDP.recvfrom(1500)

            if len(data) == 24:
                stats = struct.unpack("<6i", data)
                if self.onStats:
                    self.onStats(stats)
    
    def streamSystemAudio(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # initialize PyAudio
        p = pyaudio.PyAudio()

        inputRate = 48000
        targetRate = 12000
        packetSize = 1000
        gain = 1.0
        audioDeviceIndex = 22

        print(f"Using audio output device {p.get_device_info_by_index(audioDeviceIndex)['name']} at index{audioDeviceIndex}")

        while True: 
            if not self.audioRunning:
                time.sleep(0.1)
                continue  
            
            # state for the rate converter
            state = None

            self.audioStream = p.open(format=pyaudio.paInt16,
                            channels=2,
                            rate=inputRate,
                            input=True,
                            input_device_index=audioDeviceIndex,
                            frames_per_buffer=packetSize)
            
            packet_id = 0
            while self.audioRunning:
                pcm_data = self.audioStream.read(packetSize, exception_on_overflow=False) # raw PCM from Windows (Stereo, 48kHz)
                mono_data = audioop.tomono(pcm_data, 2, 1, 0) # convert stereo to mono
                
                # downsample from 48000 to 12000
                downsampled_data, state = audioop.ratecv(
                    mono_data, 2, 1, inputRate, targetRate, state
                )
            
                amplified_data = audioop.mul(downsampled_data, 2, gain) # apply gain
                
                # package and send
                header = struct.pack("<I", packet_id)
                data = header + amplified_data
                
                udp.sendto(data, (self.espIP, self.espUDPport))
                
                packet_id += 1

    def startAudioStream(self):
        self.audioRunning = True

    def stopAudioStream(self):
        self.audioRunning = False

    def start(self):
        threads = [
            threading.Thread(target=lambda: asyncio.run(self.connect()), name="WS-Thread"),
            threading.Thread(target=self.imgListener, name="UDP-Img-Thread"),
            threading.Thread(target=self.statsUDPlistener, name="UDP-Stats-Thread"),
            threading.Thread(target=self.streamSystemAudio, name="Audio-Send-Thread")
        ]
        for t in threads:
            t.daemon = True
            t.start()