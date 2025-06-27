import sys
import numpy as np
import cv2
import json
import base64

class CSRTtracker:
    tracker = None
    def __init__(self, firstFrame, rio):
        firstFrame = cv2.resize(firstFrame,(0, 0), fx=0.5, fy=0.5) # prepare the first frame
        # create the CSRT tracker and initialize it with the first frame and selected ROI
        self.tracker = cv2.TrackerCSRT_create()
        self.tracker.init(firstFrame, rio)
    def getObjCoordinate(self, frame):
        success, box = self.tracker.update(frame) # update the tracker and get the new position
        if success:
            (x, y, w, h) = [int(v) for v in box]
            return (x, y, w, h)

def main():
    initialized = False
    OBJtracker = None
    frameData = None

    while True:
        line = sys.stdin.readline().strip()  # read a line from standard input
        frameData = json.loads(line)
            
        if(frameData):
            # decode base64 string into OpenCV image
            base64String = frameData["imgBase64"]
            image_bytes = base64.b64decode(base64String)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if not initialized:
                # extract the ROI from the first frame data
                rio = frameData["rio"].split(",")
                rio = tuple(map(int, rio))

                OBJtracker = CSRTtracker(img, rio) # Initialize the tracker with the first frame and ROI
                initialized = True
                print("initialized", flush=True)
            else:
                newRIO = OBJtracker.getObjCoordinate(img) # Get the new position of the object
                print(newRIO, flush=True)
main()