"""
The centralized json loader file, loads contents and configurations for StudyMed
"""

import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]


def load_configuration():
    """
    The configuration file loader function
    """
    CONFIG_FILE = BASE_DIR / "config" / "config.json"

    if not CONFIG_FILE.exists():
        raise ValueError("❌ Configuration file not found")

    with open(CONFIG_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:  # noqa:BLE001
            return {}


def load_subjects_content():
    """
    The subjects file loader function
    """
    SUBJECTS_FILE = BASE_DIR / "content" / "subjects.json"

    if not SUBJECTS_FILE.exists():
        raise ValueError("❌ Subjects file not found")

    with open(SUBJECTS_FILE, encoding="utf-8") as f:
        try:
            return json.load(f)
        except Exception:  # noqa: BLE001
            return {}
