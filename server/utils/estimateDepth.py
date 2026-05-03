import cv2
import numpy as np
import json
import os

IMG_ID = 5939 
LEFT_IMAGE_PATH = f'../camSampleImages/left/{IMG_ID}.jpg'
RIGHT_IMAGE_PATH = f'../camSampleImages/right/{IMG_ID}.jpg'
CALIBRATION_JSON_PATH = '../stereoCalibParams.json'

# --- NEW: Set Maximum Distance Threshold (in cm) ---
MAX_DISTANCE_CM = 250.0  
MIN_DISTANCE_CM = 5.0

def main():
    # load calibration data
    if not os.path.exists(CALIBRATION_JSON_PATH):
        print(f"Error: Could not find {CALIBRATION_JSON_PATH}")
        return
    with open(CALIBRATION_JSON_PATH, 'r') as f:
        data = json.load(f)

    # Get calibration parameters
    K1 = np.array(data['intrinsicLeft']['cameraMatrix'])        # 3x3 camera matrix for left camera
    D1 = np.array(data['intrinsicLeft']['distCoeffs'])          # Distortion coefficients for left camera
    K2 = np.array(data['intrinsicRight']['cameraMatrix'])       # 3x3 camera matrix for right camera
    D2 = np.array(data['intrinsicRight']['distCoeffs'])         # Distortion coefficients for right camera
    R = np.array(data['extrinsicStereo']['rotationMatrixR'])    # 3x3 rotation matrix from left to right camera
    T = np.array(data['extrinsicStereo']['translationVectorT']) # 3x1 translation vector from left to right camera
    BASELINE = abs(T[0][0])                                     # Baseline in mm (distance between the two cameras)
    FOCAL_LENGTH = K1[0, 0]                                     # Focal length in pixels

    # load images
    imgLeft = cv2.imread(LEFT_IMAGE_PATH)
    imgRight = cv2.imread(RIGHT_IMAGE_PATH)
    if imgLeft is None or imgRight is None:
        print("Error: Could not load images. Check paths.")
        return

    imgHeight, imgWidth = imgLeft.shape[:2] # Get image dimensions

    # compute rectification transforms (alpha=0 crops to valid pixels)
    R1, R2, P1, P2, Q, roi_left, roi_right = cv2.stereoRectify(
        K1, D1, K2, D2, (imgWidth, imgHeight), R, T, alpha=0
    )

    map1_x, map1_y = cv2.initUndistortRectifyMap(K1, D1, R1, P1, (imgWidth, imgHeight), cv2.CV_32FC1)
    map2_x, map2_y = cv2.initUndistortRectifyMap(K2, D2, R2, P2, (imgWidth, imgHeight), cv2.CV_32FC1)

    rectifiedLeftImg = cv2.remap(imgLeft, map1_x, map1_y, cv2.INTER_LINEAR)
    rectifiedRightImg = cv2.remap(imgRight, map2_x, map2_y, cv2.INTER_LINEAR)

    # Configure SGBM parameters
    blockSize = 5 # block size for matching (must be odd)
    leftMatcher = cv2.StereoSGBM_create(
        minDisparity= 0,
        numDisparities= 16 * 4, # Must be divisible by 16
        blockSize=blockSize,
        P1=8 * 3 * blockSize**2,
        P2=32 * 3 * blockSize**2,
        disp12MaxDiff=1,
        uniquenessRatio=15,
        speckleWindowSize=100,
        speckleRange=2,
        mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
    )

    rightMatcher = cv2.ximgproc.createRightMatcher(leftMatcher)

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
    
    filteredDisparity = wlsFilter.filter(leftDisparity, grayImgLeft, disparity_map_right=rightDisparity) 
    actualDisparity = filteredDisparity.astype(np.float32) / 16.0

    with np.errstate(divide='ignore'):
        depthMap = (FOCAL_LENGTH * BASELINE) / actualDisparity
        depthMap[actualDisparity <= 0] = 0

    # ==========================================
    # VISUALIZATION: DEPTH MAP
    # ==========================================
    max_distance_mm = MAX_DISTANCE_CM * 10.0
    min_distance_mm = MIN_DISTANCE_CM * 10.0

    # 1. Create a mask for strictly valid pixels (greater than 0 AND less than or equal to Max Distance)
    valid_mask = (depthMap > 0) & (depthMap <= max_distance_mm)

    # 2. Clip the depth map so extreme far values don't destroy contrast
    depthMapClipped = np.clip(depthMap, min_distance_mm, max_distance_mm)

    # 3. Normalize the depth map to 0-255
    depthVis = cv2.normalize(depthMapClipped, None, alpha=0, beta=255, norm_type=cv2.NORM_MINMAX, dtype=cv2.CV_8U)
    
    # 4. Invert the image so Close = Red(255) and Far = Blue(0)
    depthVis = 255 - depthVis
    
    # 5. Apply the Colormap
    depthColor = cv2.applyColorMap(depthVis, cv2.COLORMAP_JET)
    
    # 6. Set invalid pixels AND pixels beyond MAX_DISTANCE_CM strictly to black
    depthColor[~valid_mask] = [0, 0, 0]

    # Create a color bar legend for depth visualization
    barWidth = 80
    gradient = np.linspace(255, 0, imgHeight, dtype=np.uint8)
    gradient = np.tile(gradient, (barWidth, 1)).T
    
    colorBar = cv2.applyColorMap(gradient, cv2.COLORMAP_JET)
    
    # Add labels to the color bar
    cv2.putText(colorBar, "Close", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
    cv2.putText(colorBar, f"{int(MAX_DISTANCE_CM)}cm", (10, imgHeight - 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)

    # Combine Left Image + Depth Map + Color Bar
    combined = np.hstack((rectifiedLeftImg, depthColor, colorBar))

    # Add a mouse callback to check distance in real-time
    def showDistance(event, x, y, flags, param):
        if event == cv2.EVENT_MOUSEMOVE:
            # Check if mouse is strictly inside the depth map
            if imgWidth <= x < 2 * imgWidth:
                target_x = x - imgWidth
                depth = depthMap[y, target_x] / 10.0 # Convert mm to cm
                disp = actualDisparity[y, target_x]
                
                temp_img = combined.copy()
                
                # Show Text based on new constant limits
                if depth > MAX_DISTANCE_CM:
                    cv2.putText(temp_img, f"Dist: > {MAX_DISTANCE_CM}cm", (x-100, y-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)  # Orange for out of bounds
                    cv2.putText(temp_img, f"Disp: {disp:.1f}px", (x-100, y-30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 165, 255), 2)
                elif depth > 0:
                    cv2.putText(temp_img, f"Dist: {depth:.1f}cm", (x-100, y-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                    cv2.putText(temp_img, f"Disp: {disp:.1f}px", (x-100, y-30), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
                else:
                    cv2.putText(temp_img, "Dist: Invalid", (x-100, y-10), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2) # Red for invalid/error
                    
                cv2.imshow('Pixelsense: SGBM + WLS Filter', temp_img)
            else:
                cv2.imshow('Pixelsense: SGBM + WLS Filter', combined)

    cv2.imshow('Pixelsense: SGBM + WLS Filter', combined)
    cv2.setMouseCallback('Pixelsense: SGBM + WLS Filter', showDistance)
    
    print("Hover over the depth map to see distances.")
    cv2.waitKey(0)
    cv2.destroyAllWindows()

if __name__ == '__main__':
    main()