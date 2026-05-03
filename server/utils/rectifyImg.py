import cv2
import numpy as np
import json

IMG_ID = 26 # Adjust this to test different images from dataset

LEFT_IMAGE_PATH = f'../camSampleImages/left/{IMG_ID}.jpg'
RIGHT_IMAGE_PATH = f'../camSampleImages/right/{IMG_ID}.jpg'
CALIBRATION_JSON_PATH = '../stereoCalibParams.json'

# load the calibration data
with open(CALIBRATION_JSON_PATH, 'r') as f:
    data = json.load(f)

# Helper to convert lists to numpy arrays
K1 = np.array(data['intrinsicLeft']['cameraMatrix'])
D1 = np.array(data['intrinsicLeft']['distCoeffs'])
K2 = np.array(data['intrinsicRight']['cameraMatrix'])
D2 = np.array(data['intrinsicRight']['distCoeffs'])
R = np.array(data['extrinsicStereo']['rotationMatrixR'])
T = np.array(data['extrinsicStereo']['translationVectorT'])

# load the images
img_left = cv2.imread(LEFT_IMAGE_PATH)
img_right = cv2.imread(RIGHT_IMAGE_PATH)
h, w = img_left.shape[:2]

# compute Rectification Transforms
# higher alpha means more of the original image is retained (with black borders), while lower alpha means more cropping but less distortion. 0 means no black borders, 1 means all pixels are retained.
R1, R2, P1, P2, Q, roi_left, roi_right = cv2.stereoRectify(
    K1, D1, K2, D2, (w, h), R, T, alpha=0
)

# create the mapping for rectification
map1_x, map1_y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, (w, h), cv2.CV_32FC1)
map2_x, map2_y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, (w, h), cv2.CV_32FC1)

# apply the maps
rectified_left = cv2.remap(img_left, map1_x, map1_y, cv2.INTER_LINEAR)
rectified_right = cv2.remap(img_right, map2_x, map2_y, cv2.INTER_LINEAR)

# visualization: Draw horizontal lines to check alignment
combined = np.hstack((rectified_left, rectified_right))
for i in range(0, combined.shape[0], 30):
    cv2.line(combined, (0, i), (combined.shape[1], i), (0, 255, 0), 1)

cv2.imshow('Rectified Stereo Pair (Green lines should cross same points)', combined)
cv2.waitKey(0)
cv2.destroyAllWindows()