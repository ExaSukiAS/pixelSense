"""
Left and Right perspoctive of two esp32 boards:
    In most parts of code:
        Here, "left board and right board" is defined in the perspective of the front side of the PCB where the camera is located, so the left board's camera is on the left side when you are facing the front of the PCB, and the right board's camera is on the right side.
    In saving calibration images:
        Here, "left and right" is reversed because of the camera orientation in the ESP32 glasses. The left board's camera captures the right perspective and the right board's camera captures the left perspective, so we save the left board's images in the "right" folder and the right board's images in the "left" folder for calibration to match the actual perspective captured by each camera.
"""

import time
import json
import re
import cv2
from termcolor import colored
from halo import Halo
import numpy as np

from ESP32handler import ESP32
from Gemini import GeminiClient
from Tracker import Tracker
from UIhandler import GUI
from TTShandler import TTS
from STThandler import STT
from Depthmap import DepthAnalysis

# gemini configuration
GEMINI_KEY_ID = "4"

# ESP32 IP addresses
ESP_LEFT_IP = "192.168.137.164"
ESP_RIGHT_IP = "192.168.137.178"

# depth map visualization configurations
MIN_DISTANCE_CM = 5.0
MAX_DISTANCE_CM = 250.0

# live features max FPS
COORD_MAX_FPS = 10
DEPTH_MAX_FPS = 2

currentMode = None # current mode (.freeform, .coord, .txt_rec, .img_des, .obj_dtc, .depth_est, singleStreaming, dualStreaming, None)
currentImage = None
coordRunning = False # status of coordination feature
depthRunning = False # status of depth estimation feature
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
    geminiAPIkey = apiKeys[GEMINI_KEY_ID]
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
        esp.requestCapture("stpSingleImgStream")
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
lastCoordProcessTime = 0
def espImageHandler(boardType, image):
    global coordRunning, tracker
    if tracker is not None:
        if coordRunning and tracker.processingFrame:
            return  # drop frame immediately if tracker is still processing
    
    global currentImage
    currentImage = image

    prefix = b'\x01' if boardType == "left" else b'\x02' # convert the boardType to a single byte prefix ('1' for left, '2' for right)
    dummyFrameID = 0 # we don't need frame id in single image stream, but we can set it to 0 as a placeholder
    frameIDBytes = dummyFrameID.to_bytes(4, byteorder='big') # create 4byte frameID header
    imgWithHeader = prefix +  frameIDBytes + image

    guiServer.sendMessage("IMG", imgWithHeader)

    if currentMode == ".freeform":
        guiServer.sendMessage("loader", "40@#$@Waiting for user prompt")
        espRight.requestMicSampleStream()
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

    if not coordRunning and currentMode == ".coord":
            coordRunning = True
            guiServer.sendMessage("loader", "30@#$@Waiting for user prompt")
            espRight.requestMicSampleStream()
            stt.startRecording()
    else:
        global trackerInitialized, lastCoordProcessTime
        if trackerInitialized and tracker is not None and time.time() - lastCoordProcessTime > 1 / COORD_MAX_FPS: # cap at specified FPS
            global objRIO_norm, handRIO_norm, trackedObjName
            coordinates = tracker.getCoordinates(currentImage)
            
            # Update Object coordinates only if we get a valid result. 
            if coordinates[1] is not None:
                objRIO_norm = coordinates[1]
            elif objRIO_norm is None:
                objRIO_norm = (0,0,0,0)

            # Update Hand coordinates only if we get a valid result.
            if coordinates[0] is not None:
                handRIO_norm = coordinates[0]
            elif handRIO_norm is None:
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
            guiServer.sendMessage("log", f"Move: {coordinates[2]}") # send grab direction
            lastCoordProcessTime = time.time()
    return

# store the incoming frames until both left and right frames are received for dual capture
# Structure: {frameID: {"left": {imageData, TOF distance}, "right": {imageData, TOF distance}}}
syncedImagePairs = {}

imagePairsCache = {} # store the last 5 pairs of images for calibration (removes the oldest pair when a new pair is added beyond 5 pairs to limit memory usage)

# handles synchronized images from both ESP32s for features that require dual images (e.g. camera calibration and depth estimation)
lastDepthProcessTime = 0
def espSyncedImageHandler(boardType, image, frameID, dist_cm):
    global depthRunning, lastDepthProcessTime

    if not depthRunning and currentMode == ".depth_est":
        depthRunning = True

    if frameID is not None:
        # create the basic structure for the frameID if it doesn't exist
        if frameID not in syncedImagePairs:
            syncedImagePairs[frameID] = {"left": None, "right": None}

        syncedImagePairs[frameID][boardType] = {"image": image, "dist_cm": dist_cm} # store the image and TOF distance for the corresponding board type

        # check if both left and right frames are received for the frameID
        if syncedImagePairs[frameID]["left"] is not None and syncedImagePairs[frameID]["right"] is not None:
            if depthRunning and depthAnalyzer.processingImage:
                return # drop the pair if depth analyzer is still processing the previous pair to avoid overlapping computations

            leftData = syncedImagePairs[frameID]["left"]
            rightData = syncedImagePairs[frameID]["right"]

            frameIDBytes = frameID.to_bytes(4, byteorder='big') # create 4byte frameID header for sending as header with image payload to GUI


            if depthRunning and time.time() - lastDepthProcessTime > 1 / DEPTH_MAX_FPS: # cap depth estimation at specified FPS to allow for processing time
                lastDepthProcessTime = time.time()
                depthMap = depthAnalyzer.getDepthMap(rightData["image"], leftData["image"]) # IMPORTANT: left andright images are reversed dueto the camera orientation in the ESP32 glasses, so we need to input right image first and left image second for correct depth estimation
                if depthMap is not None:
                    validMask = (depthMap > 0) & (depthMap <= MAX_DISTANCE_CM * 10.0)
                    depthMapClipped = np.clip(depthMap, MIN_DISTANCE_CM * 10.0, MAX_DISTANCE_CM * 10.0)
                    depthVis = cv2.normalize(depthMapClipped, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U) #normalize data to 0-255 values
                    depthColor = cv2.applyColorMap(depthVis, cv2.COLORMAP_MAGMA) # apply colormap for better visualization
                    depthColor[~validMask] = [0, 0, 0] # set invalid and out-of-range pixels to white

                    # convert depthColor to jpeg bytes and send to GUI with a prefix to indicate it's a depth map
                    _, depthColorJpeg = cv2.imencode('.jpg', depthColor)
                    depthImgPrefix = b'\x03' # prefix for depth map image
                    depthImgWithHeader = depthImgPrefix + frameIDBytes + depthColorJpeg.tobytes()
                    guiServer.sendMessage("IMG", depthImgWithHeader)

                    # send raw depth distances to GUI
                    rawDepthBytes = b'\x04' + depthMapClipped.astype(np.uint16).tobytes()
                    guiServer.sendMessage("IMG", rawDepthBytes)


            # send syncrponized images to GUI with a prefix to indicate the board type
            leftPrefix = b'\x01' # prefix for left image 
            leftImgWithHeader = leftPrefix + frameIDBytes + leftData["image"]
            rightPrefix = b'\x02' # prefix for right image
            rightImgWithHeader = rightPrefix + frameIDBytes + rightData["image"]

            guiServer.sendMessage("IMG", leftImgWithHeader)
            guiServer.sendMessage("IMG", rightImgWithHeader)

            # cache the image pairs in memory
            imagePairsCache[frameID] = {"left": leftData["image"], "right": rightData["image"]}
            if len(imagePairsCache) > 5: # limit cache to last 5 pairs
                oldestFrameID = min(imagePairsCache.keys())
                del imagePairsCache[oldestFrameID]

            syncedImagePairs.pop(frameID, None) # remove the pair from storage after processing to free up memory

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

    # parse the message to extract the type and content (if any)
    msgType = ""
    msg = ""
    if "," in message:
        msgType, msg = message.split(",", 1)
    else:
        msgType = message
        msg = ""

    if msgType in [".freeform", ".txt_rec", ".obj_dtc", ".img_des"]:
        currentMode = msgType
        espLeft.requestCapture("captureLow")
        guiServer.sendMessage("activate", msgType) # assure gui that the feature is activated and is running
        guiServer.sendMessage("loader", "20@#$@Fetching image")

    elif msgType == ".coord":
        currentMode = msgType
        espLeft.requestCapture("strtSingleImgStream")
        guiServer.sendMessage("activate", msgType) # assure gui that the feature is activated and is running
        guiServer.sendMessage("loader", "15@#$@Fetching image")
    
    elif msgType == ".depth_est":
        currentMode = msgType
        espLeft.requestCapture("strtDualImgStream")
        guiServer.sendMessage("activate", msgType) # assure gui that the feature is activated and is running

        espLeft.requestCapture("stpSingleImgStream")
        espRight.requestCapture("stpSingleImgStream")
        espLeft.requestCapture("strtDualImgStream")

    elif msgType == 'terminate':
        espLeft.stopMicSampleStream()
        tts.stopRunningSynth()
        espLeft.requestCapture("stpDualImgStream")
        espLeft.requestCapture("stpSingleImgStream")
        espRight.requestCapture("stpSingleImgStream")

        # reset variables and objects
        global trackedObjName, trackerInitialized, tracker, coordRunning, depthRunning
        currentMode = None
        trackedObjName = None
        trackerInitialized = False
        tracker = None
        coordRunning = False
        depthRunning = False

        print(colored("All processes terminated.", "yellow"))

    # streaming messages
    elif msgType == 'startLeftImageStream':
        currentMode = "streaming"
        streamingState["left"] = True

        # switch to synced dual streaming if boath ESP need to stream image
        if streamingState["left"] and streamingState["right"]:
            currentMode = "dualStreaming"
            espRight.requestCapture("stpSingleImgStream")
            time.sleep(0.5)
            espLeft.requestCapture("strtDualImgStream")
        else:
            currentMode = "singleStreaming"
            espLeft.requestCapture("strtSingleImgStream")
    elif msgType == 'stopLeftImageStream':
        if streamingState["left"] and streamingState["right"]:
            currentMode = "singleStreaming"
            espLeft.requestCapture("stpDualImgStream")
            time.sleep(0.5)
            espRight.requestCapture("strtSingleImgStream")
            streamingState["right"] = False
        else:
            currentMode = None
            espLeft.requestCapture("stpSingleImgStream")

        streamingState["left"] = False
    elif msgType == 'startRightImageStream':
        currentMode = "streaming"
        streamingState["right"] = True

        # switch to synced dual streaming if boath ESP need to stream image
        if streamingState["left"] and streamingState["right"]:
            currentMode = "dualStreaming"
            espLeft.requestCapture("stpSingleImgStream")
            time.sleep(0.5)
            espLeft.requestCapture("strtDualImgStream")
        else:
            currentMode = "singleStreaming"
            espRight.requestCapture("strtSingleImgStream")
    elif msgType == 'stopRightImageStream':
        if streamingState["left"] and streamingState["right"]:
            currentMode = "singleStreaming"
            espLeft.requestCapture("stpDualImgStream")
            time.sleep(0.5)
            espLeft.requestCapture("strtSingleImgStream")
            streamingState["left"] = False
        else:
            currentMode = None
            espRight.requestCapture("stpSingleImgStream")

        streamingState["right"] = False

    elif msgType == "saveImg_calib" or msgType == "saveImg_sample":
        if currentMode == "dualStreaming":
            try:
                frameID = int(msg)
            except ValueError:
                print(colored(f"Invalid frameID received: '{msg}'", "red"))
                return # exit this block if it's not a valid number

            """Left and Right paths are reversed because we are taking perspective of user who is wearing the glasses"""
            if frameID in imagePairsCache:
                pair = imagePairsCache[frameID]
                with open(f"./{'camCalibImages' if msgType == 'saveImg_calib' else 'camSampleImages'}/right/{frameID}.jpg", "wb") as f:
                    f.write(pair["left"])
                with open(f"./{'camCalibImages' if msgType == 'saveImg_calib' else 'camSampleImages'}/left/{frameID}.jpg", "wb") as f:
                    f.write(pair["right"])
                print(colored(f"Saved image pair with frameID {frameID} for { 'calibration' if msgType == 'saveImg_calib' else 'sampling' }.", "green"))
            else:
                print(colored(f"No image pair found in cache for frameID {frameID}. Cannot save for { 'calibration' if msgType == 'saveImg_calib' else 'sampling' }.", "red"))


if __name__ == '__main__':
    import multiprocessing
    multiprocessing.freeze_support() 

    # gemini objects
    geminiClientFast = GeminiClient(geminiAPIkey, "gemini-2.5-flash-lite", onContentChunk=fastGeminiResponseHandler)
    geminiClientCoord = GeminiClient(geminiAPIkey, "gemini-2.5-flash", onContentChunk=coordGeminiResponseHandler)

    # depth analysis object
    depthAnalyzer = DepthAnalysis("stereoCalibParams.json")

    # start GUI server
    guiServer = GUI(onConnect=onGUIclientConnect, onMessage=onGUIclientMessage)
    guiServer.start()

    # start esp32 websocket client
    espLeft = ESP32(espIP=ESP_LEFT_IP, boardType="left", imgPort=5005, micPort=5006, statsPort=5007, onConnect=onespConnect, onMessage=espMessageHandler, onImage=espImageHandler, onSyncedImage=espSyncedImageHandler, onStats=espStatsHandler)
    espRight = ESP32(espIP=ESP_RIGHT_IP, boardType="right", imgPort=5008, micPort=5009, statsPort=5010, onConnect=onespConnect, onMessage=espMessageHandler, onMicSamples=onMicSampleHandler, onImage=espImageHandler, onSyncedImage=espSyncedImageHandler, onStats=espStatsHandler)
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