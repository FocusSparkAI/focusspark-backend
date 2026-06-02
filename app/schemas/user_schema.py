from typing import Optional

from pydantic import BaseModel, EmailStr
from datetime import datetime
from app.models.user_model import AcademicFocus

class UserSignup(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    confirm_password: str
    academic_focus: AcademicFocus
    accepted_terms: bool
    timezone: Optional[str] = None
    

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserPasswordUpdate(BaseModel):
    current_password: str
    new_password: str
    confirm_password: str


class UserProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    academic_focus: AcademicFocus
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: str = "UTC"
    last_login: Optional[datetime] = None
    created_at: datetime


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    academic_focus: Optional[AcademicFocus] = None
    bio: Optional[str] = None
    avatar_url: Optional[str] = None
    timezone: Optional[str] = None
