"""
Search endpoints.
"""

from typing import Any

from fastapi import APIRouter, Depends

from src.api.dependencies import get_search_documents_use_case
from src.application.dto.requests import SearchRequest
from src.application.dto.responses import SearchResponse
from src.application.use_cases import SearchDocumentsUseCase

router = APIRouter(prefix="/api/search", tags=["search"])


@router.post(
    "",
    response_model=SearchResponse,
)
async def search_documents(
    request: SearchRequest,
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_use_case),
) -> SearchResponse:
    """
    Search indexed documents.

    Supports hybrid, semantic, and keyword search modes
    with optional reranking.
    """
    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.get(
    "/quick",
    response_model=SearchResponse,
)
async def quick_search(
    q: str,
    top_k: int = 5,
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_use_case),
) -> SearchResponse:
    """
    Quick search with GET request.

    Convenience endpoint for simple searches.
    """
    request = SearchRequest(
        query=q,
        top_k=top_k,
        search_type="hybrid",
        use_reranker=True,
    )

    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.post(
    "/semantic",
    response_model=SearchResponse,
)
async def semantic_search(
    request: SearchRequest,
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_use_case),
) -> SearchResponse:
    """
    Pure semantic (vector) search.

    Uses embeddings for similarity matching.
    """
    request.search_type = "semantic"
    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.post(
    "/keyword",
    response_model=SearchResponse,
)
async def keyword_search(
    request: SearchRequest,
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_use_case),
) -> SearchResponse:
    """
    Keyword (FTS5) search.

    Uses full-text search with BM25 ranking.
    """
    request.search_type = "keyword"
    request.use_reranker = False  # Reranker less useful for keyword search
    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.get(
    "/cache/stats",
)
async def get_cache_stats(
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_use_case),
) -> dict[str, Any]:
    """Get search cache statistics."""
    return use_case.get_cache_stats()


@router.post(
    "/cache/invalidate",
)
async def invalidate_cache(
    use_case: SearchDocumentsUseCase = Depends(get_search_documents_use_case),
) -> dict[str, str]:
    """Clear search cache."""
    use_case.invalidate_cache()
    return {"status": "cache_invalidated"}
