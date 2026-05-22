from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import inspect, text
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


def init_db():
    SQLModel.metadata.create_all(engine)
    _ensure_user_profile_columns()
    _seed_default_achievements()


def _ensure_user_profile_columns():
    inspector = inspect(engine)
    if not inspector.has_table("users"):
        return

    existing = {column["name"] for column in inspector.get_columns("users")}
    timestamp_type = "TIMESTAMP" if engine.dialect.name == "postgresql" else "DATETIME"
    additions = []
    if "bio" not in existing:
        additions.append(("bio", "TEXT NULL"))
    if "avatar_url" not in existing:
        additions.append(("avatar_url", "VARCHAR(1024) NULL"))
    if "updated_at" not in existing:
        additions.append(("updated_at", f"{timestamp_type} NULL"))

    if not additions:
        return

    with engine.begin() as connection:
        for column_name, definition in additions:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {definition}"))


def _seed_default_achievements():
    defaults = [
        {
            "key": "first_session",
            "title": "First Step",
            "description": "Complete your first study session.",
            "badge_icon": "clock",
            "criteria_type": "sessions_completed",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze", "reward": "Blue timer theme unlocked"},
        },
        {
            "key": "streak_starter",
            "title": "Streak Starter",
            "description": "Maintain a 7-day study streak.",
            "badge_icon": "flame",
            "criteria_type": "streak_days",
            "criteria_target": 7,
            "criteria_data": {"tier": "silver", "reward": "Fire avatar border"},
        },
        {
            "key": "focus_master",
            "title": "Focus Master",
            "description": "Complete a session with 100% focus.",
            "badge_icon": "trophy",
            "criteria_type": "distraction_free_sessions",
            "criteria_target": 1,
            "criteria_data": {"tier": "gold"},
        },
        {
            "key": "session_collector",
            "title": "Session Collector",
            "description": "Complete 100 focused study blocks.",
            "badge_icon": "brain",
            "criteria_type": "work_sessions_completed",
            "criteria_target": 100,
            "criteria_data": {"tier": "silver", "reward": "Purple gradient theme"},
        },
        {
            "key": "focus_champion",
            "title": "Focus Champion",
            "description": "Reach 95% average focus.",
            "badge_icon": "target",
            "criteria_type": "average_focus",
            "criteria_target": 95,
            "criteria_data": {"tier": "gold"},
        },
        {
            "key": "early_bird",
            "title": "Early Bird",
            "description": "Start a study session before 7 AM.",
            "badge_icon": "zap",
            "criteria_type": "early_sessions",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "night_owl",
            "title": "Night Owl",
            "description": "Study after midnight.",
            "badge_icon": "star",
            "criteria_type": "late_sessions",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "marathon_runner",
            "title": "Marathon Runner",
            "description": "Complete 10 study sessions in one day.",
            "badge_icon": "trending-up",
            "criteria_type": "daily_sessions",
            "criteria_target": 10,
            "criteria_data": {"tier": "gold"},
        },
        {
            "key": "knowledge_seeker",
            "title": "Knowledge Seeker",
            "description": "Upload 50 study documents.",
            "badge_icon": "book-open",
            "criteria_type": "documents_uploaded",
            "criteria_target": 50,
            "criteria_data": {"tier": "silver"},
        },
        {
            "key": "consistency_king",
            "title": "Consistency King",
            "description": "Maintain a 30-day streak.",
            "badge_icon": "calendar",
            "criteria_type": "streak_days",
            "criteria_target": 30,
            "criteria_data": {"tier": "platinum", "reward": "Crown avatar icon"},
        },
        {
            "key": "perfect_score",
            "title": "Perfect Score",
            "description": "Complete 10 distraction-free sessions.",
            "badge_icon": "award",
            "criteria_type": "distraction_free_sessions",
            "criteria_target": 10,
            "criteria_data": {"tier": "platinum"},
        },
        {
            "key": "momentum_builder",
            "title": "Momentum Builder",
            "description": "Complete a focus block in every planned slot.",
            "badge_icon": "zap",
            "criteria_type": "sessions_completed",
            "criteria_target": 12,
            "criteria_data": {"tier": "gold"},
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
