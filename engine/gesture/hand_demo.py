# engine/gesture/hand_demo.py

import cv2
import mediapipe as mp

from engine.gesture.gesture_classifier import classify_static_gesture

mp_hands = mp.solutions.hands
mp_drawing = mp.solutions.drawing_utils


def run_hand_demo():
    cap = cv2.VideoCapture(0)  

    if not cap.isOpened():
        print("Could not open webcam.")
        return

    with mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
    ) as hands:

        while True:
            ret, frame = cap.read()
            if not ret:
                print("Failed to read from camera.")
                break

            h, w, _ = frame.shape

            # Convert BGR (OpenCV) to RGB (MediaPipe)
            image = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            image.flags.writeable = False
            results = hands.process(image)

            # Back to BGR for display and drawing
            image.flags.writeable = True
            frame = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)

            gesture_label = None

            if results.multi_hand_landmarks:
                for hand_landmarks in results.multi_hand_landmarks:
                    # Draw landmarks
                    mp_drawing.draw_landmarks(
                        frame,
                        hand_landmarks,
                        mp_hands.HAND_CONNECTIONS,
                    )

                    # Classify static gesture
                    gesture_label = classify_static_gesture(hand_landmarks, w, h)

            # Show predicted label
            if gesture_label is not None:
                cv2.putText(
                    frame,
                    f"Gesture: {gesture_label}",
                    (10, 40),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (0, 255, 0),
                    2,
                    cv2.LINE_AA,
                )

            cv2.imshow("Hand Demo", frame)

            # Press 'q' to quit
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run_hand_demo()