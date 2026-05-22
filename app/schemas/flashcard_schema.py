from pydantic import BaseModel
from pydantic import Field
from typing import List, Optional
from datetime import datetime


class FlashcardDeckResponse(BaseModel):
    id: int
    user_id: int
    title: str
    description: Optional[str] = None
    topic: Optional[str] = None
    source: str
    created_from_message_id: Optional[int] = None
    created_at: datetime
    updated_at: datetime


class FlashcardCreate(BaseModel):
    front: str
    back: str


class FlashcardResponse(BaseModel):
    id: int
    front: str
    back: str

    class Config:
        from_attributes = True


class FlashcardBundleResponse(BaseModel):
    deck: FlashcardDeckResponse
    flashcards: List[FlashcardResponse]


class FlashcardGenerate(BaseModel):
    topic: str
    card_count: Optional[int] = Field(default=None, ge=1, le=50)


class FlashcardFromChat(BaseModel):
    message_id: int