from sqlmodel import SQLModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, JSON, Text, UniqueConstraint


class QuizDifficulty(str, Enum):
    BEGINNER = "Beginner"
    INTERMEDIATE = "Intermediate"
    ADVANCED = "Advanced"


class Quiz(SQLModel, table=True):
    __tablename__ = "quizzes"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    category: Optional[str] = Field(default=None, max_length=255)
    difficulty: QuizDifficulty = Field(default=QuizDifficulty.BEGINNER)
    topic: Optional[str] = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=50)
    linked_document_id: Optional[int] = Field(default=None, foreign_key="documents.id")
    time_limit_seconds: Optional[int] = None
    passing_score: int = 70
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    total_questions: int = 0
    created_from_message_id: Optional[int] = Field(
        default=None, foreign_key="chat_messages.id"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class QuizQuestion(SQLModel, table=True):
    __tablename__ = "quiz_questions"

    id: Optional[int] = Field(default=None, primary_key=True)
    quiz_id: int = Field(foreign_key="quizzes.id")
    question: str = Field(sa_column=Column(Text, nullable=False))
    image_url: Optional[str] = Field(default=None, max_length=1024)
    options: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    correct_answer_index: int
    explanation: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    topic: Optional[str] = Field(default=None, max_length=255)
    related_flashcard_id: Optional[int] = Field(default=None, foreign_key="flashcards.id")
    position: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QuizAttempt(SQLModel, table=True):
    __tablename__ = "quiz_attempts"

    id: Optional[int] = Field(default=None, primary_key=True)
    quiz_id: int = Field(foreign_key="quizzes.id")
    user_id: int = Field(foreign_key="users.id")
    score: int
    total_questions: int
    percentage: float = 0.0
    passed: bool = False
    time_taken_seconds: Optional[int] = None
    started_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class QuizAttemptAnswer(SQLModel, table=True):
    __tablename__ = "quiz_attempt_answers"
    __table_args__ = (UniqueConstraint("attempt_id", "question_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    attempt_id: int = Field(foreign_key="quiz_attempts.id")
    question_id: int = Field(foreign_key="quiz_questions.id")
    selected_answer_index: Optional[int] = None
    is_correct: bool
