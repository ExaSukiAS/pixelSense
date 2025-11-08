import socket
import json
import base64
import cv2
import mediapipe as mp
import numpy as np

HOST = 'localhost'
PORT = 8001
dataToSend = {"init": False, "objRIO": [], "handRIO": []} # this is the data structure to send to JS side

# Initialize MediaPipe for hand detection
mp_hands = mp.solutions.hands

# Create a TCP server socket
server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)
print(f"[Python] Listening on {HOST}:{PORT}")

# tracker variables
initialized = False
OBJtracker = None
frameData = None

class CSRTtracker:
    tracker = None
    def __init__(self, firstFrame, rio):
        # Create the CSRT tracker and initialize it with the first frame and selected ROI.
        # The frame is not resized, so the ROI coordinates must be for the original image.
        self.tracker = cv2.TrackerCSRT_create()
        self.tracker.init(firstFrame, rio)

    def getObjCoordinate(self, frame):
        # The tracker is updated with the original, full-size frame.
        success, box = self.tracker.update(frame) # update the tracker and get the new position
        
        if success:
            (x, y, w, h) = [int(v) for v in box]
            return (x, y, w, h)
        return None

# Accept a connection from the Node.js server
conn, addr = server.accept()
print(f"[Python] Connected by {addr}")

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
        
    while True:
        data = conn.recv(150000).decode()  # buffer size for image data
        if not data:
            continue
        try:
            frameData = json.loads(data)
        except json.JSONDecodeError:
            print("Error decoding JSON from node.js")
            continue

        if frameData:
            # decode base64 string into OpenCV image
            base64String = frameData.get("imgBase64")
            if not base64String:
                continue
            
            image_bytes = base64.b64decode(base64String)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
            imgHeight, imgWidth, _ = img.shape

            if img is None:
                print("Error decoding image.")
                continue
            
            if not initialized:
                objRIO = frameData.get("objRIO")
                if objRIO is None:
                    print("RIO not found in frameData.")
                    continue

                objRIO = tuple(map(int, objRIO))
                OBJtracker = CSRTtracker(img, objRIO)
                initialized = True
                print("initialized CSRTtracker with rio:", objRIO)
                conn.send(json.dumps({"init": True, "objRIO": [], "handRIO": []}).encode())
            else:
                """
                # show initial ROI of object
                (ox, oy, ow, oh) = map(int, frameData.get("objRIO", objRIO))
                cv2.rectangle(img, (ox, oy), (ox + ow, oy + oh), (0, 255, 0), 2)
                """
                
                newObjRIO = OBJtracker.getObjCoordinate(img)
                newHandRIO = getHandCoordinates(imgRGB, imgWidth, imgHeight)
                if newObjRIO and newHandRIO:
                    conn.send(json.dumps({"init": True, "objRIO": newObjRIO, "handRIO": newHandRIO}).encode())
                    """
                    # show predicted ROI of object
                    (ox, oy, ow, oh) = map(int, frameData.get("objRIO", newObjRIO))
                    cv2.rectangle(img, (ox, oy), (ox + ow, oy + oh), (0, 0, 255), 2)
                    # show hand RIO
                    (hx, hy, hw, hh) = map(int, newHandRIO)
                    cv2.rectangle(img, (hx, hy), (hx + hw, hy + hh), (255, 0, 0), 2)
                    """
            
            """
            # --- Show the image window ---
            scale = 0.5
            display_img = cv2.resize(img, (0, 0), fx=scale, fy=scale)
            cv2.imshow("Tracking", display_img)
            """