from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    thread_id: int


class CreateThreadRequest(BaseModel):
    title: str = "Test Thread"


class ChatResponse(BaseModel):
    response: str
    message_id: int
