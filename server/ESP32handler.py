import asyncio
import websockets
import threading
import socket
import struct
import numpy as np
import queue
import time
import cv2

class ESP32:
    def __init__(self, espIP, boardType, imgPort, micPort, statsPort, onConnect=None, onMessage=None, onImage=None, onSyncedImage=None, onMicSamples=None, onStats=None):
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
        self.onSyncedImage = onSyncedImage
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
                            rotatedImage = self._rotateAndEvaluateImgBytes(message)
                            self.onImage(self.boardType, rotatedImage)
                    else:
                        if self.onMessage:
                            self.onMessage(self.boardType, message)
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
        self.imgUDP.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 2 * 1024 * 1024) # increase OS UDP buffer size to 2MB to prevent drops under heavy CPU load
        self.imgUDP.bind(("0.0.0.0", self.imageReceivingPort))

        # structure: {frameID: {'data': bytearray, 'recvdBytes': int}}
        buffers = {} 
        
        while True:
            data, addr = self.imgUDP.recvfrom(4096)

            if len(data) >= 9:
                headerData = struct.unpack("<HIBH", data[:9])
                frameID = headerData[0]
                offset = headerData[1]
                frameType = headerData[2]
                dist_cm = headerData[3]
                payload = data[9:] # jpg data chunk

                # Initialize buffer for new frame
                if frameID not in buffers:
                    buffers[frameID] = {
                        'data': bytearray(200000), 
                        'recvdBytes': 0
                    }

                buffers[frameID]['data'][offset : offset + len(payload)] = payload
                buffers[frameID]['recvdBytes'] += len(payload)

                # Check for JPEG EOI marker
                if payload[-2:] == b'\xff\xd9':
                    total_expected_size = offset + len(payload)
                    
                    # only return if received bytes match the last offset (a fully valid image)
                    if buffers[frameID]['recvdBytes'] == total_expected_size:
                        image = buffers[frameID]['data'][:total_expected_size]
                        rotatedImage = self._rotateAndEvaluateImgBytes(image)

                        if rotatedImage is not None:
                            if frameType == 0: # single capture
                                if self.onImage:
                                    self.onImage(self.boardType, rotatedImage)
                            elif frameType == 1: # dual capture with TOF distance
                                if self.onSyncedImage:
                                    self.onSyncedImage(self.boardType, rotatedImage, frameID, dist_cm)
                    else:
                        # drop corrupted/incomplete image
                        pass

                    del buffers[frameID]

            # memory leaks preventation
            if len(buffers) > 10:
                first_key = next(iter(buffers))
                del buffers[first_key]
    
    # listens for incoming microphone samples from ESP32
    def _micSampleListener(self):
        self.micSampleUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.micSampleUDP.bind(("0.0.0.0", self.micSampleReceivingPort))

        while True:
            data, addr = self.micSampleUDP.recvfrom(2048)

            if data:
                # resample 8khz incoming audio samples into 16khz audio
                audioArray = np.frombuffer(data, dtype=np.int16)
                resampledArray = np.repeat(audioArray, 2)
                resampledData = resampledArray.tobytes()
                
                if self.onMicSamples:
                    self.onMicSamples(self.boardType, resampledData)
    
    def requestMicSampleStream(self):
        if self.websocketConnected and self.ws and self.loop and self.loop.is_running():
            asyncio.run_coroutine_threadsafe(self.ws.send("strtMicStream"), self.loop)
            return True
        print("Connection not ready for mic samples request.")
        return False
    
    def stopMicSampleStream(self):
        if self.websocketConnected and self.ws is not None and self.loop:
            asyncio.run_coroutine_threadsafe(self.ws.send("stpMicStream"), self.loop)
            return True
        print("Connection not ready for stopping mic samples stream.")
        return False
    
    # listen for stats data from ESP32 and forward to callback
    def _statsListener(self):
        self.statsUDP = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.statsUDP.bind(("0.0.0.0", self.statsReceivingPort))

        while True:
            data, addr = self.statsUDP.recvfrom(2048)

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
        # 500 samples / 12000 samples/second = ~41.667 ms
        pktDuration = (packetSize / 2) / self.espSpeakerSamplingRate 
        pktID = 0
        startTime = time.time()

        for i in range(0, len(samples), packetSize):
            packet = samples[i:i+packetSize]
            
            # create the 4-byte header
            data = struct.pack("I", pktID) + packet
            udp.sendto(data, (self.espIP, self.espUDPport))
            pktID += 1
            
            # calculate how long to sleep to maintain correct timing for audio stream
            expectedTime = startTime + (pktID * pktDuration)
            sleepTime = expectedTime - time.time()
            
            # only sleep if we are actually ahead of schedule
            if sleepTime > 0:
                time.sleep(sleepTime)
        return
    
    def _rotateAndEvaluateImgBytes(self, imgBytes):
        # Check if jpg has SOI and EOI markers
        if not imgBytes.startswith(b'\xff\xd8') or not imgBytes.endswith(b'\xff\xd9'):
            return None

        np_arr = np.frombuffer(imgBytes, np.uint8)
        img_cv = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        
        if img_cv is None:
            return None 
            
        final_cv = cv2.flip(img_cv, 0) # This rotates 180 and de-mirrors
        
        success, encoded_img = cv2.imencode('.jpg', final_cv)
        return encoded_img.tobytes() if success else None
        

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