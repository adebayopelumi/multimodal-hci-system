# engine/gesture/gesture_control.py

import cv2
import mediapipe as mp
from collections import deque, Counter

from engine.gesture.gesture_classifier import classify_static_gesture
from engine.dispatcher.mac_actions import dispatch

mp_hands = mp.solutions.hands

#  Smoothing + debounce parameters 
HISTORY_LEN = 8          # how many recent frame labels we remember
STABLE_FRAMES = 5        # minimum times a label must appear in history
COOLDOWN_FRAMES = 15     # frames to wait before allowing same gesture again

# Map gesture labels -> intents
GESTURE_TO_INTENT = {
    "open_palm": None,        
    "fist": "pause_media",    
    "point": "next_action",   
    
}


def main():
    cap = cv2.VideoCapture(0)
    # Ask for high resolution (your camera will clamp if it can’t reach this)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    if not cap.isOpened():
        print("Could not open webcam.")
        return

    # Mediapipe Hands
    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )

    label_history = deque(maxlen=HISTORY_LEN)
    stable_label = None
    frames_stable = 0

    last_trigger_label = None
    cooldown_counter = COOLDOWN_FRAMES  # start "ready"

    # 👇 NEW: last gesture we *display* on screen (never shows "none")
    last_display_label = "none"

    print("Gesture control running. Press 'q' or ESC to quit.")

    frame_index = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_index += 1

        # Flip horizontally for natural webcam feel
        frame = cv2.flip(frame, 1)
        h, w, _ = frame.shape

        # Mediapipe expects RGB
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        current_label = None

        if results.multi_hand_landmarks:
            # Use first detected hand
            hand_landmarks = results.multi_hand_landmarks[0]

            # Classify gesture
            current_label = classify_static_gesture(hand_landmarks, w, h)

            # Draw landmarks for visualization
            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
            )

        # Update label history
        label_history.append(current_label or "none")

        #  Majority vote smoothing 
        most_common, count = Counter(label_history).most_common(1)[0]

        if most_common != "none" and count >= STABLE_FRAMES:
            # We have a stable gesture
            if most_common != stable_label:
                # Gesture changed
                stable_label = most_common
                frames_stable = 1
            else:
                frames_stable += 1
        else:
            # No stable gesture right now (for logic)
            stable_label = None
            frames_stable = 0

        #  Cooldown & triggering logic 
        if cooldown_counter < COOLDOWN_FRAMES:
            cooldown_counter += 1

        if stable_label:
            # 👇 NEW: update what we show on screen ONLY when we have a gesture
            last_display_label = stable_label

            intent = GESTURE_TO_INTENT.get(stable_label)

            if intent is not None:
                # Only trigger when:
                #  - new gesture OR
                #  - cooldown finished
                if (stable_label != last_trigger_label) or (
                    cooldown_counter >= COOLDOWN_FRAMES
                ):
                    print(
                        f"[Gesture] Triggering '{stable_label}' "
                        f"-> intent '{intent}'"
                    )
                    dispatch(intent, text=None, params={})
                    last_trigger_label = stable_label
                    cooldown_counter = 0

        #  Overlay text 
        # We NEVER show "none" — we just keep the last known gesture name.
        cv2.putText(
            frame,
            f"Gesture: {last_display_label}",
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1.0,
            (0, 255, 0),
            2,
        )

        cv2.imshow("Gesture Control", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    hands.close()


if __name__ == "__main__":
    main()