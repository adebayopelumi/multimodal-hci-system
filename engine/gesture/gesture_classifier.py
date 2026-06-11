# engine/gesture/gesture_classifier.py

"""
Very simple, rule-based static hand gesture classifier.

Labels:
- "open_palm"  : all four fingers extended (index, middle, ring, pinky)
- "fist"       : all four fingers curled
- "point"      : index extended, others curled
- None         : anything else / unknown

We use Mediapipe hand landmarks in *normalized* coordinates:
- x, y in [0, 1] with origin at top-left of the image.
- A finger is considered "extended" if its TIP.y is sufficiently above its PIP.y.
"""

from __future__ import annotations
from typing import Optional


# Mediapipe hand landmark indices:
# Thumb: 4 (TIP)
# Index: 8 (TIP), 6 (PIP)
# Middle: 12 (TIP), 10 (PIP)
# Ring: 16 (TIP), 14 (PIP)
# Pinky: 20 (TIP), 18 (PIP)

def _is_finger_extended(lm, tip_idx: int, pip_idx: int, margin: float = 0.04) -> bool:
    """
    Decide if a finger is extended by comparing TIP.y and PIP.y.
    In Mediapipe, y = 0 at top, increases downward.

    So: TIP.y < PIP.y - margin  -> finger pointing up (extended).
    """
    tip_y = lm[tip_idx].y
    pip_y = lm[pip_idx].y
    return tip_y < (pip_y - margin)


def classify_static_gesture(hand_landmarks, image_width: int, image_height: int) -> Optional[str]:
    """
    Classify a static gesture from Mediapipe HandLandmarks.

    We ignore width/height here because we use normalized coordinates,
    but we keep them in the signature for future use if needed.
    """

    lm = hand_landmarks.landmark  # 21 landmarks, normalized

    # Check extension of four main fingers (ignore thumb for now)
    index_ext  = _is_finger_extended(lm, tip_idx=8,  pip_idx=6)
    middle_ext = _is_finger_extended(lm, tip_idx=12, pip_idx=10)
    ring_ext   = _is_finger_extended(lm, tip_idx=16, pip_idx=14)
    pinky_ext  = _is_finger_extended(lm, tip_idx=20, pip_idx=18)

    extended_count = sum([index_ext, middle_ext, ring_ext, pinky_ext])

    #  OPEN PALM 
    if extended_count == 4:
        return "open_palm"

    #  FIST: all curled 
    if extended_count == 0:
        return "fist"

    #  POINT: index up, others down 
    if index_ext and not (middle_ext or ring_ext or pinky_ext):
        return "point"

    # Could add more classes here, e.g. thumbs_up, pinch, etc.

    return None        