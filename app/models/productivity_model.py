from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, JSON, Text
from sqlmodel import Field, SQLModel


class StudySession(SQLModel, table=True):
    __tablename__ = "study_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    session_type: str = Field(max_length=50)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    ended_at: Optional[datetime] = None
    planned_duration_minutes: int
    actual_duration_minutes: Optional[int] = None
    completed: bool = False
    distraction_count: int = 0
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class DistractionEvent(SQLModel, table=True):
    __tablename__ = "distraction_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    session_id: int = Field(foreign_key="study_sessions.id")
    event_type: str = Field(max_length=100)
    source: str = Field(max_length=100)
    confidence_score: Optional[float] = None
    productive: Optional[bool] = None
    payload: Optional[dict] = Field(
        default=None,
        sa_column=Column("metadata", JSON, nullable=True),
    )
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class EmotionLog(SQLModel, table=True):
    __tablename__ = "emotion_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    session_id: int = Field(foreign_key="study_sessions.id")
    emotion: str = Field(max_length=100)
    confidence_score: Optional[float] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class StudyGoal(SQLModel, table=True):
    __tablename__ = "study_goals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str = Field(max_length=255)
    target_minutes: int
    current_minutes: int = 0
    completed: bool = False
    goal_date: date = Field(default_factory=date.today, index=True)
    position: int = 0
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Achievement(SQLModel, table=True):
    __tablename__ = "achievements"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: Optional[str] = Field(default=None, index=True, unique=True, max_length=100)
    title: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    badge_icon: Optional[str] = Field(default=None, max_length=100)
    criteria_type: Optional[str] = Field(default=None, index=True, max_length=100)
    criteria_target: int = 1
    criteria_window_days: Optional[int] = None
    criteria_data: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserAchievement(SQLModel, table=True):
    __tablename__ = "user_achievements"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    achievement_id: int = Field(foreign_key="achievements.id")
    achievement_title: Optional[str] = Field(default=None, max_length=255)
    unlocked_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    type: str = Field(max_length=50)
    title: str = Field(max_length=255)
    message: str = Field(sa_column=Column(Text, nullable=False))
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    dark_mode: bool = False
    pomodoro_duration_minutes: int = 25
    break_duration_minutes: int = 5
    ai_persona: str = Field(default="supportive", max_length=100)
    preferred_ai_provider: str = Field(default="openai", max_length=50)
    preferred_ai_model: Optional[str] = Field(default=None, max_length=255)
    focus_sensitivity: str = Field(default="medium", max_length=50)
    fallback_method: str = Field(default="manual", max_length=50)
    notifications_enabled: bool = True
    focus_alerts_enabled: bool = False
    integrations: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    appearance: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    accessibility: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    privacy: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
