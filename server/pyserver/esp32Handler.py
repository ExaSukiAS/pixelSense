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
    def __init__(self, onConnect=None, onMessage=None, onImage=None):
        self.espIP = "192.168.68.105"
        self.espWsPort = 9000
        self.espUDPport = 9001

        self.imageReceivingPort = 5005
        self.micSampleReceivingPort = 5006

        self.wsAddress = f"ws://{self.espIP}:{self.espWsPort}"

        self.websocketConnected = False
        self.udpConnected = False

        self.audioStream = None
        self.audioRunning = False

        self.onMessage = onMessage
        self.onImage = onImage
        self.onConnect = onConnect

        self.ws = None
        self.udp = None

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
    
    def udpListener(self):
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.bind(("0.0.0.0", self.imageReceivingPort))

        self.udp.sendto(b'handshakeMessage', (self.espIP, self.espUDPport))

        buffers = {} # structure: {frameID: bytearray(), frameID: bytearray(), ...}
        espConnected = False

        while True:
            data, addr = self.udp.recvfrom(1500)

            # ensure connection is established
            if data == b'receivedPacket':
                espConnected = True
                continue

            # get valid data packets only [(6B header) & jpg chunk]
            if espConnected and len(data) >= 6:
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
    
    def streamSystemAudio(self):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # initialize PyAudio
        p = pyaudio.PyAudio()

        for i in range(p.get_device_count()):
            dev = p.get_device_info_by_index(i)
            print(f"Index {i}: {dev['name']}")

        inputRate = 48000
        targetRate = 12000
        packetSize = 1000
        gain = 1.0

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
                            input_device_index=11,
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
        # start websocket(TCP) thread
        wsThread = threading.Thread(target=lambda: asyncio.run(self.connect()))
        wsThread.daemon = True
        wsThread.start()

        # start UDP thread
        udpThread = threading.Thread(target=self.udpListener)
        udpThread.daemon = True
        udpThread.start()

        audioStreamThread = threading.Thread(target=self.streamSystemAudio)
        audioStreamThread.daemon = True 
        audioStreamThread.start()