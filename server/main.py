import time
import json
import re
from termcolor import colored
from ESP32handler import ESP32
from Gemini import GeminiClient
from Tracker import Tracker
from UIhandler import GUI
from TTShandler import TTS
from STThandler import STT
from halo import Halo

# gemini configuration
geminiKeyToUse = "6"

currentMode = None # current mode (.freeform, .coord, .txt_rec, .img_des, .obj_dtc, streaming, None)
currentImage = None
coordRunning = False # status of coordination feature
streamingState = {"left": False, "right": False} # stores the streaming state of the two esp, False for not streaming and True for streaming

trackerConfidenceThreshold = 0.5 # minimum confidence threshold for tracking hand and target object in coordination mode
tracker = None
trackerInitialized = False
initialObjRIO_norm = None
objRIO_norm = None
handRIO_norm = None
trackedObjName = None

guiConnected = False
espRightConnected = False
espLeftConnected = False

sttInitialized = False
espOnindicated = False

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
        guiServer.sendMessage("loader", "")
        guiServer.sendMessage("log", fullResponse)
        fullResponse = ""
        return 
    
    guiServer.sendMessage("loader", "80@#$@Parsing Gemini content stream")
    guiServer.sendMessage("log", fullResponse)

    # sanitizes text for Text-to-Speech by removing markdown formatting, emojis, and unwanted symbols
    def sanitize_for_tts(text):
        text = re.sub(r'[`*_~^#>|]', '', text)
        text = re.sub(r"[^\w\s.,!?'\"():;-]", '', text)
        text = re.sub(r'_', '', text)
        return text
    
    if responseChunk is not None:
        fullResponse += responseChunk
        tts.queueTextForSynth(sanitize_for_tts(responseChunk))

    return

# handles response from gemini flash model
coordResponse = "" # gemini stream chunk accumulator
def coordGeminiResponseHandler(responseChunk):
    global coordResponse
    if responseChunk == "#$$#": # detect end of stream
        guiServer.sendMessage("loader", "85@#$@Initializing object and hand tracker models")

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
        guiServer.sendMessage("loader", "")
    else:
        coordResponse += responseChunk
        guiServer.sendMessage("loader", "70@#$@Fetching initial object coordinates")
    return

# --------------- ESP32 functions ---------------

# this function is trigered when esp32 is connected
def onespConnect(boardType):
    if boardType == "right":
        global espRightConnected
        espRightConnected = True
        print(colored("Right ESP32 connected!", "light_green"))
    elif boardType == "left":
        global espLeftConnected
        espLeftConnected = True
        print(colored("Left ESP32 connected!", "light_green"))

# handles messages from esp32
def espMessageHandler(boardType, message):
    global currentMode
    """
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
        esp.requestCapture("stopImageStream")
    """

def espStatsHandler(boardType, stats):
    espStats = [
        stats[0],            # Total SRAM
        stats[1],            # Total PSRAM
        stats[0] - stats[2], # Used SRAM
        stats[1] - stats[3], # Used PSRAM
        stats[4],            # CPU MHz
        stats[5],            # Battery voltage
        stats[6],            # TOF distance
        stats[7]             # WiFi signal
    ]
    statsString = ",".join(map(str, espStats)) # convert the new list to a comma-separated string
    statsString += f"${boardType}" # saperate board type from the payload by the "$" sign
    guiServer.sendMessage("stats", statsString)

# handles images from esp32 
# executes features(.txt_rec, .freeform, .obj_dtc, .img_des and .coord) upon receiving an image
lastSendTime = 0
def espImageHandler(boardType, image):
    global coordRunning, tracker
    if tracker is not None:
        if coordRunning and tracker.processingFrame:
            return  # drop frame immediately if tracker is still processing
    
    global currentImage
    currentImage = image

    prefix = b'\x01' if boardType == "left" else b'\x02' # convert the boardType to a single byte prefix ('1' for left, '2' for right)
    imgWithHeader = prefix + image

    guiServer.sendMessage("IMG", imgWithHeader)

    if currentMode == ".freeform":
        guiServer.sendMessage("loader", "40@#$@Waiting for user prompt")
        espLeft.requestMicSampleStream()
        stt.startRecording()
    elif currentMode == ".txt_rec":
        guiServer.sendMessage("loader", "60@#$@Waiting for Gemini response")
        geminiClientFast.generateContentStream(AIistructions[currentMode], "What is written here?", currentImage)
    elif currentMode == ".obj_dtc":
        guiServer.sendMessage("loader", "60@#$@Waiting for Gemini response")
        geminiClientFast.generateContentStream(AIistructions[currentMode], "What are the objects in this image?", currentImage)
    elif currentMode == ".img_des":
        guiServer.sendMessage("loader", "60@#$@Waiting for Gemini response")
        geminiClientFast.generateContentStream(AIistructions[currentMode], "Describe this image.", currentImage)

    if not coordRunning:
        if currentMode == ".coord":
            coordRunning = True
            guiServer.sendMessage("loader", "30@#$@Waiting for user prompt")
            espLeft.requestMicSampleStream()
            stt.startRecording()
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

def onMicSampleHandler(boardType, samples):
    stt.feedAudioSamples(samples)

# --------------- Text to speech object functions ---------------

def onAudioSamples(audioChunk):
    espLeft.queueSamplesForStream(audioChunk)
    return

def onSynthComplete():
    return

# --------------- Speech to text object functions ---------------

def onSpeechTranscription(text):
    print(colored(f"User said: {text}", "blue"))

    global currentMode

    if currentMode == ".freeform":
        guiServer.sendMessage("loader", f"70@#$@User said: {text}")
        geminiClientFast.generateContentStream(AIistructions[currentMode], text, currentImage)
    elif currentMode == ".coord":
        global trackedObjName
        trackedObjName = text
        guiServer.sendMessage("loader", f"60@#$@Getting initial coordinates of hand and {text}")
        geminiClientCoord.generateContentStream(AIistructions[currentMode], text, currentImage)

    espLeft.stopMicSampleStream()

# --------------- GUI client functions ---------------

# this function is triggered when the GUI server is connected to the GUI client
def onGUIclientConnect():
    global guiConnected
    guiConnected = True
    print(colored("GUI client connected!", "light_green"))

    global espOnindicated
    espOnindicated = False

# handle messages from GUI client
def onGUIclientMessage(message):
    global currentMode
    if message in [".freeform", ".txt_rec", ".obj_dtc", ".img_des"]:
        currentMode = message
        espLeft.requestCapture("captureHigh")
        guiServer.sendMessage("activate", message) # assure gui that the feature is activated and is running
        guiServer.sendMessage("loader", "20@#$@Fetching image")

    elif message == ".coord":
        currentMode = message
        espLeft.requestCapture("startImageStream")
        guiServer.sendMessage("activate", message) # assure gui that the feature is activated and is running
        guiServer.sendMessage("loader", "15@#$@Fetching image")

    elif message == 'terminate':
        espLeft.stopAudioStream()

        # reset variables and objects
        global trackedObjName, trackerInitialized, tracker, coordRunning
        currentMode = None
        trackedObjName = None
        trackerInitialized = False
        tracker = None

        if coordRunning:
            espLeft.requestCapture("stopImageStream")

        coordRunning = False

        print(colored("All processes terminated.", "yellow"))

    # streaming messages
    elif message == 'startLeftImageStream':
        currentMode = "streaming"
        streamingState["left"] = True
        espLeft.requestCapture("startImageStream")
    elif message == 'stopLeftImageStream':
        streamingState["left"] = False
        espLeft.requestCapture("stopImageStream")
    elif message == 'startRightImageStream':
        currentMode = "streaming"
        streamingState["right"] = True
        espRight.requestCapture("startImageStream")
    elif message == 'stopRightImageStream':
        streamingState["right"] = False
        espRight.requestCapture("stopImageStream")

if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support() 

    # gemini objects
    geminiClientFast = GeminiClient(geminiAPIkey, "gemini-2.0-flash-lite", onContentChunk=fastGeminiResponseHandler)
    geminiClientCoord = GeminiClient(geminiAPIkey, "gemini-2.0-flash", onContentChunk=coordGeminiResponseHandler)

    # start GUI server
    guiServer = GUI(onConnect=onGUIclientConnect, onMessage=onGUIclientMessage)
    guiServer.start()

    # start esp32 websocket client
    espLeft = ESP32(espIP="192.168.68.102", boardType="left", imgPort=5005, micPort=5006, statsPort=5007, onConnect=onespConnect, onMessage=espMessageHandler, onMicSamples=onMicSampleHandler, onImage=espImageHandler, onStats=espStatsHandler)
    espRight = ESP32(espIP="192.168.68.104", boardType="right", imgPort=5008, micPort=5009, statsPort=5010, onConnect=onespConnect, onMessage=espMessageHandler, onImage=espImageHandler, onStats=espStatsHandler)
    espLeft.start()
    espRight.start()

    # piper text to speech (tts) object
    tts = TTS(onAudioSamples=onAudioSamples, onSynthComplete=onSynthComplete)

    # keep operations alive
    while True:
        time.sleep(1)
        if espRightConnected and espLeftConnected and guiConnected and not espOnindicated:
            guiServer.sendMessage("activate", "espLeftConnected")
            guiServer.sendMessage("activate", "espRightConnected")
            espOnindicated = True
        if not sttInitialized:
            # tiny whisper speech to text (stt) object
            with Halo(text='Initializing STT...', spinner='dots'):
                stt = STT(onTranscription=onSpeechTranscription)
            sttInitialized = True