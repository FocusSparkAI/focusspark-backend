from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import text
from app.core.config import DATABASE_URL
from app.models.chat_model import ChatMessage, ChatThread, Document, MessageArtifact
from app.models.flashcard_model import Flashcard, FlashcardDeck, FlashcardReview
from app.models.productivity_model import (
    Achievement,
    DistractionEvent,
    EmotionLog,
    Notification,
    StudyGoal,
    StudySession,
    UserAchievement,
    UserSettings,
)
from app.models.quiz_model import Quiz, QuizAttempt, QuizAttemptAnswer, QuizQuestion
from app.models.user_model import User

assert DATABASE_URL is not None
engine = create_engine(DATABASE_URL, echo=True)

def get_session():
    with Session(engine) as session:
        yield session


def _ensure_mysql_chatmessage_content_text():
    # Existing tables created earlier may still have VARCHAR content columns.
    if engine.dialect.name != "mysql":
        return

    with engine.begin() as connection:
        table_name = connection.execute(
            text(
                """
                SELECT TABLE_NAME
                FROM INFORMATION_SCHEMA.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME IN ('chat_messages', 'chatmessage')
                ORDER BY CASE TABLE_NAME WHEN 'chat_messages' THEN 0 ELSE 1 END
                LIMIT 1
                """
            )
        ).scalar()

        if not table_name:
            return

        column_type = connection.execute(
            text(
                """
                SELECT DATA_TYPE
                FROM INFORMATION_SCHEMA.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = :table_name
                  AND COLUMN_NAME = 'content'
                """
            ),
            {"table_name": table_name},
        ).scalar()

        if str(column_type).lower() == "text":
            return

        connection.execute(
            text(f"ALTER TABLE {table_name} MODIFY COLUMN content TEXT NOT NULL")
        )

def init_db():
    SQLModel.metadata.create_all(engine)
    _ensure_mysql_chatmessage_content_text()
