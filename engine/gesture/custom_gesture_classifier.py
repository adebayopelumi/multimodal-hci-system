# engine/gesture/custom_gesture_classifier.py

import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import numpy as np
import mediapipe as mp

GESTURE_DATA_PATH = Path(__file__).resolve().parent / "custom_gestures.json"

# label -> list of sample vectors
CUSTOM_GESTURES: Dict[str, List[List[float]]] = {}

mp_hands = mp.solutions.hands


#  DATA LOADING 

def _load_custom_gestures() -> Dict[str, List[List[float]]]:
    global CUSTOM_GESTURES
    if CUSTOM_GESTURES:
        return CUSTOM_GESTURES

    if not GESTURE_DATA_PATH.exists():
        print(f"[CustomGestures] No dataset found at {GESTURE_DATA_PATH}")
        CUSTOM_GESTURES = {}
        return CUSTOM_GESTURES

    with GESTURE_DATA_PATH.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    cleaned: Dict[str, List[List[float]]] = {}
    for label, samples in raw.items():
        cleaned[label] = [list(map(float, vec)) for vec in samples]

    CUSTOM_GESTURES = cleaned
    print(f"[CustomGestures] Loaded labels: {list(CUSTOM_GESTURES.keys())}")
    return CUSTOM_GESTURES


#  FEATURE EXTRACTION 

def _landmarks_to_vector(hand_landmarks: mp_hands.HandLandmark) -> np.ndarray:
    """
    Convert MediaPipe hand landmarks → normalized 2D vector.
    - 21 landmarks
    - (x, y) only
    - wrist-centered
    - scale-normalized
    """
    vec: List[float] = []
    for lm in hand_landmarks.landmark:
        vec.append(lm.x)
        vec.append(lm.y)

    vec = np.asarray(vec, dtype=np.float32)

    # Center on wrist
    wrist_x, wrist_y = vec[0], vec[1]
    for i in range(0, len(vec), 2):
        vec[i] -= wrist_x
        vec[i + 1] -= wrist_y

    # Scale normalization
    coords = vec.reshape(-1, 2)
    max_dist = np.max(np.linalg.norm(coords, axis=1))
    if max_dist > 1e-6:
        vec /= max_dist

    return vec


#  SIMILARITY 

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    if a.shape != b.shape:
        return -1.0
    na = np.linalg.norm(a)
    nb = np.linalg.norm(b)
    if na < 1e-6 or nb < 1e-6:
        return -1.0
    return float(np.dot(a, b) / (na * nb))


#  CLASSIFIER 

def classify_custom_static(
    hand_landmarks: mp_hands.HandLandmark,
    min_score: float = 0.97,
    other_margin: float = 0.01,
) -> Tuple[Optional[str], float]:
    """
    Confidence-first custom gesture classifier.

    Rules:
    - If best_score >= min_score → RETURN label
    - Otherwise → RETURN None
    """

    gestures = _load_custom_gestures()
    if not gestures:
        return None, -1.0

    live_vec = _landmarks_to_vector(hand_landmarks)

    best_label: Optional[str] = None
    best_score: float = -1.0

    second_best: float = -1.0

    for label, samples in gestures.items():
        for sample in samples:
            score = _cosine_similarity(
                live_vec,
                np.asarray(sample, dtype=np.float32),
            )
            if score > best_score:
                second_best = best_score
                best_score = score
                best_label = label
            elif score > second_best:
                second_best = score



    # HARD RULE: strong match always wins
    if best_label is not None and best_score >= min_score:
        return best_label, best_score

    return None, best_score