from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
from sqlalchemy import Column, JSON, Text


class ChatThread(SQLModel, table=True):
    __tablename__ = "chat_threads"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    title: Optional[str] = None
    persona: str = "sensei"
    pinned: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class ChatMessage(SQLModel, table=True):
    __tablename__ = "chat_messages"

    id: Optional[int] = Field(default=None, primary_key=True)
    thread_id: int = Field(foreign_key="chat_threads.id")
    type: str  # user / ai / flashcard / quiz
    content: str = Field(sa_column=Column(Text, nullable=False))
    payload: Optional[dict] = Field(
        default=None,
        sa_column=Column("metadata", JSON, nullable=True),
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MessageArtifact(SQLModel, table=True):
    __tablename__ = "message_artifacts"

    id: Optional[int] = Field(default=None, primary_key=True)
    message_id: int = Field(foreign_key="chat_messages.id")
    artifact_type: str  # deck / quiz
    artifact_id: int

class Document(SQLModel, table=True):
    __tablename__ = "documents"

    id: Optional[int] = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="users.id")
    name: str
    file_type: str
    file_size: Optional[int] = None
    storage_path: str
    extracted_text: Optional[str] = None
    processed: bool = False
    uploaded_from: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
