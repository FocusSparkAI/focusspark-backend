from datetime import date, datetime
from typing import Optional

from sqlalchemy import Column, JSON
from sqlmodel import Field, SQLModel


class StudySession(SQLModel, table=True):
    __tablename__ = "study_sessions"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    session_type: str
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
    event_type: str
    source: str
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
    emotion: str
    confidence_score: Optional[float] = None
    detected_at: datetime = Field(default_factory=datetime.utcnow)


class StudyGoal(SQLModel, table=True):
    __tablename__ = "study_goals"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str
    target_minutes: int
    current_minutes: int = 0
    completed: bool = False
    due_date: Optional[date] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Achievement(SQLModel, table=True):
    __tablename__ = "achievements"

    id: Optional[int] = Field(default=None, primary_key=True)
    key: Optional[str] = Field(default=None, index=True, unique=True)
    title: str
    description: Optional[str] = None
    badge_icon: Optional[str] = None
    criteria_type: Optional[str] = Field(default=None, index=True)
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
    achievement_title: Optional[str] = None
    unlocked_at: datetime = Field(default_factory=datetime.utcnow)


class Notification(SQLModel, table=True):
    __tablename__ = "notifications"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    type: str
    title: str
    message: str
    read: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserSettings(SQLModel, table=True):
    __tablename__ = "user_settings"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id", unique=True)
    dark_mode: bool = False
    pomodoro_duration_minutes: int = 25
    break_duration_minutes: int = 5
    ai_persona: str = "supportive"
    focus_sensitivity: str = "medium"
    fallback_method: str = "manual"
    notifications_enabled: bool = True
    focus_alerts_enabled: bool = True
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