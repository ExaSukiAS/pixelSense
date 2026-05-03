import cv2
import numpy as np
import glob
import os
import json
from termcolor import colored

LEFT_DIR = '../camCalibImages/left'
RIGHT_DIR = '../camCalibImages/right'
IMAGE_EXTENSION = '*.jpg' 

CHESSBOARD_SIZE = (6, 4) # IMPORTANT: if taking images with portrait orientation, use (lower, higher), and if landscape, use (higher, lower) to match the actual pattern in the images
SQUARE_SIZE = 39.0  # Size of a square in mm
WAIT_TIME = 300 

def stereo_calibrate():
    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)

    # prepare object points in mm
    objp = np.zeros((CHESSBOARD_SIZE[0] * CHESSBOARD_SIZE[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:CHESSBOARD_SIZE[0], 0:CHESSBOARD_SIZE[1]].T.reshape(-1, 2)
    objp *= SQUARE_SIZE

    objpoints = []
    imgpoints_left = []
    imgpoints_right = []
    
    # NEW: List to keep track of the exact file paths for pairs that are actually used
    successful_paths = []

    leftImages = sorted(glob.glob(os.path.join(LEFT_DIR, IMAGE_EXTENSION)))
    rightImages = sorted(glob.glob(os.path.join(RIGHT_DIR, IMAGE_EXTENSION)))

    print(f"Found {len(leftImages)} image pairs. Starting detection...")
    
    img_shape = None

    for left_path, right_path in zip(leftImages, rightImages):
        img_l = cv2.imread(left_path)
        img_r = cv2.imread(right_path)

        # Convert to grayscale for corner detection
        gray_l = cv2.cvtColor(img_l, cv2.COLOR_BGR2GRAY)
        gray_r = cv2.cvtColor(img_r, cv2.COLOR_BGR2GRAY)
        
        if img_shape is None:
            img_shape = gray_l.shape[::-1]

        # Find chessboard corners
        ret_l, corners_l = cv2.findChessboardCorners(gray_l, CHESSBOARD_SIZE, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)
        ret_r, corners_r = cv2.findChessboardCorners(gray_r, CHESSBOARD_SIZE, cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_FAST_CHECK + cv2.CALIB_CB_NORMALIZE_IMAGE)

        if ret_l and ret_r:
            objpoints.append(objp)
            imgpoints_left.append(cv2.cornerSubPix(gray_l, corners_l, (11, 11), (-1, -1), criteria))
            imgpoints_right.append(cv2.cornerSubPix(gray_r, corners_r, (11, 11), (-1, -1), criteria))
            
            # Track the paths so we can identify bad images later
            successful_paths.append((left_path, right_path))

            # Display progress
            draw_l = cv2.drawChessboardCorners(img_l.copy(), CHESSBOARD_SIZE, corners_l, ret_l)
            draw_r = cv2.drawChessboardCorners(img_r.copy(), CHESSBOARD_SIZE, corners_r, ret_r)
            cv2.imshow('Left', cv2.resize(draw_l, (640, 480)))
            cv2.imshow('Right', cv2.resize(draw_r, (640, 480)))
            cv2.waitKey(WAIT_TIME)
        else:
            print(f"Chessboard not detected in: {os.path.basename(left_path)}, dropping this pair.")

    cv2.destroyAllWindows()

    print("\nCalibrating individual cameras...")

    #Extract rvecs and tvecs (rotation/translation vectors) needed for error calculation
    _, mtx_l, dist_l, rvecs_l, tvecs_l = cv2.calibrateCamera(objpoints, imgpoints_left, img_shape, None, None)
    _, mtx_r, dist_r, rvecs_r, tvecs_r = cv2.calibrateCamera(objpoints, imgpoints_right, img_shape, None, None)

    # Calculate per-image reprojection error to find bad pairs
    print("Evaluating individual image pair errors...")
    pair_errors = []
    
    for i in range(len(objpoints)):
        # Calculate Reprojection Error for Left Camera
        imgpoints2_l, _ = cv2.projectPoints(objpoints[i], rvecs_l[i], tvecs_l[i], mtx_l, dist_l)
        l2_norm_l = cv2.norm(imgpoints_left[i], imgpoints2_l, cv2.NORM_L2)
        error_l = l2_norm_l / np.sqrt(len(imgpoints2_l))

        # Calculate Reprojection Error for Right Camera
        imgpoints2_r, _ = cv2.projectPoints(objpoints[i], rvecs_r[i], tvecs_r[i], mtx_r, dist_r)
        l2_norm_r = cv2.norm(imgpoints_right[i], imgpoints2_r, cv2.NORM_L2)
        error_r = l2_norm_r / np.sqrt(len(imgpoints2_r))
        
        avg_error = (error_l + error_r) / 2.0 # Average the error of the left and right camera for sorting purposes
        
        pair_errors.append((avg_error, error_l, error_r, successful_paths[i][0], successful_paths[i][1])) # Store the errors and their corresponding file paths

    pair_errors.sort(key=lambda x: x[0], reverse=True) # Sort the list based on the highest average error (index 0 of the tuple)

    print(colored("\n--- WORST OFFENDING IMAGE PAIRS ---", "yellow"))
    print("Consider removing these pairs from your dataset and recalibrating.\n")
    
    # Print the top 10 worst images
    limit = min(10, len(pair_errors))
    for i in range(limit):
        avg_err, err_l, err_r, path_l, path_r = pair_errors[i]
        print(colored(f"#{i+1} | Average Error: {avg_err:.4f} pixels", "red" if avg_err > 0.5 else "yellow"))
        print(f"     Left Error:  {err_l:.4f}  -> {path_l}")
        print(f"     Right Error: {err_r:.4f}  -> {path_r}\n")

    # Stereo Calibration with initial intrinsic estimates and no fixed parameters
    print("\nRunning Stereo Calibration...")
    flags = (cv2.CALIB_RATIONAL_MODEL+cv2.CALIB_USE_INTRINSIC_GUESS)
    ret_stereo, cameraMatrixL, distCoeffsL, cameraMatrixR, distCoeffsR, R, T, E, F = cv2.stereoCalibrate(
        objpoints, imgpoints_left, imgpoints_right, 
        mtx_l, dist_l, mtx_r, dist_r, 
        img_shape, criteria=(cv2.TERM_CRITERIA_MAX_ITER + cv2.TERM_CRITERIA_EPS, 100, 1e-5), 
        flags=flags
    )

    print(colored(f"\nFinal Stereo Reprojection Error (RMS): {ret_stereo:.4f} pixels", 'green' if ret_stereo < 0.5 else 'red'))

    calibration_data = {
        "summary": {
            "rmsReprojectionError": float(ret_stereo),
            "units": "mm",
            "chessboard_size": CHESSBOARD_SIZE,
            "squareSize": SQUARE_SIZE
        },
        "intrinsicLeft": {
            "cameraMatrix": cameraMatrixL.tolist(),
            "distCoeffs": distCoeffsL.tolist()
        },
        "intrinsicRight": {
            "cameraMatrix": cameraMatrixR.tolist(),
            "distCoeffs": distCoeffsR.tolist()
        },
        "extrinsicStereo": {
            "rotationMatrixR": R.tolist(),
            "translationVectorT": T.tolist(),
            "essentialMatrixE": E.tolist(),
            "fundamentalMatrixF": F.tolist()
        }
    }

    # Write to a file
    output_filename = "../stereoCalibParams.json"
    with open(output_filename, "w") as f:
        json.dump(calibration_data, f, indent=4)
    
    print(f"\nSuccess! Data saved to {output_filename}")

if __name__ == '__main__':
    stereo_calibrate()