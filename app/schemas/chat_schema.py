from pydantic import BaseModel
from typing import Literal


class ChatRequest(BaseModel):
    message: str
    thread_id: int


class CreateThreadRequest(BaseModel):
    title: str | None = None
    ai_provider: Literal["openai", "gemini"] | None = None
    ai_model: str | None = None


class ChatResponse(BaseModel):
    response: str
    message_id: int
