"""
The central database module
"""

import sqlite3
from pathlib import Path


class Database:
    """
    This the central database class that performs all the SQL queries
    """

    def __init__(self, database_path: str = "data/studymed.db"):
        self.database_path = Path(database_path)

        # Create the parent directory if it doesn't exist
        self.database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.initialize()

    def connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)

        # Enable foreign-key enforcement
        connection.execute("PRAGMA foreign_keys = ON")

        return connection

    def initialize(self):
        with self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    last_name TEXT,
                    study_time INTEGER
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS knowledge_cards (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    subject TEXT NOT NULL,
                    source_knowledge TEXT NOT NULL,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    difficulty TEXT NOT NULL,
                    case_sensitive INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                        DEFAULT CURRENT_TIMESTAMP,

                    FOREIGN KEY (user_id)
                        REFERENCES users(id)
                        ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS card_topics (
                    card_id INTEGER NOT NULL,
                    topic TEXT NOT NULL,

                    PRIMARY KEY (card_id, topic),

                    FOREIGN KEY (card_id)
                        REFERENCES knowledge_cards(id)
                        ON DELETE CASCADE
                );
                """
            )
