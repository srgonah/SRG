"""
Search service for RAG orchestration.

Layer-pure service coordinating hybrid search, reranking, and context preparation.
NO infrastructure imports - depends only on core entities, interfaces, exceptions.
"""

from dataclasses import dataclass
from typing import Any

from src.core.entities.document import SearchResult
from src.core.exceptions import SearchError
from src.core.interfaces import IHybridSearcher, IReranker, ISearchCache


@dataclass
class SearchContext:
    """Context prepared for RAG consumption."""

    query: str
    results: list[SearchResult]
    formatted_context: str
    total_chunks: int
    search_type: str


class SearchService:
    """
    RAG-oriented search service.

    Combines hybrid search with optional reranking and caching.
    Prepares context for LLM consumption.

    Required interfaces for DI:
    - IHybridSearcher: Hybrid search implementation
    - IReranker: Optional result reranking
    - ISearchCache: Optional result caching
    """

    def __init__(
        self,
        searcher: IHybridSearcher,
        reranker: IReranker | None = None,
        cache: ISearchCache | None = None,
    ):
        """
        Initialize search service with injected dependencies.

        Args:
            searcher: Hybrid search implementation (required)
            reranker: Optional reranker for improved relevance
            cache: Optional search cache
        """
        self._searcher = searcher
        self._reranker = reranker
        self._cache = cache

    async def search(
        self,
        query: str,
        top_k: int = 5,
        search_type: str = "hybrid",
        use_cache: bool = True,
        use_reranker: bool = True,
        filters: dict[str, Any] | None = None,
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

        Raises:
            SearchError: If search fails
        """
        if not query or not query.strip():
            return []

        query = query.strip()

        # Check cache
        if use_cache and self._cache:
            cached = self._cache.get(
                query=query,
                search_type=search_type,
                top_k=top_k,
                filters=str(filters) if filters else "",
            )
            if cached:
                return cached

        try:
            # Get more results if reranking
            reranker_enabled = self._reranker and self._reranker.is_enabled()
            fetch_k = top_k * 3 if use_reranker and reranker_enabled else top_k

            # Execute search
            results = await self._searcher.search(
                query=query,
                top_k=fetch_k,
                search_type=search_type,
                filters=filters,
            )

            # Apply reranking if enabled
            if use_reranker and results and reranker_enabled:
                results = await self._apply_reranking(query, results, top_k)
            else:
                results = results[:top_k]

            # Apply additional filters if provided
            if filters:
                results = self._apply_filters(results, filters)

            # Cache results
            if use_cache and self._cache and results:
                self._cache.set(
                    query=query,
                    search_type=search_type,
                    top_k=top_k,
                    results=results,
                    filters=str(filters) if filters else "",
                )

            return results

        except Exception as e:
            raise SearchError(f"Search failed: {str(e)}")

    async def search_items(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Search invoice line items.

        Args:
            query: Search query
            top_k: Number of results
            filters: Optional filters

        Returns:
            List of item SearchResults
        """
        if not query or not query.strip():
            return []

        try:
            return await self._searcher.search_items(
                query=query.strip(),
                top_k=top_k,
                filters=filters,
            )
        except Exception as e:
            raise SearchError(f"Item search failed: {str(e)}")

    async def _apply_reranking(
        self,
        query: str,
        results: list[SearchResult],
        top_k: int,
    ) -> list[SearchResult]:
        """Apply reranking to search results."""
        if not self._reranker:
            return results[:top_k]

        try:
            # Extract texts for reranking
            texts = [r.text for r in results]

            # Rerank
            ranked = await self._reranker.rerank(query, texts, top_k=top_k)

            # Reorder results based on reranking
            reranked_results = []
            for idx, score in ranked:
                if idx < len(results):
                    result = results[idx]
                    result.reranker_score = score
                    result.final_score = score
                    reranked_results.append(result)

            # Update final ranks
            for i, result in enumerate(reranked_results):
                result.final_rank = i

            return reranked_results

        except Exception:
            # Graceful degradation - return original results
            return results[:top_k]

    def _apply_filters(
        self,
        results: list[SearchResult],
        filters: dict[str, Any],
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
            chunk_text = f"[{i + 1}] {result.text}"

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

    async def find_similar_chunks(
        self,
        chunk_id: int,
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Find chunks similar to a given chunk.

        Args:
            chunk_id: ID of reference chunk
            top_k: Number of similar chunks

        Returns:
            List of similar chunks
        """
        # This would require getting the chunk's embedding first
        # Implementation depends on having chunk text available
        return []

    def invalidate_cache(self) -> None:
        """Clear search cache."""
        if self._cache:
            self._cache.invalidate()

    def cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        if self._cache:
            return self._cache.stats()
        return {"enabled": False}
