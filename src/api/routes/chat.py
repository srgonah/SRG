"""
Chat endpoints.
"""

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from src.api.dependencies import get_chat_use_case
from src.application.dto.requests import ChatRequest
from src.application.dto.responses import ChatResponse, ErrorResponse
from src.application.use_cases import ChatWithContextUseCase

router = APIRouter(prefix="/api/chat", tags=["chat"])


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def chat(
    request: ChatRequest,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """
    Send a chat message.

    Uses RAG to retrieve relevant context before generating response.
    Creates a new session if session_id not provided.
    """
    if request.stream:
        # Redirect to streaming endpoint
        return await chat_stream(request, use_case)

    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.post(
    "/stream",
)
async def chat_stream(
    request: ChatRequest,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """
    Stream a chat response.

    Returns Server-Sent Events with response chunks.
    """

    async def generate():
        try:
            async for chunk in use_case.stream(request):
                yield f"data: {chunk}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


@router.get(
    "/context",
)
async def get_context_for_query(
    query: str,
    top_k: int = 5,
    use_case: ChatWithContextUseCase = Depends(get_chat_use_case),
):
    """
    Get context that would be used for a query.

    Useful for debugging and understanding RAG behavior.
    """
    from src.application.use_cases.search_documents import SearchDocumentsUseCase

    search_use_case = SearchDocumentsUseCase()
    context = await search_use_case.search_for_rag(
        query=query,
        top_k=top_k,
    )

    return {
        "query": query,
        "context": context.formatted_context,
        "chunks": context.total_chunks,
    }
