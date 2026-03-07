import time
import json
import asyncio
import re
from termcolor import colored
from esp32Handler import ESP32WebSocket
from gemini import GeminiClient
from voice import Voice
from tracker import Tracker
from UIhandler import GUI

# gemini configuration
geminiKeyToUse = "2"

currentMode = None # current mode (.freeform, .coord, .txt_rec, .img_des, .obj_dtc, streaming, None)
currentImage = None
coordRunning = False # status of coordination feature

trackerConfidenceThreshold = 0.5 # minimum confidence threshold for tracking hand and target object in coordination mode
tracker = None
trackerInitialized = False
initialObjRIO_norm = None
objRIO_norm = None
handRIO_norm = None
trackedObjName = None

guiConnected = False
espConnected = False
voiceConnected = False

# fetch tehe correct gemini api key from geminiAPI.json
geminiAPIkey = ""
with open("geminiAPI.json", "r") as jsonStringObj:
    apiKeys = json.load(jsonStringObj)
    geminiAPIkey = apiKeys[geminiKeyToUse]
AIistructions = {}
# fetch AI instructions
with open("instructions.txt", "r") as file:
    instructions = file.read()
    instructions = instructions.split("$$")
    keyFound = False
    currentKey = ""
    for idx,data in enumerate(instructions):
        if data == "":
            continue
        if not keyFound:
            AIistructions[data] = ""
            currentKey = data
            keyFound = True
        else:
            AIistructions[currentKey] = data
            keyFound = False

# --------------- Gemini functions ---------------

# handles response from gemini flash lite model
fullResponse = ""
def fastGeminiResponseHandler(responseChunk):
    global fullResponse
    if responseChunk == "#$$#": # detect end of stream
        guiServer.sendMessage("loader", "100")
        guiServer.sendMessage("log", fullResponse)
        fullResponse = ""
        return 
    guiServer.sendMessage("loader", "80")
    guiServer.sendMessage("log", fullResponse)
    # sanitizes text for Text-to-Speech by removing markdown formatting, emojis, and unwanted symbols
    def sanitize_for_tts(text):
        text = re.sub(r'[`*_~^#>|]', '', text)
        text = re.sub(r"[^\w\s.,!?'\"():;-]", '', text)
        text = re.sub(r'_', '', text)
        return text
    if responseChunk is not None:
        fullResponse += responseChunk
        voiceServer.utterChunk(sanitize_for_tts(responseChunk))
    return

# handles response from gemini flash model
coordResponse = "" # gemini stream chunk accumulator
def coordGeminiResponseHandler(responseChunk):
    global coordResponse
    if responseChunk == "#$$#": # detect end of stream
        guiServer.sendMessage("loader", "85")
        guiServer.sendMessage("log", "Initializing object and hand tracker models...")

        cleanCoordinates = re.sub(r'^```json\n|```$', '', coordResponse) # sanitize coordinates
        coordResponse = ""
        objectCoordinate = json.loads(cleanCoordinates)

        global initialObjRIO_norm
        initialObjRIO_norm = (int(objectCoordinate.get("xmin")), int(objectCoordinate.get("ymin")), int(objectCoordinate.get("xmax")), int(objectCoordinate.get("ymax")))

        # initialize tracker model
        global tracker, trackerConfidenceThreshold
        tracker = Tracker(currentImage, initialObjRIO_norm, trackerConfidenceThreshold, False)
        global trackerInitialized
        trackerInitialized = True
        guiServer.sendMessage("loader", "100")
    else:
        coordResponse += responseChunk
        guiServer.sendMessage("loader", "70")
    return

# --------------- ESP32 functions ---------------

# this function is trigered when esp32 is connected
def onespConnect():
    global espConnected
    espConnected = True
    print(colored("ESP32 connected!", "light_green"))

# handles messages from esp32
def espMessageHandler(message):
    global currentMode
    if message == "$#TXT#$touch1_single":
        guiServer.sendMessage("activate", ".txt_rec")
        currentMode = ".txt_rec"
        esp.requestCapture("captureHigh")
    elif message == "$#TXT#$touch1_double":
        guiServer.sendMessage("activate", ".obj_dtc")
        currentMode = ".obj_dtc"
        esp.requestCapture("captureHigh")
    elif message == "$#TXT#$touch1_hold":
        guiServer.sendMessage("activate", ".img_des")
        currentMode = ".img_des"
        esp.requestCapture("captureHigh")
    elif message == "$#TXT#$touch2_single":
        guiServer.sendMessage("activate", ".freeform")
        currentMode = ".freeform"
        esp.requestCapture("captureHigh")
    elif message == "$#TXT#$touch2_double":
        guiServer.sendMessage("activate", ".coord")
        currentMode = ".coord"
        esp.requestCapture("captureHigh")
    elif message == "$#TXT#$touch2_hold":
        guiServer.sendMessage("activate", "terminateTask")
        esp.requestCapture("stopStream")

# handles images from esp32 
lastSendTime = 0
def espImageHandler(image):
    global coordRunning, tracker
    if tracker is not None:
        if coordRunning and tracker.processingFrame:
            return  # drop frame immediately if tracker is still processing
    
    global currentImage
    currentImage = image

    guiServer.sendMessage("IMG", image)

    if currentMode == ".freeform":
        guiServer.sendMessage("loader", "40")
        guiServer.sendMessage("log", "Waiting for user input...")
        if voiceServer.loop:
            asyncio.run_coroutine_threadsafe(executeFreeform(), voiceServer.loop) # run in the same asyncio loop as voiceServer
    elif currentMode == ".txt_rec":
        guiServer.sendMessage("loader", "60")
        guiServer.sendMessage("log", "Waiting for gemini to respond...")
        executeTextRecognition()
    elif currentMode == ".obj_dtc":
        guiServer.sendMessage("loader", "60")
        guiServer.sendMessage("log", "Waiting for gemini to respond...")
        executeObjectDetection()
    elif currentMode == ".img_des":
        guiServer.sendMessage("loader", "60")
        guiServer.sendMessage("log", "Waiting for gemini to respond...")
        executeImageDescription()

    if not coordRunning:
        if currentMode == ".coord":
            coordRunning = True
            guiServer.sendMessage("loader", "30")
            guiServer.sendMessage("log", "Waiting for user input...")

            if voiceServer.loop:
                asyncio.run_coroutine_threadsafe(executeCoordination(), voiceServer.loop) # run in the same asyncio loop as voiceServer
    else:
        global trackerInitialized, lastSendTime
        if trackerInitialized and tracker is not None and time.time() - lastSendTime > 0.1: # cap at 10FPS
            global objRIO_norm, handRIO_norm, trackedObjName
            coordinates = tracker.getCoordinates(currentImage)
            
            if coordinates[1] is not None:
                objRIO_norm = coordinates[1]
            else:
                objRIO_norm = (0,0,0,0)

            if coordinates[0] is not None:
                handRIO_norm = coordinates[0]
            else:
                handRIO_norm = (0,0,0,0)

            objx, objy, objw, objh = objRIO_norm
            handx, handy, handw, handh = handRIO_norm
            coordinateDict = {
                "object": {
                    "x": objx,
                    "y": objy,
                    "width": objw,
                    "height": objh,
                    "label": trackedObjName
                },
                "hand":{
                    "x": handx,
                    "y": handy,
                    "width": handw,
                    "height": handh,
                    "label": "Hand"
                }
            }
            coordinateJSONstring = json.dumps(coordinateDict)

            guiServer.sendMessage("coordinates", coordinateJSONstring)
            lastSendTime = time.time()
    return

# --------------- Voice client functions ---------------

# this function is triggered when the voice client is connected
def onVoiceClientConnect():
    global voiceConnected
    voiceConnected = True
    print(colored("Voice client connected!", "light_green"))

# --------------- GUI client functions ---------------

# this function is triggered when the GUI server is connected to the GUI client
def onGUIclientConnect():
    global guiConnected
    guiConnected = True
    print(colored("GUI client connected!", "light_green"))

    global espOnindicated, voiceOnIndicated, voiceConnected
    espOnindicated = False
    voiceOnIndicated = False
    voiceConnected = False

# handle messages from GUI client
def onGUIclientMessage(message):
    global currentMode
    if message in [".freeform", ".txt_rec", ".obj_dtc", ".img_des"]:
        currentMode = message
        esp.requestCapture("captureHigh")
        guiServer.sendMessage("activate", message) # assure gui that the feature is activated and is running
        guiServer.sendMessage("loader", "20")
        guiServer.sendMessage("log", "Fetching image...")

    elif message == ".coord":
        currentMode = message
        esp.requestCapture("startStream")
        guiServer.sendMessage("activate", message) # assure gui that the feature is activated and is running
        guiServer.sendMessage("loader", "15")
        guiServer.sendMessage("log", "Fetching image...")

    elif message == 'terminate':
        voiceServer.stopUttering()

        # reset variables and objects
        global trackedObjName, trackerInitialized, tracker, coordRunning
        currentMode = None
        trackedObjName = None
        trackerInitialized = False
        tracker = None

        if coordRunning:
            esp.requestCapture("stopStream")

        coordRunning = False

        print(colored("All processes terminated.", "yellow"))


    elif message == 'startStream':
        currentMode = "streaming"
        esp.requestCapture("startStream")

    elif message == 'stopStream':
        currentMode = None
        esp.requestCapture("stopStream")

# --------------- Main user feature functions ---------------

# all main user features
async def executeFreeform():
    voiceContentFuture = voiceServer.getVoiceContentFuture()
    voiceContent = await voiceContentFuture

    print(colored(f"User said: {voiceContent}", "blue"))

    guiServer.sendMessage("loader", "70")
    guiServer.sendMessage("log", f"User said: {voiceContent}")

    geminiClientFast.generateContentStream(AIistructions[currentMode], voiceContent, currentImage)

async def executeCoordination():
    voiceContentFuture = voiceServer.getVoiceContentFuture()
    voiceContent = await voiceContentFuture

    print(colored(f"User said: {voiceContent}", "blue"))

    global trackedObjName
    trackedObjName = voiceContent

    guiServer.sendMessage("loader", "60")
    guiServer.sendMessage("log", f"Getting initial coordinates of hand and {voiceContent}...")

    geminiClientCoord.generateContentStream(AIistructions[currentMode], voiceContent, currentImage)
    return

def executeTextRecognition():
    geminiClientFast.generateContentStream(AIistructions[currentMode], "What is written here?", currentImage)

def executeObjectDetection():
    geminiClientFast.generateContentStream(AIistructions[currentMode], "What are the objects in this image?", currentImage)

def executeImageDescription():
    geminiClientFast.generateContentStream(AIistructions[currentMode], "Describe this image.", currentImage)


# gemini objects
geminiClientFast = GeminiClient(geminiAPIkey, "gemini-2.5-flash-lite", onContentChunk=fastGeminiResponseHandler)
geminiClientCoord = GeminiClient(geminiAPIkey, "gemini-2.5-flash", onContentChunk=coordGeminiResponseHandler)

# start esp32 websocket client
esp = ESP32WebSocket(onConnect=onespConnect, onMessage=espMessageHandler, onImage=espImageHandler)
esp.start()

# start voice server
voiceServer = Voice(onConnect=onVoiceClientConnect)
voiceServer.start()

# start GUI server
guiServer = GUI(onConnect=onGUIclientConnect, onMessage=onGUIclientMessage)
guiServer.start()

espOnindicated = False
voiceOnIndicated = False
# keep operations alive
while True:
    time.sleep(1)
    if espConnected and guiConnected and not espOnindicated:
        guiServer.sendMessage("activate", "espConnected")
        espOnindicated = True
    if voiceConnected and guiConnected and not voiceOnIndicated:
        guiServer.sendMessage("activate", "voiceConnected")
        voiceOnIndicated = True