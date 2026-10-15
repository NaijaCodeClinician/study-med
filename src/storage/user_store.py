"""
This is the integrated User store module integrated with the central database module
"""

from datetime import UTC, datetime

from src.models.user import User
from src.storage.database import Database


class UserStore:
    """
    The central knowledge card store class
    """

    def __init__(self, database: Database):
        self.database = database

    def store_user(
        self,
        user: User,
    ):

        with self.database.connect() as connection:
            # ------------------------------------------
            # Make sure the user exists
            # ------------------------------------------

            connection.execute(
                """
                INSERT OR IGNORE INTO users (
                    user_id,
                    first_name,
                    last_name,
                    study_time,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    user.user_id,
                    user.first_name,
                    user.last_name,
                    user.study_time,
                    datetime.now(UTC).isoformat(),
                ),
            )

            for topic in user.weak_subjects:
                connection.execute(
                    """
                    INSERT INTO weak_subjects (
                        user_id,
                        subject,
                        topic
                        )
                        VALUES (?, ?, ?)
                    """,
                    (
                        user.user_id,
                        topic,
                    ),
                )
