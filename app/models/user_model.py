from sqlmodel import SQLModel, Field
from typing import Optional
from enum import Enum
from datetime import datetime
from sqlalchemy import Column, Text


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
    email: str = Field(index=True, unique=True, max_length=255)
    password: str = Field(max_length=255)
    full_name: str = Field(max_length=255)
    bio: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    avatar_url: Optional[str] = Field(default=None, max_length=1024)
    avatar_public_id: Optional[str] = Field(default=None, max_length=255)
    current_streak: int = 0
    longest_streak: int = 0
    total_focus_minutes: int = 0
    preferred_study_duration: int = 25
    preferred_break_duration: int = 5
    academic_focus: AcademicFocus
    accepted_terms: bool = Field(default=False)
    is_email_verified: bool = Field(default=False)
    email_verification_otp_hash: Optional[str] = Field(default=None, max_length=64)
    email_verification_expires_at: Optional[datetime] = None
    email_verification_sent_at: Optional[datetime] = None
    password_reset_otp_hash: Optional[str] = Field(default=None, max_length=64)
    password_reset_expires_at: Optional[datetime] = None
    password_reset_sent_at: Optional[datetime] = None
    timezone: str = Field(default="UTC", max_length=100)
    last_login: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
