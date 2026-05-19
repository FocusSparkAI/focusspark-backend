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
from sqlmodel import select

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
    _seed_default_achievements()
    _ensure_mysql_chatmessage_content_text()


def _seed_default_achievements():
    defaults = [
        {
            "key": "first_session",
            "title": "First Session",
            "description": "Complete your first study session.",
            "badge_icon": "spark",
            "criteria_type": "sessions_completed",
            "criteria_target": 1,
        },
        {
            "key": "focus_builder",
            "title": "Focus Builder",
            "description": "Complete 5 study sessions.",
            "badge_icon": "flame",
            "criteria_type": "sessions_completed",
            "criteria_target": 5,
        },
        {
            "key": "deep_focus",
            "title": "Deep Focus",
            "description": "Reach 100 total focus minutes.",
            "badge_icon": "clock",
            "criteria_type": "focus_minutes",
            "criteria_target": 100,
        },
        {
            "key": "distraction_control",
            "title": "Distraction Control",
            "description": "Complete 30 distraction-free study sessions.",
            "badge_icon": "shield",
            "criteria_type": "distraction_free_sessions",
            "criteria_target": 30,
        },
        {
            "key": "streak_keeper",
            "title": "Streak Keeper",
            "description": "Reach a 7-day focus streak.",
            "badge_icon": "calendar",
            "criteria_type": "streak_days",
            "criteria_target": 7,
        },
    ]

    with Session(engine) as session:
        existing_keys = set(session.exec(select(Achievement.key)).all())
        added = False
        for item in defaults:
            if item["key"] in existing_keys:
                continue
            session.add(Achievement(**item))
            added = True
        if added:
            session.commit()
