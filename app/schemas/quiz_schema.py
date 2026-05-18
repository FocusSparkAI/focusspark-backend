from pydantic import BaseModel
from typing import List
from typing import Optional
from datetime import datetime
from app.models.quiz_model import QuizDifficulty


class QuizQuestionCreate(BaseModel):
    question: str
    options: List[str]
    correct_answer_index: int


class QuizCreate(BaseModel):
    title: str
    questions: List[QuizQuestionCreate]


class QuizGenerate(BaseModel):
    topic: str
    difficulty: QuizDifficulty = QuizDifficulty.BEGINNER


class QuizFromChat(BaseModel):
    message_id: int


class QuizQuestionResponse(BaseModel):
    id: int
    quiz_id: int
    question: str
    options: List[str]
    correct_answer_index: int
    explanation: Optional[str] = None


class QuizResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    difficulty: QuizDifficulty
    topic: Optional[str] = None
    source: str
    created_from_message_id: Optional[int] = None
    created_at: datetime


class QuizBundleResponse(BaseModel):
    quiz: QuizResponse
    questions: List[QuizQuestionResponse]