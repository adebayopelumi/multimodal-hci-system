# engine/gesture/custom_gesture_live.py

import time
import cv2
import mediapipe as mp
import math  # NEW

from engine.gesture.custom_gesture_classifier import classify_custom_static
from engine.gesture.motion_gesture_classifier import MotionGestureClassifier
from engine.gesture.click_motion import PinchClickDetector  

mp_hands = mp.solutions.hands


def _dist(a, b) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return (dx * dx + dy * dy) ** 0.5


def _extended_from_wrist(wrist, tip, pip, ratio: float) -> bool:
    return _dist(wrist, tip) > _dist(wrist, pip) * ratio


def index_only_mode_raw(hand_landmarks, ratio: float = 1.17) -> bool:
    """
    Index-only mode: index up, middle/ring/pinky down.
    """
    if hand_landmarks is None:
        return False

    lm = hand_landmarks.landmark
    wrist = lm[0]

    index_up = _extended_from_wrist(wrist, lm[8], lm[6], ratio)
    middle_up = _extended_from_wrist(wrist, lm[12], lm[10], ratio)
    ring_up = _extended_from_wrist(wrist, lm[16], lm[14], ratio)
    pinky_up = _extended_from_wrist(wrist, lm[20], lm[18], ratio)

    return index_up and (not middle_up) and (not ring_up) and (not pinky_up)


def two_finger_swipe_mode_raw(hand_landmarks, ratio: float = 1.17) -> bool:
    """
    Two-finger mode ONLY when exactly index + middle are extended.
    Ring and pinky must be DOWN.
    """
    if hand_landmarks is None:
        return False

    lm = hand_landmarks.landmark
    wrist = lm[0]

    index_up = _extended_from_wrist(wrist, lm[8], lm[6], ratio)
    middle_up = _extended_from_wrist(wrist, lm[12], lm[10], ratio)
    ring_up = _extended_from_wrist(wrist, lm[16], lm[14], ratio)
    pinky_up = _extended_from_wrist(wrist, lm[20], lm[18], ratio)

    return index_up and middle_up and (not ring_up) and (not pinky_up)


#  NEW: strict shape gates 

def scroll_down_hold_shape_raw(hand_landmarks, ratio: float = 1.17) -> bool:
    """
    scroll_down_hold should be ONLY:
    middle + ring + pinky UP, index DOWN.
    """
    if hand_landmarks is None:
        return False

    lm = hand_landmarks.landmark
    wrist = lm[0]

    index_up = _extended_from_wrist(wrist, lm[8], lm[6], ratio)
    middle_up = _extended_from_wrist(wrist, lm[12], lm[10], ratio)
    ring_up = _extended_from_wrist(wrist, lm[16], lm[14], ratio)
    pinky_up = _extended_from_wrist(wrist, lm[20], lm[18], ratio)

    return (not index_up) and middle_up and ring_up and pinky_up


#  NEW: index MUST be straight 

def _angle_deg(a, b, c) -> float:
    # angle ABC (b is vertex)
    bax, bay = a.x - b.x, a.y - b.y
    bcx, bcy = c.x - b.x, c.y - b.y
    dot = bax * bcx + bay * bcy
    mag1 = (bax * bax + bay * bay) ** 0.5
    mag2 = (bcx * bcx + bcy * bcy) ** 0.5
    if mag1 < 1e-9 or mag2 < 1e-9:
        return 0.0
    cosv = max(-1.0, min(1.0, dot / (mag1 * mag2)))
    return math.degrees(math.acos(cosv))


def is_index_straight(hand_landmarks, pip_thresh: float = 174.0, dip_thresh: float = 174.0) -> bool:
    """
    True only if index finger is VERY straight.
    Uses joint angles at PIP (6) and DIP (7). ~180 = straight.
    Raise thresholds to make stricter.
    """
    if hand_landmarks is None:
        return False

    lm = hand_landmarks.landmark
    mcp = lm[5]
    pip = lm[6]
    dip = lm[7]
    tip = lm[8]

    ang_pip = _angle_deg(mcp, pip, dip)
    ang_dip = _angle_deg(pip, dip, tip)

    return (ang_pip >= pip_thresh) and (ang_dip >= dip_thresh)




class ModeSmoother:
    """
    Debounce a boolean mode so it doesn't flicker.
    """
    def __init__(self, on_frames: int = 3, off_frames: int = 6):
        self.on_frames = on_frames
        self.off_frames = off_frames
        self.state = False
        self._on = 0
        self._off = 0

    def update(self, raw: bool) -> bool:
        if raw:
            self._on += 1
            self._off = 0
            if (not self.state) and self._on >= self.on_frames:
                self.state = True
        else:
            self._off += 1
            self._on = 0
            if self.state and self._off >= self.off_frames:
                self.state = False
        return self.state


def main():
    cap = cv2.VideoCapture(0)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    if not cap.isOpened():
        print("Could not open webcam.")
        return

    hands = mp_hands.Hands(
        static_image_mode=False,
        max_num_hands=1,
        min_detection_confidence=0.6,
        min_tracking_confidence=0.6,
    )

    motion = MotionGestureClassifier(
        window_sec=0.7,
        min_frames=10,
        min_move=0.22,
        dominance=1.4,
        cooldown_sec=0.6,
    )

    # clicks (tap)
    clicker = PinchClickDetector(
        pinch_on=0.055,
        pinch_off=0.064,
        max_tap_sec=0.30,
        cooldown_sec=0.65,
    )

    print("Custom gesture live test. Press 'q' or ESC to quit.")

    #  static gesture smoothing 
    confirm_frames = 6
    release_frames = 8
    cooldown_sec = 0.15

    confirmed_label = "none"
    confirmed_score = 0.0
    candidate_label = "none"
    candidate_count = 0
    frames_since_confirmed_seen = 0
    last_confirm_time = 0.0

    #  mode smoothing 
    two_mode_smooth = ModeSmoother(on_frames=3, off_frames=6)
    idx_mode_smooth = ModeSmoother(on_frames=3, off_frames=6)
    two_mode = False
    idx_mode = False

    #  motion display persistence 
    motion_label = "none"
    motion_score = 0.0
    last_motion_label = "none"
    last_motion_time = 0.0
    motion_display_sec = 0.5

    #  click display persistence 
    click_label = "none"
    click_score = 0.0
    last_click_label = "none"
    last_click_time = 0.0
    click_display_sec = 0.35

    #  screenshot display-only 
    screenshot_hold_frames = 16
    screenshot_count = 0
    screenshot_cooldown_sec = 1.5
    last_screenshot_time = 0.0

    #  capture display-only 
    capture_hold_frames = 12
    capture_count = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        hand_landmarks = None
        raw_label = "none"
        raw_score = 0.0

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]

            label, score = classify_custom_static(hand_landmarks)
            raw_label = label if label is not None else "none"
            raw_score = float(score)
            # STRICT gate: move_cursor ONLY when confidence is perfect
            if raw_label == "move_cursor" and raw_score < 0.996:
                raw_label = "none"
                raw_score = 0.0
            if raw_label == "screenshot" and raw_score < 0.996:
                raw_label = "none"
                raw_score = 0.0

            mp.solutions.drawing_utils.draw_landmarks(
                frame,
                hand_landmarks,
                mp_hands.HAND_CONNECTIONS,
            )

        #  enforce strict shapes BEFORE smoothing 
        if raw_label == "scroll_down_hold":
            if not scroll_down_hold_shape_raw(hand_landmarks, ratio=1.17):
                raw_label = "none"
                raw_score = 0.0

        now = time.time()

        #  Static label smoothing 
        in_cooldown = (now - last_confirm_time) < cooldown_sec

        if in_cooldown:
            if raw_label == confirmed_label and confirmed_label != "none":
                frames_since_confirmed_seen = 0
                confirmed_score = raw_score
            else:
                frames_since_confirmed_seen += 1
        else:
            if raw_label == candidate_label:
                candidate_count += 1
            else:
                candidate_label = raw_label
                candidate_count = 1

            if candidate_label != "none" and candidate_count >= confirm_frames:
                confirmed_label = candidate_label
                confirmed_score = raw_score
                frames_since_confirmed_seen = 0
                last_confirm_time = now

            if confirmed_label != "none":
                if raw_label == confirmed_label:
                    frames_since_confirmed_seen = 0
                    confirmed_score = raw_score
                else:
                    frames_since_confirmed_seen += 1
                    if frames_since_confirmed_seen >= release_frames:
                        confirmed_label = "none"
                        confirmed_score = 0.0
                        candidate_label = "none"
                        candidate_count = 0

        display_label = confirmed_label
        display_score = confirmed_score if confirmed_label != "none" else 0.0
\
        #  Directional swipe modes 
        raw_two = two_finger_swipe_mode_raw(hand_landmarks, ratio=1.17)
        two_mode = two_mode_smooth.update(raw_two)

        # ONLY CHANGE: index-only mode now also requires a VERY straight index finger
        raw_idx = (
            (not two_mode)
            and index_only_mode_raw(hand_landmarks, ratio=1.17)
            and is_index_straight(hand_landmarks, pip_thresh=174.0, dip_thresh=174.0)
        )
        idx_mode = idx_mode_smooth.update(raw_idx)

        #  Motion gestures (direction-filtered) 
        allowed = None
        if two_mode:
            allowed = {"swipe_right", "swipe_down"}
        elif idx_mode:
            allowed = {"swipe_left", "swipe_up"}

        if allowed is not None:
            m = motion.update(hand_landmarks)
            if m.label and (m.label in allowed):
                last_motion_label = m.label
                last_motion_time = now
                motion_score = float(m.confidence)

        if (now - last_motion_time) <= motion_display_sec:
            motion_label = last_motion_label
        else:
            motion_label = "none"
            motion_score = 0.0
        

        #  Click tap detection 
        c = clicker.update(hand_landmarks)
        if c.label:
            last_click_label = c.label
            last_click_time = now
            click_score = float(c.confidence)

        if (now - last_click_time) <= click_display_sec:
            click_label = last_click_label
        else:
            click_label = "none"
            click_score = 0.0

        #  Screenshot display-only 
        if display_label == "screenshot":
            screenshot_count += 1
        else:
            screenshot_count = 0

        if (
            screenshot_count >= screenshot_hold_frames
            and (now - last_screenshot_time) >= screenshot_cooldown_sec
        ):
            last_screenshot_time = now
            screenshot_count = 0

        #  Capture display-only 
        if display_label == "capture":
            capture_count = min(capture_hold_frames, capture_count + 1)
        else:
            capture_count = 0

        #  UI overlay 
        cv2.putText(frame, f"Custom: {display_label} ({display_score:.2f})",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        mode_txt = "OFF"
        if two_mode:
            mode_txt = "TWO-FINGER (Right/Down)"
        elif idx_mode:
            mode_txt = "INDEX-ONLY (Left/Up)"

        cv2.putText(frame, f"SwipeMode: {mode_txt}",
                    (10, 70), cv2.FONT_HERSHEY_SIMPLEX, 0.95, (0, 255, 0), 2)

        cv2.putText(frame, f"Motion: {motion_label} ({motion_score:.2f})",
                    (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.putText(frame, f"Click: {click_label} ({click_score:.2f})",
                    (10, 150), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        if display_label == "screenshot":
            cv2.putText(frame, f"Screenshot HOLD: {screenshot_count}/{screenshot_hold_frames}",
                        (10, 230), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        if display_label == "capture":
            cv2.putText(frame, f"Capture HOLD: {capture_count}/{capture_hold_frames}",
                        (10, 270), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)

        cv2.imshow("Custom Gesture Live", frame)

        key = cv2.waitKey(1) & 0xFF
        if key == ord("q") or key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    hands.close()


if __name__ == "__main__":
    main()