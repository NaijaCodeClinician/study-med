"""
A compilation of validator functions, for validating StudyMed user inputs
"""

from src.utils.helpers import parse_time

# ===========================
#       TIME VALIDATORS
# ===========================


def validate_and_detect_format(
    time_input: str,
):
    """Validate a time input and detect format (12h or 24h)."""
    time_str = time_input.strip()

    time_has_meridian = "am" in time_str.lower() or "pm" in time_str.lower()

    fmt = "12h" if time_has_meridian else "24h"

    time_min = parse_time(time_str)

    if time_min is None:
        return None, None

    return time_min, fmt
