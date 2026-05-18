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
    

class UserLogin(BaseModel):
    email: EmailStr
    password: str


class UserProfile(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    academic_focus: AcademicFocus
    created_at: datetime
