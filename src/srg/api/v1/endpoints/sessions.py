"""Session management endpoints."""

from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.application.dto.requests import CreateSessionRequest as CreateSessionDTO
from src.application.dto.responses import (
    SessionListResponse as SessionListDTO,
    SessionResponse as SessionDTO,
)
from src.application.use_cases import ChatWithContextUseCase
from src.srg.api.deps import SessionStoreDep
from src.srg.schemas.session import (
    CreateSessionRequest,
    MessageResponse,
    SessionListResponse,
    SessionResponse,
)

router = APIRouter()


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(request: CreateSessionRequest) -> SessionDTO:
    """Create a new chat session."""
    use_case = ChatWithContextUseCase()
    dto = CreateSessionDTO(title=request.title, metadata=request.metadata)

    session = await use_case.create_session(dto)
    return use_case.session_to_response(session)


@router.get("", response_model=SessionListResponse)
async def list_sessions(limit: int = 20, offset: int = 0) -> SessionListDTO:
    """List recent chat sessions."""
    use_case = ChatWithContextUseCase()
    sessions = await use_case.list_sessions(limit=limit, offset=offset)

    return use_case.sessions_to_response(sessions)


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(session_id: str) -> SessionDTO:
    """Get session by ID."""
    use_case = ChatWithContextUseCase()
    session = await use_case.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    return use_case.session_to_response(session)


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(session_id: str) -> None:
    """Delete a chat session."""
    use_case = ChatWithContextUseCase()
    result = await use_case.delete_session(session_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")


@router.get("/{session_id}/messages", response_model=list[MessageResponse])
async def get_session_messages(session_id: str, store: SessionStoreDep, limit: int = 50) -> list[MessageResponse]:
    """Get messages for a session."""
    messages = await store.get_messages(session_id, limit=limit)

    return [
        MessageResponse(
            id=str(msg.id or 0),
            role=msg.role.value,
            content=msg.content,
            created_at=msg.created_at,
            context_used=msg.metadata.get("context_used"),
        )
        for msg in messages
    ]


@router.get("/{session_id}/summary")
async def get_session_summary(session_id: str) -> dict[str, Any]:
    """Generate a summary of the session."""
    use_case = ChatWithContextUseCase()
    summary = await use_case.get_session_summary(session_id)

    return {"session_id": session_id, "summary": summary}
