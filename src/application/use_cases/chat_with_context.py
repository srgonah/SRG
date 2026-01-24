"""
Chat With Context Use Case.

Handles RAG-powered chat conversations.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass

from src.application.dto.requests import ChatRequest, CreateSessionRequest
from src.application.dto.responses import (
    ChatMessageResponse,
    ChatResponse,
    SessionListResponse,
    SessionResponse,
)
from src.config import get_logger
from src.core.entities.session import ChatSession, Message
from src.core.services import (
    ChatService,
    get_chat_service,
)

logger = get_logger(__name__)


@dataclass
class ChatResultDTO:
    """Chat result data transfer object."""

    session: ChatSession
    message: Message
    context_chunks: int = 0


class ChatWithContextUseCase:
    """
    Use case for RAG-powered chat.

    Manages sessions, retrieves context,
    and generates responses.
    """

    def __init__(self, chat_service: ChatService | None = None):
        self._chat = chat_service

    async def _get_chat(self) -> ChatService:
        if self._chat is None:
            self._chat = await get_chat_service()
        return self._chat

    async def execute(self, request: ChatRequest) -> ChatResultDTO:
        """
        Execute chat use case.

        Args:
            request: Chat request with message and options

        Returns:
            ChatResultDTO with response and session info
        """
        logger.info(
            "chat_started",
            session_id=request.session_id,
            use_rag=request.use_rag,
        )

        chat = await self._get_chat()

        # Get or create session
        session = None
        if request.session_id:
            session = await chat.get_session(request.session_id)

        # Send message
        response = await chat.chat(
            message=request.message,
            session_id=request.session_id,
            use_rag=request.use_rag,
            top_k=request.top_k,
        )

        # Get updated session
        if session is None:
            session = await chat.get_session(response.session_id)

        context_chunks = 0
        if response.context_used:
            # Count context chunks used
            context_chunks = response.context_used.count("[")

        logger.info(
            "chat_complete",
            session_id=session.id,
            response_length=len(response.content),
        )

        return ChatResultDTO(
            session=session,
            message=response,
            context_chunks=context_chunks,
        )

    async def stream(self, request: ChatRequest) -> AsyncIterator[str]:
        """
        Stream chat response.

        Yields response chunks as they're generated.
        """
        chat = await self._get_chat()

        async for chunk in chat.chat_stream(
            message=request.message,
            session_id=request.session_id,
            use_rag=request.use_rag,
            top_k=request.top_k,
        ):
            yield chunk

    async def create_session(
        self,
        request: CreateSessionRequest,
    ) -> ChatSession:
        """Create a new chat session."""
        chat = await self._get_chat()
        return await chat.create_session(
            title=request.title,
            metadata=request.metadata,
        )

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get session by ID."""
        chat = await self._get_chat()
        return await chat.get_session(session_id)

    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List recent sessions."""
        chat = await self._get_chat()
        return await chat.list_sessions(limit=limit, offset=offset)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        chat = await self._get_chat()
        return await chat.delete_session(session_id)

    async def get_session_summary(self, session_id: str) -> str:
        """Generate session summary."""
        chat = await self._get_chat()
        return await chat.get_session_summary(session_id)

    def to_response(self, result: ChatResultDTO) -> ChatResponse:
        """Convert to API response format."""
        return ChatResponse(
            session_id=result.session.session_id,
            message=ChatMessageResponse(
                id=result.message.id,
                role=result.message.role.value,
                content=result.message.content,
                created_at=result.message.created_at,
                context_used=getattr(result.message, "context_used", None),
            ),
            context_chunks=result.context_chunks,
        )

    def session_to_response(self, session: ChatSession) -> SessionResponse:
        """Convert session to response format."""
        return SessionResponse(
            id=session.session_id,
            title=session.title or "",
            message_count=session.message_count,
            created_at=session.created_at,
            updated_at=session.updated_at,
            metadata=session.metadata,
        )

    def sessions_to_response(
        self,
        sessions: list[ChatSession],
        total: int | None = None,
    ) -> SessionListResponse:
        """Convert session list to response format."""
        return SessionListResponse(
            sessions=[self.session_to_response(s) for s in sessions],
            total=total or len(sessions),
        )
