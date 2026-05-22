from sqlmodel import SQLModel, Field
from typing import List, Optional
from datetime import datetime
from sqlalchemy import Column, JSON, Text, UniqueConstraint


class FlashcardDeck(SQLModel, table=True):
    __tablename__ = "flashcard_decks"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: str = Field(max_length=255)
    description: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    topic: Optional[str] = Field(default=None, max_length=255)
    source: str = Field(default="manual", max_length=50)  # ai / manual / chat
    linked_document_id: Optional[int] = Field(default=None, foreign_key="documents.id")
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    total_cards: int = 0
    created_from_message_id: Optional[int] = Field(
        default=None, foreign_key="chat_messages.id"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class Flashcard(SQLModel, table=True):
    __tablename__ = "flashcards"

    id: Optional[int] = Field(default=None, primary_key=True)
    deck_id: int = Field(foreign_key="flashcard_decks.id")
    title: Optional[str] = Field(default=None, max_length=255)
    front: str = Field(sa_column=Column(Text, nullable=False))
    back: str = Field(sa_column=Column(Text, nullable=False))
    explanation: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    example: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    memory_tip: Optional[str] = Field(default=None, sa_column=Column(Text, nullable=True))
    difficulty: str = Field(default="medium", max_length=50)
    tags: List[str] = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    position: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

class FlashcardReview(SQLModel, table=True):
    __tablename__ = "flashcard_reviews"
    __table_args__ = (UniqueConstraint("user_id", "flashcard_id"),)

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    flashcard_id: int = Field(foreign_key="flashcards.id")
    known: bool = False
    correct_count: int = 0
    incorrect_count: int = 0
    repetitions: int = 0
    review_interval_days: int = 1
    last_reviewed_at: Optional[datetime] = None
    next_review_at: Optional[datetime] = None
    ease_factor: float = 2.5
