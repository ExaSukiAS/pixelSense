import asyncio
import websockets
import threading

class Voice:
    def __init__(self, onConnect=None):
        self.onConnect = onConnect
        self.ws = None
        self.loop = None
        self.connectdClients = set()
        self.voiceContentFuture = None

    # handles incoming messages from voice client
    async def handleVoiceClient(self, websocket):
        self.connectdClients.add(websocket)
        self.ws = websocket
        if self.onConnect:
            self.onConnect()
        try:
            async for message in websocket:
                self.voiceContentFuture.set_result(message)
                self.voiceContentFuture = None
        except websockets.exceptions.ConnectionClosed:
            print("Voice client disconnected")

    # starts the voice server and opens the port
    async def main(self):
        self.loop = asyncio.get_running_loop() 
        async with websockets.serve(self.handleVoiceClient, "localhost", 8080):
            await asyncio.Future()  # Run forever

    # Updated utterChunk in voice.py
    def utterChunk(self, chunk):
        asyncio.run_coroutine_threadsafe(self.ws.send(chunk), self.loop)
        print("Chunk sent to loop", chunk)
        return True
        
    # returns an asyncio future which, when resolved gives the voice content
    def getVoiceContentFuture(self):
        if len(self.connectdClients) > 0 and self.ws and self.loop:
            self.voiceContentFuture = self.loop.create_future()
            asyncio.run_coroutine_threadsafe(self.ws.send('stt'), self.loop)
            return self.voiceContentFuture
        return False

    # terminates uttering of voice client
    def stopUttering(self):
        if len(self.connectdClients) > 0 and self.ws and self.loop:
            asyncio.run_coroutine_threadsafe(self.ws.send('tts_stop'), self.loop)
            return True
        return False
    
    def start(self):
        thread = threading.Thread(target=lambda: asyncio.run(self.main()))
        thread.daemon = True
        thread.start()
