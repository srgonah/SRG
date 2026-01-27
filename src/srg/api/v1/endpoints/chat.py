"""Chat endpoints."""

from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from src.application.dto.requests import ChatRequest as ChatRequestDTO
from src.application.dto.responses import ChatResponse as ChatResponseDTO
from src.application.use_cases import ChatWithContextUseCase
from src.srg.schemas.chat import ChatRequest, ChatResponse

router = APIRouter()


@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest) -> ChatResponseDTO | StreamingResponse:
    """Send a chat message with RAG context."""
    use_case = ChatWithContextUseCase()
    dto = ChatRequestDTO(
        message=request.message,
        session_id=request.session_id,
        use_rag=request.use_rag,
        top_k=request.top_k,
        stream=request.stream,
    )

    if request.stream:
        return await chat_stream(request)

    result = await use_case.execute(dto)
    return use_case.to_response(result)


@router.post("/stream")
async def chat_stream(request: ChatRequest) -> StreamingResponse:
    """Stream a chat response using SSE."""
    use_case = ChatWithContextUseCase()
    dto = ChatRequestDTO(
        message=request.message,
        session_id=request.session_id,
        use_rag=request.use_rag,
        top_k=request.top_k,
    )

    async def generate() -> AsyncIterator[str]:
        try:
            async for chunk in use_case.stream(dto):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.get("/context")
async def get_context_for_query(query: str, top_k: int = 5) -> dict[str, Any]:
    """Get RAG context for debugging."""
    from src.application.use_cases import SearchDocumentsUseCase

    use_case = SearchDocumentsUseCase()
    context = await use_case.search_for_rag(query=query, top_k=top_k)

    return {
        "query": query,
        "context": context.formatted_context,
        "chunks": context.total_chunks,
    }
