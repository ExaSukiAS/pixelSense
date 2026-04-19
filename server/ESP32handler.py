import asyncio
import websockets
import threading
import socket
import struct
import numpy as np
import queue
import time

class ESP32:
    def __init__(self, espIP, boardType, imgPort, micPort, statsPort, onConnect=None, onMessage=None, onImage=None, onMicSamples=None, onStats=None):
        self.espIP = espIP
        self.boardType = boardType
        self.espWsPort = 9000
        self.espUDPport = 9001

        self.imageReceivingPort = imgPort
        self.micSampleReceivingPort = micPort
        self.statsReceivingPort = statsPort

        self.wsAddress = f"ws://{self.espIP}:{self.espWsPort}"

        self.websocketConnected = False
        self.udpConnected = False

        self.onMessage = onMessage
        self.onImage = onImage
        self.onMicSamples = onMicSamples
        self.onConnect = onConnect
        self.onStats = onStats

        self.ws = None
        self.imgUDP = None
        self.micSampleUDP = None
        self.statsUDP = None

        self.audioSampleQueue = queue.Queue()
        self.espSpeakerSamplingRate = 12000

        self.loop = None  

    # connects to ESP32
    async def connect(self):
        self.loop = asyncio.get_running_loop() 

        try:
            async with websockets.connect(self.wsAddress, open_timeout=300, close_timeout=300) as ws:
                self.ws = ws
                
                self.websocketConnected = True

                if self.onConnect:
                    self.onConnect(self.boardType)

                async for message in ws:
                    if isinstance(message, bytes):
                        if self.onImage:
                            self.onImage(self.boardType, message)
                    else:
                        if self.onMessage:
                            self.onMessage(self.boardType)
        except Exception as e:
            print("Error from ESP32handler.py:", e)

    # requests an image capture from esp32
    def requestCapture(self, capture_mode):
        if self.websocketConnected and self.ws is not None and self.loop:
            asyncio.run_coroutine_threadsafe(self.ws.send(capture_mode), self.loop)
            return True
        print("Connection not ready for capture request.")
        return False
    
    # listens for incoming image frames from ESP32
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
                        self.onImage(self.boardType, image)

                    del buffers[frameID]
    
    # listens for incoming microphone samples from ESP32
    def _micSampleListener(self):
        self.micSampleUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.micSampleUDP.bind(("0.0.0.0", self.micSampleReceivingPort))

        while True:
            data, addr = self.micSampleUDP.recvfrom(1024)

            if data:
                # resample 8khz incoming audio samples into 16khz audio
                audioArray = np.frombuffer(data, dtype=np.int16)
                resampledArray = np.repeat(audioArray, 2)
                resampledData = resampledArray.tobytes()
                
                if self.onMicSamples:
                    self.onMicSamples(self.boardType, resampledData)
    
    def requestMicSampleStream(self):
        if self.websocketConnected and self.ws and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws.send("startAudioStream"), self.loop)
            return True
        print("Connection not ready for mic samples request.")
        return False
    
    def stopMicSampleStream(self):
        if self.websocketConnected and self.ws is not None and self.loop:
            asyncio.run_coroutine_threadsafe(self.ws.send("stopAudioStream"), self.loop)
            return True
        print("Connection not ready for stopping mic samples stream.")
        return False
    
    # listen for stats data from ESP32 and forward to callback
    def _statsListener(self):
        self.statsUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.statsUDP.bind(("0.0.0.0", self.statsReceivingPort))

        while True:
            data, addr = self.statsUDP.recvfrom(64)

            if len(data) == 32:
                stats = struct.unpack("<8i", data)
                if self.onStats:
                    self.onStats(self.boardType, stats)
    
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
            threading.Thread(target=self._statsListener, name="UDP-Stats-Thread"),
            threading.Thread(target=self._micSampleListener, name="UDP-MicSample-Thread"),
            threading.Thread(target=self._handleAudioSampleQueue, name="Audio-Send-Thread")
        ]
        for t in threads:
            t.daemon = True
            t.start()