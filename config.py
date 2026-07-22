"""Runtime configuration helpers for SafelyDriven."""

import os
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent


def get_int(name, default, minimum=0):
    """Read a non-negative integer environment variable with a safe fallback."""
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value >= minimum else default


FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = get_int("FLASK_PORT", 5000, minimum=1)
CAMERA_INDEX = get_int("CAMERA_INDEX", 0)
ARDUINO_PORT = os.getenv("ARDUINO_PORT", "").strip()
LANDMARK_MODEL_PATH = PROJECT_ROOT / "shape_predictor_68_face_landmarks.dat"
MUSIC_PATH = PROJECT_ROOT / "music.wav"
EVENT_LOG_PATH = PROJECT_ROOT / "event_log"
