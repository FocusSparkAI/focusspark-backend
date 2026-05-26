from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class ExpiredToken(SQLModel, table=True):
    __tablename__ = "expired_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    token_hash: str = Field(index=True, unique=True, max_length=64)
    user_id: Optional[int] = Field(default=None, index=True)
    expires_at: Optional[datetime] = Field(default=None, index=True)
    expired_at: datetime = Field(default_factory=datetime.utcnow)
