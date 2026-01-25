"""
Search Documents Use Case.

Handles document search with various modes.
"""

import time
from dataclasses import dataclass

from src.application.dto.requests import SearchRequest
from src.application.dto.responses import SearchResponse, SearchResultResponse
from src.application.services import get_search_service
from src.config import get_logger
from src.core.entities.document import SearchResult
from src.core.services import SearchContext, SearchService

logger = get_logger(__name__)


@dataclass
class SearchResultDTO:
    """Search result data transfer object."""

    query: str
    results: list[SearchResult]
    search_type: str
    took_ms: float


class SearchDocumentsUseCase:
    """
    Use case for searching documents.

    Supports hybrid, semantic, and keyword search
    with optional reranking.
    """

    def __init__(self, search_service: SearchService | None = None):
        self._search = search_service

    def _get_search(self) -> SearchService:
        if self._search is None:
            self._search = get_search_service()
        return self._search

    async def execute(self, request: SearchRequest) -> SearchResultDTO:
        """
        Execute search use case.

        Args:
            request: Search request parameters

        Returns:
            SearchResultDTO with results and timing
        """
        logger.info(
            "search_started",
            query=request.query[:50],
            type=request.search_type,
        )

        start = time.time()

        search = self._get_search()
        results = await search.search(
            query=request.query,
            top_k=request.top_k,
            search_type=request.search_type,
            use_reranker=request.use_reranker,
            filters=request.filters,
        )

        took_ms = (time.time() - start) * 1000

        logger.info(
            "search_complete",
            query=request.query[:50],
            results=len(results),
            took_ms=took_ms,
        )

        return SearchResultDTO(
            query=request.query,
            results=results,
            search_type=request.search_type,
            took_ms=took_ms,
        )

    async def search_for_rag(
        self,
        query: str,
        top_k: int = 5,
        max_context_length: int = 4000,
    ) -> SearchContext:
        """
        Search and prepare context for RAG.

        Returns formatted context suitable for LLM prompt.
        """
        search = self._get_search()
        return await search.search_for_rag(
            query=query,
            top_k=top_k,
            max_context_length=max_context_length,
        )

    def to_response(self, result: SearchResultDTO) -> SearchResponse:
        """Convert to API response format."""
        return SearchResponse(
            query=result.query,
            results=[
                SearchResultResponse(
                    chunk_id=r.chunk_id,
                    document_id=r.document_id,
                    content=r.content,
                    score=r.score,
                    metadata=r.metadata,
                    page_number=r.metadata.get("page_number"),
                    file_name=r.metadata.get("file_name"),
                )
                for r in result.results
            ],
            total=len(result.results),
            search_type=result.search_type,
            took_ms=result.took_ms,
        )

    def invalidate_cache(self) -> None:
        """Clear search cache."""
        search = self._get_search()
        search.invalidate_cache()

    def get_cache_stats(self) -> dict:
        """Get cache statistics."""
        search = self._get_search()
        return search.cache_stats()
