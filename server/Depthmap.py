import cv2
import numpy as np
import json
import os
from termcolor import colored

class DepthAnalysis:
    def __init__(self, calibDataPath):        
        # load calibration calibData
        if not os.path.exists(calibDataPath):
            print(colored(f"Error from DepthAnalysis.__init__: Could not find {calibDataPath}", 'red'))
            return
        with open(calibDataPath, 'r') as f:
            calibData = json.load(f)

        # Get calibration parameters
        self.K1 = np.array(calibData['intrinsicLeft']['cameraMatrix'])        # 3x3 camera matrix for left camera
        self.D1 = np.array(calibData['intrinsicLeft']['distCoeffs'])          # Distortion coefficients for left camera
        self.K2 = np.array(calibData['intrinsicRight']['cameraMatrix'])       # 3x3 camera matrix for right camera
        self.D2 = np.array(calibData['intrinsicRight']['distCoeffs'])         # Distortion coefficients for right camera
        self.R = np.array(calibData['extrinsicStereo']['rotationMatrixR'])    # 3x3 rotation matrix from left to right camera
        self.T = np.array(calibData['extrinsicStereo']['translationVectorT']) # 3x1 translation vector from left to right camera
        self.baselineDist = abs(self.T[0][0])                                 # Baseline in mm (distance between the two cameras)
        self.focalLength = self.K1[0, 0]                                      # Focal length in pixels

        self.currentImgWidth = None
        self.currentImgHeight = None

        self.processingImage = False # indicates if a current image is being processed in getDepthMap() function
    
    # left and right images should be raw JPG bytes (640x480 resolution)
    # returns a 1D array of the depth map
    def getDepthMap(self, leftImg, rightImg):
        if self.processingImage:
            return None # skip if currently processing an image to avoid overlapping computations
        
        if not leftImg or not rightImg:
            print(colored("Error from DepthAnalysis.getDepthMap: Empty image bytes received.", 'red'))
            return None
        
        self.processingImage = True

        try:
            # convert raw bytes to 1D numpy arrays
            left_np_arr = np.frombuffer(leftImg, np.uint8)
            right_np_arr = np.frombuffer(rightImg, np.uint8)

            # decode the arrays into OpenCV BGR images
            decodedLeftImg = cv2.imdecode(left_np_arr, cv2.IMREAD_COLOR)
            decodedRightImg = cv2.imdecode(right_np_arr, cv2.IMREAD_COLOR)

            if decodedLeftImg is None or decodedRightImg is None:
                print(colored("Error from DepthAnalysis.getDepthMap: Failed to decode JPG bytes.", 'red'))
                return None

            # process the decoded images
            rectifiedLeftImg, rectifiedRightImg = self._rectifyImages(decodedLeftImg, decodedRightImg)
            disparityMap = self._getDistarity(rectifiedLeftImg, rectifiedRightImg)
            depthMap = self._convDisparityToDepth(disparityMap)

            return depthMap

        except Exception as e:
            print(colored(f"Error processing depth map: {e}", 'red'))
            return None

        finally:
            self.processingImage = False

    # Rectifies the input left and right images using the stereo calibration parameters. 
    # This process corrects for lens distortion and aligns the images so that corresponding points lie on the same horizontal line
    def _rectifyImages(self, leftImg, rightImg):
        self.currentImgHeight, self.currentImgWidth = leftImg.shape[:2]

        # compute rectification transforms (alpha=0 crops to valid pixels)
        R1, R2, P1, P2, Q, roi_left, roi_right = cv2.stereoRectify(
            self.K1, self.D1, self.K2, self.D2, (self.currentImgWidth, self.currentImgHeight), self.R, self.T, alpha=0
        )

        map1_x, map1_y = cv2.initUndistortRectifyMap(self.K1, self.D1, R1, P1, (self.currentImgWidth, self.currentImgHeight), cv2.CV_32FC1)
        map2_x, map2_y = cv2.initUndistortRectifyMap(self.K2, self.D2, R2, P2, (self.currentImgWidth, self.currentImgHeight), cv2.CV_32FC1)

        rectifiedLeftImg = cv2.remap(leftImg, map1_x, map1_y, cv2.INTER_LINEAR)
        rectifiedRightImg = cv2.remap(rightImg, map2_x, map2_y, cv2.INTER_LINEAR)

        return rectifiedLeftImg, rectifiedRightImg
    
    # Returns a disparity map where each pixel value represents the disparity (in pixels) between the left and right images. 
    # Higher values indicate closer objects, while lower values indicate farther objects. 
    # Invalid or unmatched pixels will have a disparity of 0 or less.
    def _getDistarity(self, rectifiedLeftImg, rectifiedRightImg):
        # Configure SGBM parameters
        blockSize = 5 # block size for matching (must be odd)
        leftMatcher = cv2.StereoSGBM_create(
            minDisparity= 0,
            numDisparities= 16 * 4, # Must be divisible by 16 (highet values allows to detect farther objects but increases computation)
            blockSize=blockSize,
            P1=8 * 3 * blockSize**2,
            P2=32 * 3 * blockSize**2,
            disp12MaxDiff=1,
            uniquenessRatio=15,
            speckleWindowSize=100,
            speckleRange=2,
            mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
        )

        rightMatcher = cv2.ximgproc.createRightMatcher(leftMatcher) # Create a matcher for the right image (for WLS filtering)

        # Configure WLS filter parameters
        wlsFilter = cv2.ximgproc.createDisparityWLSFilter(matcher_left=leftMatcher)
        wlsFilter.setLambda(8000)   
        wlsFilter.setSigmaColor(1.5) 

        # convert to grayscale for disparity computation
        grayImgLeft = cv2.cvtColor(rectifiedLeftImg, cv2.COLOR_BGR2GRAY)
        grayImgRight = cv2.cvtColor(rectifiedRightImg, cv2.COLOR_BGR2GRAY)

        # Compute disparity maps for left and right images
        leftDisparity = leftMatcher.compute(grayImgLeft, grayImgRight)
        rightDisparity = rightMatcher.compute(grayImgRight, grayImgLeft)
        
        filteredDisparity = wlsFilter.filter(leftDisparity, grayImgLeft, disparity_map_right=rightDisparity) # WLS filter the disparity map to reduce noise and improve quality
        actualDisparity = filteredDisparity.astype(np.float32) / 16.0

        return actualDisparity
    
    # Converts a disparity map to a depth map using the formula: Depth = (Focal Length * Baseline) / Disparity.
    # The resulting depth map will have the same dimensions as the input disparity map, where each pixel value represents the estimated depth (in mm) of the corresponding point in the scene.
    def _convDisparityToDepth(self, disparityMap):
        with np.errstate(divide='ignore'):
            depthMap = (self.focalLength * self.baselineDist) / disparityMap
            depthMap[disparityMap <= 0] = 0
        return depthMap