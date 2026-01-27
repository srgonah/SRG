"""
Chat session domain entities.

Manages conversation state, messages, and memory facts.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message sender role."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class MessageType(str, Enum):
    """Type of message content."""

    TEXT = "text"
    SEARCH_QUERY = "search_query"
    SEARCH_RESULT = "search_result"
    DOCUMENT_REF = "document_ref"
    ERROR = "error"


class Message(BaseModel):
    """
    Single message in a chat session.

    Includes content, role, and optional RAG context.
    """

    id: int | None = None
    session_id: str

    # Message content
    role: MessageRole
    content: str
    message_type: MessageType = MessageType.TEXT

    # RAG context (if message includes search results)
    search_query: str | None = None
    search_results: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    # Token counts (for context management)
    token_count: int = 0

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class MemoryFactType(str, Enum):
    """Type of memory fact."""

    USER_PREFERENCE = "user_preference"
    DOCUMENT_CONTEXT = "document_context"
    ENTITY = "entity"
    RELATIONSHIP = "relationship"
    TEMPORAL = "temporal"


class MemoryFact(BaseModel):
    """
    Long-term memory fact extracted from conversation.

    Facts are used to maintain context across sessions.
    """

    id: int | None = None
    session_id: str | None = None

    # Fact content
    fact_type: MemoryFactType
    key: str
    value: str
    confidence: float = 1.0

    # Relationships
    related_doc_ids: list[int] = Field(default_factory=list)
    related_invoice_ids: list[int] = Field(default_factory=list)

    # Usage tracking
    access_count: int = 0
    last_accessed: datetime | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None


class SessionStatus(str, Enum):
    """Session state."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class ChatSession(BaseModel):
    """
    Chat session containing messages and context.

    Replaces JSON file storage with proper entities.
    """

    id: int | None = None
    session_id: str = Field(default_factory=lambda: str(uuid4()))

    # Session metadata
    title: str | None = None
    status: SessionStatus = SessionStatus.ACTIVE

    # Context
    company_key: str | None = None
    active_doc_ids: list[int] = Field(default_factory=list)
    active_invoice_ids: list[int] = Field(default_factory=list)

    # Messages (loaded on demand)
    messages: list[Message] = Field(default_factory=list)

    # Memory facts
    memory_facts: list[MemoryFact] = Field(default_factory=list)

    # Summary for long conversations
    conversation_summary: str | None = None
    summary_message_count: int = 0

    # Token tracking
    total_tokens: int = 0
    max_context_tokens: int = 8000

    # Settings
    system_prompt: str | None = None
    temperature: float = 0.7

    # Custom metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    last_message_at: datetime | None = None

    def add_message(self, role: MessageRole, content: str, **kwargs: Any) -> Message:
        """Add a message to the session."""
        message = Message(session_id=self.session_id, role=role, content=content, **kwargs)
        self.messages.append(message)
        self.last_message_at = message.created_at
        self.updated_at = message.created_at
        return message

    def get_context_messages(self, max_tokens: int = 4000) -> list[Message]:
        """
        Get recent messages that fit within token budget.

        Includes conversation summary if available.
        """
        if not self.messages:
            return []

        # Start from most recent and work backwards
        context: list[Message] = []
        tokens_used = 0

        for msg in reversed(self.messages):
            if tokens_used + msg.token_count > max_tokens:
                break
            context.insert(0, msg)
            tokens_used += msg.token_count

        return context

    def add_memory_fact(
        self, fact_type: MemoryFactType, key: str, value: str, **kwargs: Any
    ) -> MemoryFact:
        """Add or update a memory fact."""
        # Check if fact with same key exists
        for existing in self.memory_facts:
            if existing.key == key:
                existing.value = value
                existing.updated_at = datetime.utcnow()
                existing.access_count += 1
                return existing

        # Create new fact
        fact = MemoryFact(
            session_id=self.session_id, fact_type=fact_type, key=key, value=value, **kwargs
        )
        self.memory_facts.append(fact)
        return fact

    @property
    def message_count(self) -> int:
        return len(self.messages)

    @property
    def needs_summary(self) -> bool:
        """Check if conversation needs summarization."""
        return self.message_count > 20 and self.message_count - self.summary_message_count > 10
