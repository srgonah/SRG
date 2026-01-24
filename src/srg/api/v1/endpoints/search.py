"""Search endpoints."""

from fastapi import APIRouter

from src.application.dto.requests import SearchRequest as SearchRequestDTO
from src.application.use_cases import SearchDocumentsUseCase
from src.srg.schemas.search import SearchRequest, SearchResponse

router = APIRouter()


@router.post("", response_model=SearchResponse)
async def search_documents(request: SearchRequest):
    """Search indexed documents using hybrid search."""
    use_case = SearchDocumentsUseCase()
    dto = SearchRequestDTO(
        query=request.query,
        top_k=request.top_k,
        search_type=request.search_type,
        use_reranker=request.use_reranker,
        filters=request.filters,
    )

    result = await use_case.execute(dto)
    return use_case.to_response(result)


@router.get("/quick", response_model=SearchResponse)
async def quick_search(q: str, top_k: int = 5):
    """Quick search with GET request."""
    use_case = SearchDocumentsUseCase()
    dto = SearchRequestDTO(
        query=q,
        top_k=top_k,
        search_type="hybrid",
        use_reranker=True,
    )

    result = await use_case.execute(dto)
    return use_case.to_response(result)


@router.get("/cache/stats")
async def get_cache_stats():
    """Get search cache statistics."""
    use_case = SearchDocumentsUseCase()
    return use_case.get_cache_stats()


@router.post("/cache/invalidate")
async def invalidate_cache():
    """Clear search cache."""
    use_case = SearchDocumentsUseCase()
    use_case.invalidate_cache()
    return {"status": "cache_invalidated"}
