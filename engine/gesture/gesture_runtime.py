# engine/gesture/gesture_runtime.py

import json
import time
import warnings
import cv2
import mediapipe as mp
import os
import argparse

from engine.dispatcher.actions import dispatch
from engine.gesture.custom_gesture_classifier import classify_custom_static
from engine.gesture.motion_gesture_classifier import MotionGestureClassifier
from engine.gesture.click_motion import PinchClickDetector  

mp_hands = mp.solutions.hands

warnings.filterwarnings(
    "ignore",
    message=".*SymbolDatabase\\.GetPrototype\\(\\) is deprecated.*",
    category=UserWarning,
)

def _headless_enabled() -> bool:
    """
    HEADLESS=1 disables any cv2.imshow / window usage.
    You can also pass --headless when running directly.
    """
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--headless", action="store_true")
    args, _ = parser.parse_known_args()

    env_flag = os.environ.get("HEADLESS", "").strip().lower() in {"1", "true", "yes", "on"}
    return env_flag or bool(args.headless)

#  Small helpers 

def _dist(a, b) -> float:
    dx = a.x - b.x
    dy = a.y - b.y
    return (dx * dx + dy * dy) ** 0.5


def _extended_from_wrist(wrist, tip, pip, ratio: float) -> bool:
    return _dist(wrist, tip) > (_dist(wrist, pip) * ratio)


def _clamp01(v: float) -> float:
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _clamp_int(v: int, lo: int, hi: int) -> int:
    if v < lo:
        return lo
    if v > hi:
        return hi
    return v


def _fire(label: str, intent: str, score: float | None = None):
    """Run a gesture's action and tell the app's Dashboard which gesture it was."""
    print(json.dumps({"type": "GESTURE", "label": label, "intent": intent, "confidence": score}), flush=True)
    dispatch(intent, params={})


def _get_screen_size() -> tuple[int, int]:
    """
    Best-effort screen size for mapping normalized MediaPipe coords -> pixels.
    """
    # Quartz (preferred if available)
    try:
        import Quartz  # type: ignore
        w = int(Quartz.CGDisplayPixelsWide(Quartz.CGMainDisplayID()))
        h = int(Quartz.CGDisplayPixelsHigh(Quartz.CGMainDisplayID()))
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass

    # pyautogui (fallback)
    try:
        import pyautogui  # type: ignore
        w, h = pyautogui.size()
        w = int(w); h = int(h)
        if w > 0 and h > 0:
            return w, h
    except Exception:
        pass

    # fallback
    return 1920, 1080


def finger_states(hand_landmarks, ratio: float = 1.17):
    """
    Returns tuple of booleans: (index_up, middle_up, ring_up, pinky_up)
    Based on wrist->tip vs wrist->pip distances.
    """
    if hand_landmarks is None:
        return (False, False, False, False)

    lm = hand_landmarks.landmark
    wrist = lm[0]

    index_up = _extended_from_wrist(wrist, lm[8], lm[6], ratio)
    middle_up = _extended_from_wrist(wrist, lm[12], lm[10], ratio)
    ring_up = _extended_from_wrist(wrist, lm[16], lm[14], ratio)
    pinky_up = _extended_from_wrist(wrist, lm[20], lm[18], ratio)

    return (index_up, middle_up, ring_up, pinky_up)


def index_only_mode_raw(hand_landmarks, ratio: float = 1.17) -> bool:
    """
    Index-only mode: index UP, middle/ring/pinky DOWN.
    """
    idx, mid, ring, pinky = finger_states(hand_landmarks, ratio)
    return idx and (not mid) and (not ring) and (not pinky)


def two_finger_mode_raw(hand_landmarks, ratio: float = 1.17) -> bool:
    """
    Two-finger mode: index+middle UP, ring+pinky DOWN.
    """
    idx, mid, ring, pinky = finger_states(hand_landmarks, ratio)
    return idx and mid and (not ring) and (not pinky)


def scroll_down_hold_shape_raw(hand_landmarks, ratio: float = 1.17) -> bool:
    """
    EXACT scroll_down_hold shape:
    middle+ring+pinky UP, index DOWN
    (prevents 4-finger activation when index is also up)
    """
    idx, mid, ring, pinky = finger_states(hand_landmarks, ratio)
    return (not idx) and mid and ring and pinky


class DebounceBool:
    def __init__(self, on_frames=3, off_frames=6):
        self.on_frames = on_frames
        self.off_frames = off_frames
        self.state = False
        self.on_count = 0
        self.off_count = 0

    def update(self, raw: bool) -> bool:
        if raw:
            self.on_count += 1
            self.off_count = 0
            if not self.state and self.on_count >= self.on_frames:
                self.state = True
        else:
            self.off_count += 1
            self.on_count = 0
            if self.state and self.off_count >= self.off_frames:
                self.state = False
        return self.state


class HoldTrigger:
    """
    Triggers once when label is held for N frames, then cools down.
    """
    def __init__(self, label: str, hold_frames: int, cooldown_sec: float):
        self.label = label
        self.hold_frames = hold_frames
        self.cooldown_sec = cooldown_sec
        self._count = 0
        self._last_fire = 0.0

    def update(self, current_label: str, now: float) -> bool:
        if current_label == self.label:
            self._count += 1
        else:
            self._count = 0

        if self._count >= self.hold_frames and (now - self._last_fire) >= self.cooldown_sec:
            self._last_fire = now
            self._count = 0
            return True
        return False


class RateLimiter:
    """
    Allows repeated actions (like scroll) at a controlled rate.
    """
    def __init__(self, every_sec: float):
        self.every_sec = every_sec
        self._last = 0.0

    def ready(self, now: float) -> bool:
        if (now - self._last) >= self.every_sec:
            self._last = now
            return True
        return False


class EdgeCooldownTrigger:
    """
    Fires ONLY on a rising-edge (none -> label) and enforces a cooldown
    so one gesture event can't spam dispatch across frames.
    """
    def __init__(self, cooldown_sec: float = 0.35):
        self.cooldown_sec = cooldown_sec
        self._last_fire = 0.0
        self._prev_label = "none"

    def should_fire(self, label: str, now: float) -> bool:
        rising = (self._prev_label == "none") and (label != "none")
        self._prev_label = label

        if not rising:
            return False
        if (now - self._last_fire) < self.cooldown_sec:
            return False

        self._last_fire = now
        return True


#  Main runtime 

def main():

    headless = _headless_enabled()
    if headless:
        print("[Gesture] HEADLESS mode ON: no cv2.imshow window will be created.")
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
        min_frames=8,
        min_move=0.18,
        dominance=1.4,
        cooldown_sec=0.6,
    )

    clicker = PinchClickDetector(
        pinch_on=0.055,
        pinch_off=0.064,
        max_tap_sec=0.30,
        cooldown_sec=0.65,
    )

    # smooth the two “modes”
    index_mode_smoother = DebounceBool(on_frames=3, off_frames=6)
    two_finger_mode_smoother = DebounceBool(on_frames=3, off_frames=6)

    # One-shot holds
    screenshot_trigger = HoldTrigger(label="screenshot", hold_frames=16, cooldown_sec=1.5)
    capture_trigger = HoldTrigger(label="capture", hold_frames=16, cooldown_sec=1.2)

    # Continuous holds (rate limited)
    scroll_up_limiter = RateLimiter(every_sec=0.8)
    scroll_down_limiter = RateLimiter(every_sec=0.8)

    # stop repeated swipe dispatch spam
    motion_fire = EdgeCooldownTrigger(cooldown_sec=0.45)

    # cursor mapping + smoothing
    screen_w, screen_h = _get_screen_size()
    ema_x = None
    ema_y = None

    #  ONLY CHANGES: cursor calibration/sensitivity/smoothing ---
    ROI_SCALE = 1.70         # >1.0 expands reach so you can hit edges easier
    GAIN = 1.35              # >1.0 increases sensitivity (bigger motion on screen)
    Y_OFFSET_NORM = 0.14     # move cursor ABOVE hand (normalized units). increase to move higher.
    ALPHA_SLOW = 0.06        # smoothing when almost still (less jitter)
    ALPHA_FAST = 0.75        # responsiveness when moving (less lag)
    SPEED_LOW = 4.0          # px/frame threshold for "slow"
    SPEED_HIGH = 20.0        # px/frame threshold for "fast"

    print("Gesture Runtime (mapping enabled). Press 'q' to quit.")

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = hands.process(rgb)

        hand_landmarks = None
        static_label = "none"
        static_score = 0.0

        if results.multi_hand_landmarks:
            hand_landmarks = results.multi_hand_landmarks[0]
            lbl, score = classify_custom_static(hand_landmarks)
            static_label = lbl if lbl is not None else "none"
            static_score = float(score)

            # STRICT gate: move_cursor ONLY when confidence is perfect
            if static_label == "move_cursor" and static_score < 0.996:
                static_label = "none"
                static_score = 0.0

            # STRICT gate: screenshot ONLY when confidence is perfect
            if static_label == "screenshot" and static_score < 0.996:
                static_label = "none"
                static_score = 0.0

        now = time.time()

        #  MODE GATING 
        index_mode = index_mode_smoother.update(index_only_mode_raw(hand_landmarks, ratio=1.17))
        two_finger_mode = two_finger_mode_smoother.update(two_finger_mode_raw(hand_landmarks, ratio=1.17))

        if two_finger_mode:
            index_mode = False

        #  enforce STRICT static shapes 
        # (2) scroll_down_hold must be EXACT (index must be down)
        if static_label == "scroll_down_hold":
            if not scroll_down_hold_shape_raw(hand_landmarks, ratio=1.17):
                static_label = "none"

        #  Motion swipes with direction allow-list 
        motion_label = "none"
        allowed = set()

        if index_mode:
            allowed = {"swipe_left", "swipe_up"}
        elif two_finger_mode:
            allowed = {"swipe_right", "swipe_down"}

        if allowed:
            m = motion.update(hand_landmarks)
            if m.label and (m.label in allowed):
                motion_label = m.label

        # --------- click detection ---------
        click_label = "none"
        c = clicker.update(hand_landmarks)
        if c.label:
            click_label = c.label

        #  INTENT MAPPING 

        # 1) Motion swipes -> fire ONCE per swipe event 
        if motion_fire.should_fire(motion_label, now):
            if motion_label == "swipe_right":
                _fire("Swipe right", "next_action")
            elif motion_label == "swipe_left":
                _fire("Swipe left", "previous_action")
            elif motion_label == "swipe_up":
                _fire("Swipe up", "scroll_up")
            elif motion_label == "swipe_down":
                _fire("Swipe down", "scroll_down")

        # 2) Continuous scroll holds
        if static_label == "scroll_up_hold" and scroll_up_limiter.ready(now):
            _fire("Scroll up", "scroll_up", static_score)
        if static_label == "scroll_down_hold" and scroll_down_limiter.ready(now):
            _fire("Scroll down", "scroll_down", static_score)

        # 3) Screenshot
        if screenshot_trigger.update(static_label, now):
            _fire("Screenshot", "capture_screen", static_score)

        # 5) Clicks
        if click_label == "click_left":
            _fire("Left click", "mouse_left_click")
        elif click_label == "click_right":
            _fire("Right click", "mouse_right_click")

        # 7) Cursor movement
        if static_label == "move_cursor" and hand_landmarks is not None:
            lm = hand_landmarks.landmark

            nx = _clamp01(lm[8].x)
            ny = _clamp01(lm[8].y)

            nx = _clamp01((nx - 0.5) * ROI_SCALE + 0.5)
            ny = _clamp01((ny - 0.5) * ROI_SCALE + 0.5)

            ny = _clamp01(ny - Y_OFFSET_NORM)

            x = int(nx * (screen_w - 1))
            y = int(ny * (screen_h - 1))

            cx = (screen_w - 1) * 0.5
            cy = (screen_h - 1) * 0.5
            x = int(cx + (x - cx) * GAIN)
            y = int(cy + (y - cy) * GAIN)

            x = _clamp_int(x, 0, screen_w - 1)
            y = _clamp_int(y, 0, screen_h - 1)

            if ema_x is None:
                ema_x, ema_y = float(x), float(y)
                alpha = ALPHA_FAST
            else:
                dx = float(x) - float(ema_x)
                dy = float(y) - float(ema_y)
                speed = (dx * dx + dy * dy) ** 0.5

                if speed <= SPEED_LOW:
                    alpha = ALPHA_SLOW
                elif speed >= SPEED_HIGH:
                    alpha = ALPHA_FAST
                else:
                    t = (speed - SPEED_LOW) / (SPEED_HIGH - SPEED_LOW)
                    alpha = (1.0 - t) * ALPHA_SLOW + t * ALPHA_FAST

            ema_x = (1.0 - alpha) * ema_x + alpha * float(x)
            ema_y = (1.0 - alpha) * ema_y + alpha * float(y)

            dispatch("mouse_move", params={"x": int(ema_x), "y": int(ema_y)})

        

        cv2.putText(frame, f"Static: {static_label} ({static_score:.2f})", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        mode_text = "INDEX" if index_mode else ("TWO-FINGER" if two_finger_mode else "OFF")
        cv2.putText(frame, f"SwipeMode: {mode_text}", (10, 70),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.putText(frame, f"Motion: {motion_label}", (10, 110),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)

        cv2.putText(frame, f"Click: {click_label}", (10, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 255, 0), 2)


        if not headless:
            cv2.imshow("Gesture Runtime", frame)
            key = cv2.waitKey(1) & 0xFF
            if key == ord("q") or key == 27:
                break
        else:
            # no GUI window; still allow clean exit if process is killed
            # small sleep to avoid maxing CPU
            time.sleep(0.001)

    cap.release()
    if not headless:
        cv2.destroyAllWindows()
    hands.close()

if __name__ == "__main__":
    main()