"""
This is the integrated KnowledgeCard store module integrated with the central database module
"""

from datetime import datetime, timezone

from src.models.knowledge_card import KnowledgeCard
from src.storage.database import Database


class KnowledgeCardStore:
    """
    The central knowledge card store class
    """

    def __init__(self, database: Database):
        self.database = database

    def save_card(
        self,
        user_id: int,
        card: KnowledgeCard,
    ) -> int:

        with self.database.connect() as connection:
            # ------------------------------------------
            # Make sure the user exists
            # ------------------------------------------

            connection.execute(
                """
                INSERT OR IGNORE INTO users (
                    id,
                    created_at
                )
                VALUES (?, ?)
                """,
                (
                    user_id,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )

            # ------------------------------------------
            # Save the knowledge card
            # ------------------------------------------

            cursor = connection.execute(
                """
                INSERT INTO knowledge_cards (
                    user_id,
                    subject,
                    source_knowledge,
                    question,
                    answer,
                    difficulty,
                    case_sensitive
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user_id,
                    card.subject,
                    card.source_knowledge,
                    card.question,
                    card.answer,
                    card.difficulty,
                    int(card.case_sensitive),
                ),
            )

            card_id = cursor.lastrowid

            # ------------------------------------------
            # Save each topic
            # ------------------------------------------

            for topic in card.topics:
                connection.execute(
                    """
                    INSERT INTO card_topics (
                        card_id,
                        topic
                    )
                    VALUES (?, ?)
                    """,
                    (
                        card_id,
                        topic,
                    ),
                )

        return card_id if card_id else 0
