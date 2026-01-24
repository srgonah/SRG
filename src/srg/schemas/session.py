"""Session schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class CreateSessionRequest(BaseModel):
    """Create session request."""

    title: str | None = Field(default=None, max_length=200)
    metadata: dict | None = None


class SessionResponse(BaseModel):
    """Session response schema."""

    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}


class SessionListResponse(BaseModel):
    """Session list response."""

    sessions: list[SessionResponse]
    total: int


class MessageResponse(BaseModel):
    """Message response schema."""

    id: str
    role: str
    content: str
    created_at: datetime
    context_used: str | None = None
