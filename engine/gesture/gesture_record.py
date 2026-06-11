# engine/gesture/gesture_record.py

import cv2
import mediapipe as mp

from engine.gesture.custom_gestures import (
    landmarks_to_vector,
    add_gesture_sample,
)

mp_hands = mp.solutions.hands


def main():
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("Could not open webcam.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )

    print("Custom gesture recorder")
    print("Press 'r' to record current hand pose as a sample.")
    print("Press 'q' or ESC to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        # Flip horizontally for natural webcam feel
        frame = cv2.flip(frame, 1)

        # Mediapipe expects RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        # Draw landmarks 
        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
            )
        else:
            hand_landmarks = None

        cv2.putText(
            frame,
            "Press 'r' to record gesture, 'q' to quit",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 255, 0),
            2,
        )

        cv2.imshow("Gesture Recorder", frame)

        key = cv2.waitKey(1) & 0xFF

        # Quit
        if key == ord("q") or key == 27:
            break

        # Record sample
        if key == ord("r"):
            if hand_landmarks is None:
                print("[Recorder] No hand detected, cannot record sample.")
            else:
                # Convert to normalized vector
                vec = landmarks_to_vector(hand_landmarks)
                print("[Recorder] Captured gesture. Enter label name in terminal:")
                label = input("Label for this gesture sample: ").strip()
                if label:
                    add_gesture_sample(label, vec)
                else:
                    print("[Recorder] Empty label, sample discarded.")

    cap.release()
    cv2.destroyAllWindows()
    hands.close()


if __name__ == "__main__":
    main()