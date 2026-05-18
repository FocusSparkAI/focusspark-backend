from sqlmodel import SQLModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime


class AcademicFocus(str, Enum):
    COMPUTER_SCIENCE = "Computer Science"
    MEDICINE = "Medicine"
    ENGINEERING = "Engineering"
    BUSINESS = "Business"
    LAW = "Law"
    PSYCHOLOGY = "Psychology"
    BIOLOGY = "Biology"
    MATHEMATICS = "Mathematics"
    PHYSICS = "Physics"
    OTHER = "Other"


class User(SQLModel, table=True):
    __tablename__ = "users"
    id: Optional[int] = Field(default=None, primary_key=True)
    email: str = Field(index=True, unique=True)
    password: str
    full_name: str
    avatar_url: Optional[str] = None
    current_streak: int = 0
    longest_streak: int = 0
    total_focus_minutes: int = 0
    preferred_study_duration: int = 25
    preferred_break_duration: int = 5
    academic_focus: AcademicFocus
    accepted_terms: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
