import asyncio
import websockets
import threading

class GUI:
    def __init__(self, onConnect=None, onMessage=None):
        self.onConnect = onConnect
        self.onMessage = onMessage
        self.ws = None
        self.loop = None
        self.connectdClients = set()
        self.voiceContentFuture = None
        self.imageSending = False

    # handles incoming messages from GUI client
    async def handleGUIclient(self, websocket):
        self.connectdClients.add(websocket)
        self.ws = websocket
        if self.onConnect:
            self.onConnect()
        try:
            async for message in websocket:
                if self.onMessage:
                    self.onMessage(message)
        except websockets.exceptions.ConnectionClosed:
            print("GUI client disconnected")

    # starts the GUI server and opens the port
    async def main(self):
        self.loop = asyncio.get_running_loop() 
        async with websockets.serve(self.handleGUIclient, "localhost", 8070):
            await asyncio.Future()  # Run forever

    # sends a message to the GUI client
    def sendMessage(self, messageType, message):
        if self.loop and self.connectdClients:
            if messageType == "IMG":
                header = b'\x01'
                fullMessage = header + message
            else:
                fullMessage = f"{messageType}$@#${message}"
            asyncio.run_coroutine_threadsafe(self.ws.send(fullMessage), self.loop)
            return True
        else:
            return False
    
    def start(self):
        thread = threading.Thread(target=lambda: asyncio.run(self.main()))
        thread.daemon = True
        thread.start()