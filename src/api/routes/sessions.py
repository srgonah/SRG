"""
Chat session management endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_chat_use_case, get_sess_store
from src.application.dto.requests import CreateSessionRequest
from src.application.dto.responses import (
    ChatMessageResponse,
    ErrorResponse,
    SessionListResponse,
    SessionResponse,
)
from src.application.use_cases import ChatWithContextUseCase

router = APIRouter(prefix="/api/sessions", tags=["sessions"])


@router.post(
    "",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_session(
    request: CreateSessionRequest,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """Create a new chat session."""
    session = await use_case.create_session(request)
    return use_case.session_to_response(session)


@router.get(
    "",
    response_model=SessionListResponse,
)
async def list_sessions(
    limit: int = 20,
    offset: int = 0,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """List recent chat sessions."""
    sessions = await use_case.list_sessions(limit=limit, offset=offset)
    return use_case.sessions_to_response(sessions)


@router.get(
    "/{session_id}",
    response_model=SessionResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
    },
)
async def get_session(
    session_id: str,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """Get session by ID."""
    session = await use_case.get_session(session_id)

    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )

    return use_case.session_to_response(session)


@router.delete(
    "/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_session(
    session_id: str,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """Delete a chat session."""
    result = await use_case.delete_session(session_id)

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Session not found: {session_id}",
        )


@router.get(
    "/{session_id}/messages",
    response_model=list[ChatMessageResponse],
)
async def get_session_messages(
    session_id: str,
    limit: int = 50,
    store=Depends(get_sess_store),
):
    """Get messages for a session."""
    messages = await store.get_messages(session_id, limit=limit)

    return [
        ChatMessageResponse(
            id=msg.id,
            role=msg.role.value,
            content=msg.content,
            created_at=msg.created_at,
            context_used=msg.context_used,
        )
        for msg in messages
    ]


@router.get(
    "/{session_id}/summary",
)
async def get_session_summary(
    session_id: str,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """Generate a summary of the session."""
    summary = await use_case.get_session_summary(session_id)
    return {"session_id": session_id, "summary": summary}
