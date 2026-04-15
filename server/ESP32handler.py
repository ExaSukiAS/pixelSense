import asyncio
import websockets
import threading
import socket
import struct
import numpy as np
import queue
import time

class ESP32:
    def __init__(self, onConnect=None, onMessage=None, onImage=None, onStats=None):
        self.espIP = "192.168.68.106"
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

        self.audioSampleQueue = queue.Queue()
        self.espSpeakerSamplingRate = 12000

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
    
    def _imgListener(self):
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
    
    # listen for stats data(CPU usage, memory usage) from ESP32 and forward to callback
    def _statsUDPlistener(self):
        self.statsUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.statsUDP.bind(("0.0.0.0", self.statsReceivingPort))

        while True:
            data, addr = self.statsUDP.recvfrom(1500)

            if len(data) == 24:
                stats = struct.unpack("<6i", data)
                if self.onStats:
                    self.onStats(stats)
    
    def queueSamplesForStream(self, samples):
        self.audioSampleQueue.put(samples)
    
    def _handleAudioSampleQueue(self):
        while True:
            samples = self.audioSampleQueue.get()
            if samples is None: break

            self._streamAudio(samples)

            self.audioSampleQueue.task_done()

    def _streamAudio(self, samples):
        udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        
        # 1000 bytes = 500 samples
        packetSize = 1000 
        
        # calculate exactly how much audio time is in one packet
        # 500 samples / 12000 samples per second = ~0.04166 seconds
        packet_duration = (packetSize / 2) / self.espSpeakerSamplingRate 
        packet_id = 0
        startTime = time.time()

        for i in range(0, len(samples), packetSize):
            packet = samples[i:i+packetSize]
            
            # create the 4-byte header
            data = struct.pack("I", packet_id) + packet
            udp.sendto(data, (self.espIP, self.espUDPport))
            packet_id += 1
            
            expectedTime = startTime + (packet_id * packet_duration)
            sleepTime = expectedTime - time.time()
            
            # only sleep if we are actually ahead of schedule
            if sleepTime > 0:
                time.sleep(sleepTime)
        return

    def start(self):
        threads = [
            threading.Thread(target=lambda: asyncio.run(self.connect()), name="WS-Thread"),
            threading.Thread(target=self._imgListener, name="UDP-Img-Thread"),
            threading.Thread(target=self._statsUDPlistener, name="UDP-Stats-Thread"),
            threading.Thread(target=self._handleAudioSampleQueue, name="Audio-Send-Thread")
        ]
        for t in threads:
            t.daemon = True
            t.start()