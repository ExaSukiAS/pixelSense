import socket
import json
import base64
import cv2
import os
import mediapipe as mp
import numpy as np
from termcolor import colored

HOST = 'localhost'
PORT = 8001
dataToSend = {"init": False, "objRIO": [], "handRIO": []} # this is the data structure to send to JS side

# Initialize MediaPipe for hand detection
mp_hands = mp.solutions.hands

# Create a TCP server socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)
print(colored(f"\nListening on {HOST}:{PORT}", "green", attrs=["bold"]))

# tracker variables
initialized = False
OBJtracker = None
frameData = None
confidenceThreshold = 0.5 # minimum confidence score to consider tracking successful
trackerModelPath = os.path.join(os.path.dirname(__file__), "object_tracking_vittrack_2023sep.onnx") # vitTracker ONNX model path
useRecovery = False # whether to use recovery mechanism when tracking fails

class VitTracker:
    def __init__(self, firstFrame, roi, minConfidence, useRecovery, modelPath):
        params = cv2.TrackerVit_Params()
        params.net = modelPath
        self.tracker = cv2.TrackerVit.create(params)
        self.tracker.init(firstFrame, roi)
        
        self.minConfidence = minConfidence
        self.useRecovery = useRecovery
        
        # Save the template for recovery
        x, y, w, h = [int(v) for v in roi]
        self.template = firstFrame[y:y+h, x:x+w].copy()
        self.obj_size = (w, h) # Keep track of original size

    def getObjCoordinate(self, frame):
        success, box = self.tracker.update(frame)
        score = self.tracker.getTrackingScore()
        
        # Primary Tracking Logic
        if success and score >= self.minConfidence:
            (x, y, w, h) = [int(v) for v in box]
            return (x, y, w, h)

        if self.useRecovery:
            # Recovery Logic (if primary fails)
            res = cv2.matchTemplate(frame, self.template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(res)

            # Re-initialize tracker if recovery confidence is high enough
            if max_val > 0.8:
                print(colored(f"Recovery: Re-initializing tracker with new location (Score: {max_val:.2f})", "yellow"))
                new_roi = (max_loc[0], max_loc[1], self.obj_size[0], self.obj_size[1])
                self.tracker.init(frame, new_roi)
                return None

        return None

# Accept a connection from the Node.js server
conn, addr = server.accept()
print(f"Connected by {addr}")

# Initialize the Hands model
with mp_hands.Hands(
    static_image_mode=True,
    max_num_hands=1,
    min_detection_confidence=0.6
) as hands:
    def getHandCoordinates(imgRGB, imgWidth, imgHeight):
        handCoords = hands.process(imgRGB)
        if handCoords.multi_hand_landmarks:
            for hand_landmarks in handCoords.multi_hand_landmarks:
                x_coords = [lm.x * imgWidth for lm in hand_landmarks.landmark]
                y_coords = [lm.y * imgHeight for lm in hand_landmarks.landmark]
                rio = [int(min(x_coords)), int(min(y_coords)), int(max(x_coords)) - int(min(x_coords)), int(max(y_coords)) - int(min(y_coords))] #x, y, width, height
                return rio
        else:
            return None
        
    buffer = "" # buffer to accumulate incoming data
    while True:
        conn.settimeout(0.1)
        try:
            # Receive data in chunks
            chunk = conn.recv(1024 * 16) 
            if not chunk:
                break
            buffer += chunk.decode('utf-8')
        except socket.timeout:
            pass
        except Exception as e:
            print(f"Error: {e}")
            break

        # Check if we have a full message (\n indicates end of a full message)
        if "\n" in buffer:
            lines = buffer.split("\n")
            # Process all complete lines, keep the last (potentially partial) line in buffer
            buffer = lines.pop() 

            for line in lines:
                if not line.strip():
                    continue
                try:
                    frameData = json.loads(line)
                except json.JSONDecodeError:
                    print(colored("Error decoding JSON: Message was incomplete.", "red"))
                    continue

        if frameData:
            # decode base64 string into OpenCV image
            base64String = frameData.get("imgBase64")
            if not base64String:
                continue
            
            # Decode the base64 string to an image
            image_bytes = base64.b64decode(base64String)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR) # BGR format
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB) # RGB format
            imgHeight, imgWidth, _ = img.shape # image dimensions

            if img is None:
                print("Error decoding image.")
                continue
            
            if not initialized:
                objRIO = frameData.get("objRIO")
                if objRIO is None:
                    print("RIO not found in frameData.")
                    continue

                objRIO = tuple(map(int, objRIO))
                OBJtracker = VitTracker(img, objRIO, confidenceThreshold, useRecovery, trackerModelPath)
                initialized = True
                print("initialized vitTracker with rio:", objRIO)
                conn.send(json.dumps({"init": True, "objRIO": [], "handRIO": []}).encode())
                
                (ox, oy, ow, oh) = map(int, frameData.get("objRIO", objRIO))
                cv2.rectangle(img, (ox, oy), (ox + ow, oy + oh), (0, 0, 255), 2)
            else:
                
                # check for reset command
                if frameData.get("reset", False):
                    initialized = False
                    OBJtracker = None
                    print("Resetting tracker")
                    continue

                newObjRIO = OBJtracker.getObjCoordinate(img)
                #newHandRIO = getHandCoordinates(imgRGB, imgWidth, imgHeight)
                newHandRIO = [0, 0, 0, 0] # for testing without hand tracking

                # convert rio to normalized format
                normObjRIO = [newObjRIO[0] / imgWidth, newObjRIO[1] / imgHeight, newObjRIO[2] / imgWidth, newObjRIO[3] / imgHeight] if newObjRIO else [0, 0, 0, 0]
                normHandRIO = [newHandRIO[0] / imgWidth, newHandRIO[1] / imgHeight, newHandRIO[2] / imgWidth, newHandRIO[3] / imgHeight] if newHandRIO else [0, 0, 0, 0]
                conn.send(json.dumps({"init": True, "objRIO": normObjRIO, "handRIO": normHandRIO}).encode())
                
                if newObjRIO and newHandRIO:
                    # show predicted ROI of object
                    (ox, oy, ow, oh) = map(int, frameData.get("objRIO", newObjRIO))
                    cv2.rectangle(img, (ox, oy), (ox + ow, oy + oh), (0, 0, 255), 2)
                    # show hand RIO
                    (hx, hy, hw, hh) = map(int, newHandRIO)
                    cv2.rectangle(img, (hx, hy), (hx + hw, hy + hh), (255, 0, 0), 2)

            # --- Show the image window ---
            scale = 0.5
            display_img = cv2.resize(img, (0, 0), fx=scale, fy=scale)
            cv2.imshow("Tracking", display_img)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
conn.close()
server.close()