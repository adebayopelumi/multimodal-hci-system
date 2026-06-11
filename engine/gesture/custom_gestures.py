# engine/gesture/custom_gestures.py

import json
import math
from pathlib import Path
from typing import Dict, List, Tuple, Optional

# Where we'll store your gesture database
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "engine" / "gesture" / "custom_gestures.json"


def landmarks_to_vector(hand_landmarks) -> List[float]:
    """
    Convert Mediapipe hand landmarks to a normalized flat vector.
    - Translate so wrist is at (0, 0).
    - Scale so average distance to wrist ~ 1.
    This makes gestures more robust to position and size.
    """
    lm = hand_landmarks.landmark
    wrist = lm[0]

    xs = []
    ys = []

    for p in lm:
        xs.append(p.x - wrist.x)
        ys.append(p.y - wrist.y)

    # Compute scale (average distance from wrist)
    dists = [math.sqrt(x * x + y * y) for x, y in zip(xs, ys)]
    scale = sum(dists) / len(dists) if dists else 1.0
    if scale < 1e-6:
        scale = 1.0

    # Normalize
    vec: List[float] = []
    for x, y in zip(xs, ys):
        vec.append(x / scale)
        vec.append(y / scale)

    return vec  


def _load_db() -> Dict[str, List[List[float]]]:
    """
    Load gesture database from gesture_db.json.
    Structure:
    {
      "next_slide": [[...vec1...], [...vec2...]],
      "pause_play": [[...], ...],
      ...
    }
    """
    if not DB_PATH.exists():
        return {}
    with DB_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def _save_db(db: Dict[str, List[List[float]]]) -> None:
    """
    Save gesture database to gesture_db.json.
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DB_PATH.open("w", encoding="utf-8") as f:
        json.dump(db, f, indent=2)


def add_gesture_sample(label: str, vec: List[float]) -> None:
    """
    Add one gesture sample to the DB under the given label.
    Example:
      add_gesture_sample("next_slide", [0.1, -0.2, ...])
    """
    db = _load_db()
    if label not in db:
        db[label] = []
    db[label].append(vec)
    _save_db(db)
    print(f"[Gestures] Saved sample for '{label}'. Total samples: {len(db[label])}")


def classify_gesture(vec: List[float], threshold: float = 0.35) -> Tuple[Optional[str], float]:
    """
    Compare current vector to all stored samples using Euclidean distance.

    Returns:
      (best_label, best_distance) if best_distance < threshold
      (None, best_distance) otherwise
    """
    db = _load_db()
    if not db:
        return None, 999.0

    best_label: Optional[str] = None
    best_dist: float = 999.0

    for label, samples in db.items():
        for sample in samples:
            # Euclidean distance
            d = math.sqrt(sum((a - b) ** 2 for a, b in zip(vec, sample)))
            if d < best_dist:
                best_dist = d
                best_label = label

    if best_label is not None and best_dist < threshold:
        return best_label, best_dist
    return None, best_dist