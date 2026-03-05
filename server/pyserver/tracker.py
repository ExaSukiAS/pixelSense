import cv2
import mediapipe as mp
import numpy as np
from termcolor import colored

class Tracker:
    def __init__(self, firstFrame, roi_normalized, minConfidenceThreshold, useRecovery):
        self.processingFrame = False # indicates if a current frame is being processed in getCoordinates() function

        self.firstFrameRGB, self.firstFrameBGR, self.imgHeight, self.imgWidth = self.decodeImage(firstFrame)
        # convert 0 - 1000 scale normalized rio to pixel format
        x_min_n, y_min_n, x_max_n, y_max_n = roi_normalized
        x_min = int((x_min_n / 1000.0) * self.imgWidth)
        y_min = int((y_min_n / 1000.0) * self.imgHeight)
        x_max = int((x_max_n / 1000.0) * self.imgWidth)
        y_max = int((y_max_n / 1000.0) * self.imgHeight)
        w = x_max - x_min
        h = y_max - y_min
        roi = (int(x_min), int(y_min), int(w), int(h))

        self.minConfidenceThreshold = minConfidenceThreshold

        # Vit tracker initialization
        self.useRecovery = useRecovery
        modelPath = r"../tracker/object_tracking_vittrack_2023sep.onnx"
        params = cv2.TrackerVit_Params()
        params.net = modelPath
        self.objTracker = cv2.TrackerVit.create(params)
        self.objTracker.init(self.firstFrameBGR, roi) # Initialize objTracker
        # save the template for recovery
        self.template = self.firstFrameBGR[y_min:y_min+h, x_min:x_min+w].copy()
        self.obj_size = (w, h)

        print(colored(f"Object tracker initialized with rio(norm): {roi_normalized}", "green"))

        # Initialize MediaPipe for hand detection
        self.mp_hands = mp.solutions.hands
        self.hands = self.mp_hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=self.minConfidenceThreshold
        )
        print(colored("Hand tracker initialized", "green"))
    
    # returns predicted coordinates of hand and object
    def getCoordinates(self, frame):
        self.processingFrame = True

        try:
            frameRGB, frameBGR, frameHeight, frameWidth = self.decodeImage(frame)

            if frameBGR is None or frameWidth == 0 or frameHeight == 0:
                print("Invalid frame received")
                return None, None

            normalizedHandCoord = None
            normalizedObjCoord = None

            # -------------- Object Tracking --------------
            objTrackSuccess, objBox = self.objTracker.update(frameBGR)
            if objTrackSuccess and objBox is not None:
                objTrackScore = self.objTracker.getTrackingScore()

                if objTrackScore >= self.minConfidenceThreshold:
                    x, y, w, h = [int(v) for v in objBox]

                    # Convert to normalized 0–1000 scale
                    x_n = int((x / frameWidth) * 1000)
                    y_n = int((y / frameHeight) * 1000)
                    w_n = int((w / frameWidth) * 1000)
                    h_n = int((h / frameHeight) * 1000)

                    normalizedObjCoord = (x_n, y_n, w_n, h_n)

            # -------------- Hand Detection (MediaPipe) --------------
            results = self.hands.process(frameRGB)

            if results.multi_hand_landmarks:
                hand_landmarks = results.multi_hand_landmarks[0]

                x_coords = [lm.x * frameWidth for lm in hand_landmarks.landmark]
                y_coords = [lm.y * frameHeight for lm in hand_landmarks.landmark]

                x_min = int(min(x_coords))
                y_min = int(min(y_coords))
                x_max = int(max(x_coords))
                y_max = int(max(y_coords))

                w = x_max - x_min
                h = y_max - y_min

                x_n = int((x_min / frameWidth) * 1000)
                y_n = int((y_min / frameHeight) * 1000)
                w_n = int((w / frameWidth) * 1000)
                h_n = int((h / frameHeight) * 1000)

                normalizedHandCoord = (x_n, y_n, w_n, h_n)

            return normalizedHandCoord, normalizedObjCoord

        except Exception as e:
            print(f"Error in getCoordinates(): {e}")
            return None, None

        finally:
            self.processingFrame = False

    # decodes JPEG bytes to RGB image, also returns image height and width
    def decodeImage(self, frame):
        nparr = np.frombuffer(frame, np.uint8)
        frameBGR = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        frameRGB = cv2.cvtColor(frameBGR, cv2.COLOR_BGR2RGB)
        imgHeight, imgWidth, _ = frameRGB.shape
        return (frameRGB, frameBGR, imgHeight, imgWidth)