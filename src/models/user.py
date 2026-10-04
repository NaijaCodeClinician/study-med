"""
This module is the central model of a basic telegram user
"""

from dataclasses import dataclass


@dataclass
class User:
    """
    The model of a basic telegram user
    """

    user_id: int
