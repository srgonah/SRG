"""Chat schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Chat request schema."""

    message: str = Field(..., min_length=1, max_length=4000)
    session_id: str | None = None
    use_rag: bool = True
    top_k: int = Field(default=5, ge=1, le=20)
    stream: bool = False


class MessageSchema(BaseModel):
    """Chat message schema."""

    id: str
    role: str
    content: str
    created_at: datetime
    context_used: str | None = None


class ChatResponse(BaseModel):
    """Chat response schema."""

    session_id: str
    message: MessageSchema
    context_chunks: int = 0
