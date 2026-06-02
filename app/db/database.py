from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy import inspect, text
from app.core.config import DATABASE_URL, SQL_ECHO
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
from app.models.token_model import ExpiredToken
from app.models.user_model import User
from sqlmodel import select

assert DATABASE_URL is not None
engine = create_engine(DATABASE_URL, echo=SQL_ECHO)

def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    _ensure_user_profile_columns()
    _ensure_user_settings_columns()
    _ensure_study_goal_columns()
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
    if "avatar_public_id" not in existing:
        additions.append(("avatar_public_id", "VARCHAR(255) NULL"))
    if "timezone" not in existing:
        additions.append(("timezone", "VARCHAR(100) NOT NULL DEFAULT 'UTC'"))
    if "updated_at" not in existing:
        additions.append(("updated_at", f"{timestamp_type} NULL"))
    if "last_login" not in existing:
        additions.append(("last_login", f"{timestamp_type} NULL"))
    if "is_email_verified" not in existing:
        additions.append(("is_email_verified", "BOOLEAN NOT NULL DEFAULT FALSE"))
    if "email_verification_otp_hash" not in existing:
        additions.append(("email_verification_otp_hash", "VARCHAR(64) NULL"))
    if "email_verification_expires_at" not in existing:
        additions.append(("email_verification_expires_at", f"{timestamp_type} NULL"))
    if "email_verification_sent_at" not in existing:
        additions.append(("email_verification_sent_at", f"{timestamp_type} NULL"))
    if "password_reset_otp_hash" not in existing:
        additions.append(("password_reset_otp_hash", "VARCHAR(64) NULL"))
    if "password_reset_expires_at" not in existing:
        additions.append(("password_reset_expires_at", f"{timestamp_type} NULL"))
    if "password_reset_sent_at" not in existing:
        additions.append(("password_reset_sent_at", f"{timestamp_type} NULL"))

    if not additions:
        return

    with engine.begin() as connection:
        for column_name, definition in additions:
            connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {definition}"))


def _ensure_user_settings_columns():
    inspector = inspect(engine)
    if not inspector.has_table("user_settings"):
        return

    existing = {column["name"] for column in inspector.get_columns("user_settings")}
    additions = []
    if "preferred_ai_provider" not in existing:
        additions.append(("preferred_ai_provider", "VARCHAR(50) NULL"))
    if "preferred_ai_model" not in existing:
        additions.append(("preferred_ai_model", "VARCHAR(255) NULL"))

    if not additions:
        return

    with engine.begin() as connection:
        for column_name, definition in additions:
            connection.execute(text(f"ALTER TABLE user_settings ADD COLUMN {column_name} {definition}"))


def _ensure_study_goal_columns():
    inspector = inspect(engine)
    if not inspector.has_table("study_goals"):
        return

    existing = {column["name"] for column in inspector.get_columns("study_goals")}
    timestamp_type = "TIMESTAMP" if engine.dialect.name == "postgresql" else "DATETIME"
    additions = []
    if "goal_date" not in existing:
        additions.append(("goal_date", "DATE NULL"))
    if "position" not in existing:
        additions.append(("position", "INTEGER NULL"))
    if "completed_at" not in existing:
        additions.append(("completed_at", f"{timestamp_type} NULL"))
    if "updated_at" not in existing:
        additions.append(("updated_at", f"{timestamp_type} NULL"))

    with engine.begin() as connection:
        for column_name, definition in additions:
            connection.execute(text(f"ALTER TABLE study_goals ADD COLUMN {column_name} {definition}"))

        if "goal_date" not in existing:
            if engine.dialect.name == "postgresql":
                connection.execute(
                    text("UPDATE study_goals SET goal_date = COALESCE(due_date, created_at::date, CURRENT_DATE)")
                )
            else:
                connection.execute(
                    text("UPDATE study_goals SET goal_date = COALESCE(due_date, DATE(created_at), DATE('now'))")
                )
        if "position" not in existing:
            connection.execute(text("UPDATE study_goals SET position = COALESCE(position, id, 0)"))
        if "updated_at" not in existing:
            connection.execute(text("UPDATE study_goals SET updated_at = COALESCE(created_at, CURRENT_TIMESTAMP)"))
        connection.execute(text("UPDATE study_goals SET target_minutes = 5 WHERE target_minutes < 5"))


def _seed_default_achievements():
    defaults = [
        {
            "key": "account_created",
            "title": "Welcome to FocusSpark",
            "description": "Create your FocusSpark account.",
            "badge_icon": "user-check",
            "criteria_type": "account_created",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "first_session",
            "title": "First Step",
            "description": "Complete your first study session.",
            "badge_icon": "play-circle",
            "criteria_type": "sessions_completed",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "streak_starter",
            "title": "Streak Starter",
            "description": "Maintain a 7-day study streak.",
            "badge_icon": "flame",
            "criteria_type": "streak_days",
            "criteria_target": 7,
            "criteria_data": {"tier": "silver"},
        },
        {
            "key": "focus_master",
            "title": "Focus Master",
            "description": "Complete a session with 100% focus.",
            "badge_icon": "shield-check",
            "criteria_type": "distraction_free_sessions",
            "criteria_target": 1,
            "criteria_data": {"tier": "gold"},
        },
        {
            "key": "session_collector",
            "title": "Session Collector",
            "description": "Complete 100 focused study blocks.",
            "badge_icon": "boxes",
            "criteria_type": "work_sessions_completed",
            "criteria_target": 100,
            "criteria_data": {"tier": "silver"},
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
            "badge_icon": "sunrise",
            "criteria_type": "early_sessions",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "night_owl",
            "title": "Night Owl",
            "description": "Study after midnight.",
            "badge_icon": "moon",
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
            "key": "first_quiz",
            "title": "Quiz Starter",
            "description": "Create your first quiz.",
            "badge_icon": "clipboard-check",
            "criteria_type": "quizzes_created",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "quiz_builder",
            "title": "Quiz Builder",
            "description": "Create 5 quizzes.",
            "badge_icon": "list-checks",
            "criteria_type": "quizzes_created",
            "criteria_target": 5,
            "criteria_data": {"tier": "silver"},
        },
        {
            "key": "first_flashcard_deck",
            "title": "Flashcard Starter",
            "description": "Create your first flashcard deck.",
            "badge_icon": "layers",
            "criteria_type": "flashcard_decks_created",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "flashcard_builder",
            "title": "Flashcard Builder",
            "description": "Create 5 flashcard decks.",
            "badge_icon": "layers",
            "criteria_type": "flashcard_decks_created",
            "criteria_target": 5,
            "criteria_data": {"tier": "silver"},
        },
        {
            "key": "first_document",
            "title": "First Upload",
            "description": "Upload your first study document.",
            "badge_icon": "upload",
            "criteria_type": "documents_uploaded",
            "criteria_target": 1,
            "criteria_data": {"tier": "bronze"},
        },
        {
            "key": "consistency_king",
            "title": "Consistency King",
            "description": "Maintain a 30-day streak.",
            "badge_icon": "calendar-days",
            "criteria_type": "streak_days",
            "criteria_target": 30,
            "criteria_data": {"tier": "platinum"},
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
    seed_order = [
        "account_created",
        "first_session",
        "first_quiz",
        "first_flashcard_deck",
        "first_document",
        "early_bird",
        "night_owl",
        "focus_master",
        "quiz_builder",
        "flashcard_builder",
        "streak_starter",
        "momentum_builder",
        "marathon_runner",
        "focus_champion",
        "knowledge_seeker",
        "session_collector",
        "perfect_score",
        "consistency_king",
    ]
    defaults.sort(
        key=lambda item: (
            seed_order.index(item["key"]) if item["key"] in seed_order else len(seed_order),
            item["criteria_target"],
            item["title"],
        )
    )

    with Session(engine) as session:
        existing_keys = set(session.exec(select(Achievement.key)).all())
        added = False
        for item in defaults:
            if item["key"] in existing_keys:
                existing = session.exec(select(Achievement).where(Achievement.key == item["key"])).first()
                if existing:
                    existing.title = item["title"]
                    existing.description = item["description"]
                    existing.badge_icon = item["badge_icon"]
                    existing.criteria_type = item["criteria_type"]
                    existing.criteria_target = item["criteria_target"]
                    existing.criteria_data = item["criteria_data"]
                    session.add(existing)
                    added = True
                continue
            session.add(Achievement(**item))
            added = True
        if added:
            session.commit()
