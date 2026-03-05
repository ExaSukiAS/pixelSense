import asyncio
import websockets
import threading

class ESP32WebSocket:
    def __init__(self, onConnect=None, onMessage=None, onImage=None):
        self.address = "ws://192.168.68.103:9000"
        self.websocketConnected = False
        self.onMessage = onMessage
        self.onImage = onImage
        self.onConnect = onConnect
        self.ws = None
        self.loop = None  

    async def connect(self):
        self.loop = asyncio.get_running_loop() 
        try:
            async with websockets.connect(self.address, open_timeout=300, close_timeout=300) as ws:
                self.ws = ws
                
                self.websocketConnected = True
                if self.onConnect:
                    try:
                        self.onConnect()
                    except Exception as callback_error:
                        print(f"External callback failed, but ESP32 is fine: {callback_error}")

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

    def start(self):
        thread = threading.Thread(target=lambda: asyncio.run(self.connect()))
        thread.daemon = True
        thread.start()