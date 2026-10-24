# --- IMPORTS ---
import json
from pathlib import Path

# --- PATH CONFIG ---
BASE_DIR = Path(__file__).resolve().parent.parent

def get_workout_guide():
    file_path = (
        BASE_DIR /
        "workout_app_guideline" /
        "guide" /
        "workout_guide.json"
    )

    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)