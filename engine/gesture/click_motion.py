# engine/gesture/click_motion.py

from __future__ import annotations
import time
from dataclasses import dataclass
from typing import Optional

import mediapipe as mp

mp_hands = mp.solutions.hands


def _dist(lm, a: int, b: int) -> float:
    ax, ay = lm[a].x, lm[a].y
    bx, by = lm[b].x, lm[b].y
    dx = ax - bx
    dy = ay - by
    return (dx * dx + dy * dy) ** 0.5


# ---------------- Click (DOUBLE-TAP) ----------------

@dataclass
class ClickResult:
    label: Optional[str] = None          # "click_left" | "click_right" | None
    confidence: float = 0.0              # 0..1


class PinchClickDetector:
    """
    DOUBLE-TAP pinch detector:

      - Left click  = index-thumb DOUBLE tap
      - Right click = middle-thumb DOUBLE tap

    A "tap" = pinch goes below pinch_on then releases above pinch_off within max_tap_sec.
    A "double tap" = two taps within double_tap_gap_sec.

    cooldown_sec applies AFTER a successful double-tap click.
    """

    def __init__(
        self,
        pinch_on: float = 0.055,
        pinch_off: float = 0.064,
        max_tap_sec: float = 0.30,
        cooldown_sec: float = 0.65,
        double_tap_gap_sec: float = 0.45,   
    ):
        self.pinch_on = pinch_on
        self.pinch_off = pinch_off
        self.max_tap_sec = max_tap_sec
        self.cooldown_sec = cooldown_sec
        self.double_tap_gap_sec = double_tap_gap_sec

        # per-finger pinch state for forming a SINGLE tap
        self._idx_down = False
        self._mid_down = False
        self._idx_t0 = 0.0
        self._mid_t0 = 0.0

        # per-finger double-tap tracking
        self._idx_tap_count = 0
        self._mid_tap_count = 0
        self._idx_last_tap_time = 0.0
        self._mid_last_tap_time = 0.0

        # global cooldown after firing a click
        self._last_fire = 0.0

    def reset(self) -> None:
        self._idx_down = False
        self._mid_down = False
        self._idx_t0 = 0.0
        self._mid_t0 = 0.0
        self._idx_tap_count = 0
        self._mid_tap_count = 0
        self._idx_last_tap_time = 0.0
        self._mid_last_tap_time = 0.0

    def _register_tap(self, which: str, now: float) -> bool:
        """
        Returns True if this tap completes a DOUBLE TAP for `which` finger.
        """
        if which == "idx":
            # if too much time since last tap, restart sequence
            if (now - self._idx_last_tap_time) > self.double_tap_gap_sec:
                self._idx_tap_count = 0
            self._idx_tap_count += 1
            self._idx_last_tap_time = now
            if self._idx_tap_count >= 2:
                self._idx_tap_count = 0
                return True
            return False

        if which == "mid":
            if (now - self._mid_last_tap_time) > self.double_tap_gap_sec:
                self._mid_tap_count = 0
            self._mid_tap_count += 1
            self._mid_last_tap_time = now
            if self._mid_tap_count >= 2:
                self._mid_tap_count = 0
                return True
            return False

        return False

    def update(self, hand_landmarks) -> ClickResult:
        now = time.time()

        if hand_landmarks is None:
            self.reset()
            return ClickResult(None, 0.0)

        # global cooldown after a successful click (double-tap)
        if (now - self._last_fire) < self.cooldown_sec:
            return ClickResult(None, 0.0)

        lm = hand_landmarks.landmark

        # Distances are in normalized coords (0..1)
        d_idx = _dist(lm, 4, 8)    # thumb tip to index tip
        d_mid = _dist(lm, 4, 12)   # thumb tip to middle tip

        #  Index SINGLE tap detection 
        idx_tap_done = False
        idx_conf = 0.0

        if not self._idx_down:
            if d_idx <= self.pinch_on:
                self._idx_down = True
                self._idx_t0 = now
        else:
            # cancel if takes too long
            if (now - self._idx_t0) > self.max_tap_sec:
                self._idx_down = False
            elif d_idx >= self.pinch_off:
                # single tap completed
                self._idx_down = False
                idx_tap_done = True
                idx_conf = 1.0 - min(1.0, (d_idx / max(self.pinch_off, 1e-6)))
                idx_conf = max(0.55, idx_conf)

        #  Middle SINGLE tap detection 
        mid_tap_done = False
        mid_conf = 0.0

        if not self._mid_down:
            if d_mid <= self.pinch_on:
                self._mid_down = True
                self._mid_t0 = now
        else:
            if (now - self._mid_t0) > self.max_tap_sec:
                self._mid_down = False
            elif d_mid >= self.pinch_off:
                self._mid_down = False
                mid_tap_done = True
                mid_conf = 1.0 - min(1.0, (d_mid / max(self.pinch_off, 1e-6)))
                mid_conf = max(0.55, mid_conf)

        # ---------------- Double-tap logic ----------------
        # Priority: if both happen same frame (rare), prefer index (left click)
        if idx_tap_done:
            if self._register_tap("idx", now):
                self._last_fire = now
                # clear other tap sequences to avoid cross-trigger weirdness
                self._mid_tap_count = 0
                return ClickResult("click_left", float(min(1.0, idx_conf)))

        if mid_tap_done:
            if self._register_tap("mid", now):
                self._last_fire = now
                self._idx_tap_count = 0
                return ClickResult("click_right", float(min(1.0, mid_conf)))

        return ClickResult(None, 0.0)


#  Drag 

@dataclass
class DragResult:
    label: Optional[str] = None          
    confidence: float = 0.0
    dragging: bool = False


class PinchDragHoldDetector:
    """
    Drag/hold detector using thumb-index pinch HOLD.

    - drag_on fires once when pinch is held for hold_frames
    - dragging stays True while pinched
    - drag_off fires once when released for release_frames
    """

    def __init__(
        self,
        pinch_on: float = 0.055,
        pinch_off: float = 0.064,
        hold_frames: int = 12,
        release_frames: int = 4,
    ):
        self.pinch_on = pinch_on
        self.pinch_off = pinch_off
        self.hold_frames = hold_frames
        self.release_frames = release_frames

        self._pinched = False
        self._dragging = False
        self._hold_count = 0
        self._release_count = 0

    def reset(self):
        self._pinched = False
        self._dragging = False
        self._hold_count = 0
        self._release_count = 0

    def update(self, hand_landmarks) -> DragResult:
        if hand_landmarks is None:
            self.reset()
            return DragResult(None, 0.0, False)

        lm = hand_landmarks.landmark
        d = _dist(lm, 4, 8)  # thumb tip -> index tip

        # hysteresis for pinch state
        if not self._pinched:
            if d <= self.pinch_on:
                self._pinched = True
        else:
            if d >= self.pinch_off:
                self._pinched = False

        # Not dragging yet: count holds to start
        if not self._dragging:
            if self._pinched:
                self._hold_count += 1
                if self._hold_count >= self.hold_frames:
                    self._dragging = True
                    self._hold_count = 0
                    self._release_count = 0
                    return DragResult("drag_on", 1.0, True)
            else:
                self._hold_count = 0

            return DragResult(None, 0.0, False)

        # Dragging: watch release
        if not self._pinched:
            self._release_count += 1
            if self._release_count >= self.release_frames:
                self._dragging = False
                self._release_count = 0
                return DragResult("drag_off", 1.0, False)
        else:
            self._release_count = 0

        return DragResult(None, 0.0, self._dragging)