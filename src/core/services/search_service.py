"""
Search service for RAG orchestration.

Coordinates hybrid search, reranking, and context preparation.
"""

from dataclasses import dataclass

from src.config import get_logger, get_settings
from src.core.entities.document import SearchResult
from src.core.exceptions import SearchError
from src.infrastructure.cache import SearchCache, get_search_cache
from src.infrastructure.search import (
    HybridSearcher,
    Reranker,
    get_hybrid_searcher,
    get_reranker,
    is_reranker_enabled,
)

logger = get_logger(__name__)


@dataclass
class SearchContext:
    """Context prepared for RAG."""

    query: str
    results: list[SearchResult]
    formatted_context: str
    total_chunks: int
    search_type: str


class SearchService:
    """
    RAG-oriented search service.

    Combines hybrid search with reranking and
    prepares context for LLM consumption.
    """

    def __init__(
        self,
        searcher: HybridSearcher | None = None,
        reranker: Reranker | None = None,
        cache: SearchCache | None = None,
    ):
        """
        Initialize search service.

        Args:
            searcher: Optional custom hybrid searcher
            reranker: Optional custom reranker
            cache: Optional custom search cache
        """
        self._searcher = searcher
        self._reranker = reranker
        self._cache = cache
        self._settings = get_settings()

    def _get_searcher(self) -> HybridSearcher:
        """Lazy load searcher."""
        if self._searcher is None:
            self._searcher = get_hybrid_searcher()
        return self._searcher

    def _get_reranker(self) -> Reranker | None:
        """Lazy load reranker if enabled."""
        if self._reranker is None and is_reranker_enabled():
            self._reranker = get_reranker()
        return self._reranker

    def _get_cache(self) -> SearchCache:
        """Lazy load cache."""
        if self._cache is None:
            self._cache = get_search_cache()
        return self._cache

    async def search(
        self,
        query: str,
        top_k: int = 5,
        search_type: str = "hybrid",
        use_cache: bool = True,
        use_reranker: bool = True,
        filters: dict | None = None,
    ) -> list[SearchResult]:
        """
        Perform search with optional caching and reranking.

        Args:
            query: Search query
            top_k: Number of results to return
            search_type: "hybrid", "semantic", or "keyword"
            use_cache: Whether to use cache
            use_reranker: Whether to apply reranking
            filters: Optional metadata filters

        Returns:
            List of SearchResult entities
        """
        if not query or not query.strip():
            return []

        query = query.strip()
        cache = self._get_cache()

        # Check cache
        if use_cache:
            cached = cache.get(
                query=query,
                search_type=search_type,
                top_k=top_k,
                filters=str(filters) if filters else "",
            )
            if cached:
                logger.debug("search_cache_hit", query=query[:50])
                return cached

        logger.info(
            "executing_search",
            query=query[:100],
            top_k=top_k,
            search_type=search_type,
        )

        try:
            searcher = self._get_searcher()

            # Get more results if reranking
            fetch_k = top_k * 3 if use_reranker and is_reranker_enabled() else top_k

            # Execute search
            results = await searcher.search(
                query=query,
                top_k=fetch_k,
                search_type=search_type,
            )

            # Apply reranking if enabled
            if use_reranker and results and is_reranker_enabled():
                results = await self._apply_reranking(query, results, top_k)
            else:
                results = results[:top_k]

            # Apply filters if provided
            if filters:
                results = self._apply_filters(results, filters)

            # Cache results
            if use_cache and results:
                cache.set(
                    query=query,
                    search_type=search_type,
                    top_k=top_k,
                    results=results,
                    filters=str(filters) if filters else "",
                )

            logger.info(
                "search_complete",
                query=query[:50],
                results=len(results),
            )

            return results

        except Exception as e:
            logger.error("search_failed", query=query[:50], error=str(e))
            raise SearchError(f"Search failed: {str(e)}")

    async def _apply_reranking(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Apply reranking to search results."""
        reranker = self._get_reranker()
        if not reranker:
            return results[:top_k]

        try:
            # Extract texts for reranking
            texts = [r.content for r in results]

            # Rerank
            ranked = await reranker.rerank(query, texts, top_k=top_k)

            # Reorder results based on reranking
            reranked_results = []
            for idx, score in ranked:
                result = results[idx]
                # Update score with reranker score
                result.score = score
                reranked_results.append(result)

            logger.debug(
                "reranking_applied",
                original=len(results),
                reranked=len(reranked_results),
            )

            return reranked_results

        except Exception as e:
            logger.warning("reranking_failed", error=str(e))
            return results[:top_k]

    def _apply_filters(
        self,
        results: list[SearchResult],
        filters: dict,
    ) -> list[SearchResult]:
        """Apply metadata filters to results."""
        filtered = []

        for result in results:
            match = True

            for key, value in filters.items():
                result_value = result.metadata.get(key)

                if isinstance(value, list):
                    if result_value not in value:
                        match = False
                        break
                elif result_value != value:
                    match = False
                    break

            if match:
                filtered.append(result)

        return filtered

    async def search_for_rag(
        self,
        query: str,
        top_k: int = 5,
        max_context_length: int = 4000,
    ) -> SearchContext:
        """
        Search and prepare context for RAG.

        Args:
            query: User query
            top_k: Number of chunks to retrieve
            max_context_length: Maximum context length in chars

        Returns:
            SearchContext with formatted context for LLM
        """
        results = await self.search(
            query=query,
            top_k=top_k,
            search_type="hybrid",
            use_reranker=True,
        )

        # Format context
        context_parts = []
        total_length = 0

        for i, result in enumerate(results):
            chunk_text = f"[{i + 1}] {result.content}"

            if total_length + len(chunk_text) > max_context_length:
                # Truncate if needed
                remaining = max_context_length - total_length
                if remaining > 100:
                    chunk_text = chunk_text[:remaining] + "..."
                    context_parts.append(chunk_text)
                break

            context_parts.append(chunk_text)
            total_length += len(chunk_text) + 2  # +2 for newlines

        formatted = "\n\n".join(context_parts)

        return SearchContext(
            query=query,
            results=results,
            formatted_context=formatted,
            total_chunks=len(results),
            search_type="hybrid",
        )

    async def find_similar_documents(
        self,
        document_id: str,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Find documents similar to a given document.

        Args:
            document_id: ID of reference document
            top_k: Number of similar documents

        Returns:
            List of similar documents
        """
        # TODO: Implement document-level similarity
        # This would require aggregating chunk embeddings
        logger.warning("find_similar_documents not fully implemented")
        return []

    def invalidate_cache(self) -> None:
        """Clear search cache."""
        cache = self._get_cache()
        cache.invalidate()
        logger.info("search_cache_invalidated")

    def cache_stats(self) -> dict:
        """Get cache statistics."""
        cache = self._get_cache()
        return cache.stats()


# Singleton
_search_service: SearchService | None = None


def get_search_service() -> SearchService:
    """Get or create search service singleton."""
    global _search_service
    if _search_service is None:
        _search_service = SearchService()
    return _search_service
