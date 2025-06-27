import cv2
import mediapipe as mp

def main():
    # Capture video from your webcam
    cap = cv2.VideoCapture(0)

    # Initialize hand tracking module from Mediapipe
    mpHands = mp.solutions.hands
    hands = mpHands.Hands()
    mpDraw = mp.solutions.drawing_utils

    while True:
        success, img = cap.read()
        if not success:
            print("Failed to capture image from camera.")
            break

        # Convert the image to RGB
        imgRGB = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Process the image to find hands
        results = hands.process(imgRGB)

        # Check if hands are detected
        if results.multi_hand_landmarks:
            for hand_landmarks in results.multi_hand_landmarks:
                # Draw landmarks on the hand
                mpDraw.draw_landmarks(img, hand_landmarks, mpHands.HAND_CONNECTIONS)

        # Display the image with landmarks
        cv2.imshow("Hand Tracking", img)

        # Exit the loop when 'q' is pressed
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
