import asyncio
import websockets
import threading
import socket
import struct
import numpy as np

class ESP32WebSocket:
    def __init__(self, onConnect=None, onMessage=None, onImage=None):
        self.espIP = "192.168.68.103"
        self.espWsPort = 9000
        self.espUDPport = 9001

        self.wsAddress = f"ws://{self.espIP}:{self.espWsPort}"

        self.websocketConnected = False
        self.udpConnected = False

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
        self.udp.bind(("0.0.0.0", 5005))

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

    def start(self):
        # start websocket(TCP) thread
        wsThread = threading.Thread(target=lambda: asyncio.run(self.connect()))
        wsThread.daemon = True
        wsThread.start()

        # start UDP thread
        udpThread = threading.Thread(target=self.udpListener)
        udpThread.daemon = True
        udpThread.start()