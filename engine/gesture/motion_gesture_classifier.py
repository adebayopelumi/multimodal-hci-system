# engine/gesture/motion_gesture_classifier.py

from __future__ import annotations
from dataclasses import dataclass
from collections import deque
from typing import Deque, Optional, Tuple
import time
import numpy as np

# Mediapipe landmark indices:
# 0 = wrist

@dataclass
class MotionResult:
    label: Optional[str]   # "swipe_left", "swipe_right", "swipe_up", "swipe_down", or None
    confidence: float      # 0..1


class MotionGestureClassifier:
    """
    Rule-based dynamic gesture detector using wrist trajectory over a rolling window.
    - Feed it each frame's hand_landmarks (or None).
    - Call update(...) -> MotionResult
    """

    def __init__(
        self,
        window_sec: float = 0.7,
        min_frames: int = 10,
        min_move: float = 0.18,      # normalized movement threshold (tune)
        dominance: float = 1.4,      # axis dominance ratio (tune)
        cooldown_sec: float = 0.6,   # prevent double triggers
    ):
        self.window_sec = window_sec
        self.min_frames = min_frames
        self.min_move = min_move
        self.dominance = dominance
        self.cooldown_sec = cooldown_sec

        self.points: Deque[Tuple[float, float, float]] = deque() 
        self.last_fire_time = 0.0

    def reset(self):
        self.points.clear()

    def _prune(self, now: float):
        while self.points and (now - self.points[0][0]) > self.window_sec:
            self.points.popleft()

    def update(self, hand_landmarks) -> MotionResult:
        now = time.time()

        # If no hand, decay/reset trajectory
        if hand_landmarks is None:
            self._prune(now)
            return MotionResult(None, 0.0)

        # Wrist normalized coords from MediaPipe (0..1-ish)
        wrist = hand_landmarks.landmark[0]
        x, y = float(wrist.x), float(wrist.y)

        self.points.append((now, x, y))
        self._prune(now)

        # Cooldown
        if (now - self.last_fire_time) < self.cooldown_sec:
            return MotionResult(None, 0.0)

        if len(self.points) < self.min_frames:
            return MotionResult(None, 0.0)

        # Compute movement from oldest to newest in window
        t0, x0, y0 = self.points[0]
        t1, x1, y1 = self.points[-1]

        dx = x1 - x0
        dy = y1 - y0

        adx = abs(dx)
        ady = abs(dy)

        # Decide direction
        label = None
        conf = 0.0

        if adx > self.min_move and adx > (ady * self.dominance):
            label = "swipe_right" if dx > 0 else "swipe_left"
            # confidence = how far past threshold 
            conf = float(min(1.0, (adx - self.min_move) / (self.min_move * 1.5) + 0.4))

        elif ady > self.min_move and ady > (adx * self.dominance):
            label = "swipe_down" if dy > 0 else "swipe_up"
            conf = float(min(1.0, (ady - self.min_move) / (self.min_move * 1.5) + 0.4))

        if label:
            self.last_fire_time = now
            self.reset()  # reset so one swipe triggers once
            return MotionResult(label, conf)

        return MotionResult(None, 0.0)