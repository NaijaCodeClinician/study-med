"""
The module of the central model of a Knowledge Card
"""

from dataclasses import dataclass


@dataclass
class KnowledgeCard:
    """
    The model of a basic knowledge card
    """

    subject: str
    topics: list[str]
    source_knowledge: str
    question: str
    answer: str
    difficulty: str
    case_sensitive: bool
