"""
Hybrid search combining FAISS vector search with FTS5 keyword search.

Uses Reciprocal Rank Fusion (RRF) to merge results from both sources.
"""

from src.config import get_logger, get_settings
from src.core.entities import SearchResult
from src.infrastructure.embeddings import get_embedding_provider
from src.infrastructure.search.fts import get_fts_searcher
from src.infrastructure.search.reranker import get_reranker, is_reranker_enabled
from src.infrastructure.storage.vector import get_vector_store

logger = get_logger(__name__)


def reciprocal_rank_fusion(
    vector_results: list[SearchResult],
    keyword_results: list[SearchResult],
    k: int = 60,
    vector_weight: float = 0.6,
    keyword_weight: float = 0.4,
) -> list[SearchResult]:
    """
    Combine vector and keyword results using Reciprocal Rank Fusion.

    Args:
        vector_results: Results from vector search (ordered by score)
        keyword_results: Results from keyword search (ordered by score)
        k: RRF constant (default 60)
        vector_weight: Weight for vector search (default 0.6)
        keyword_weight: Weight for keyword search (default 0.4)

    Returns:
        Merged results ordered by RRF score
    """
    scores: dict[int, float] = {}
    results_map: dict[int, SearchResult] = {}

    # Process vector results
    for rank, result in enumerate(vector_results):
        id_key = result.chunk_id or result.item_id or 0
        if id_key == 0:
            continue

        rrf_score = vector_weight / (k + rank + 1)
        scores[id_key] = scores.get(id_key, 0.0) + rrf_score
        results_map[id_key] = result

    # Process keyword results
    for rank, result in enumerate(keyword_results):
        id_key = result.chunk_id or result.item_id or 0
        if id_key == 0:
            continue

        rrf_score = keyword_weight / (k + rank + 1)
        scores[id_key] = scores.get(id_key, 0.0) + rrf_score

        # Keep the richer result
        if id_key not in results_map:
            results_map[id_key] = result

    # Sort by RRF score
    sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)

    # Build final results
    merged = []
    for rank, id_key in enumerate(sorted_ids):
        result = results_map[id_key]
        result.hybrid_score = scores[id_key]
        result.final_score = scores[id_key]
        result.final_rank = rank
        merged.append(result)

    return merged


class HybridSearcher:
    """
    Hybrid searcher combining vector and keyword search.

    Pipeline:
    1. Vector search via FAISS
    2. Keyword search via FTS5
    3. RRF fusion
    4. Optional reranking
    """

    def __init__(self):
        self.settings = get_settings()

    async def search_chunks(
        self,
        query: str,
        top_k: int = 10,
        use_hybrid: bool = True,
        use_reranker: bool = True,
    ) -> list[SearchResult]:
        """
        Search document chunks with hybrid approach.

        Args:
            query: Search query
            top_k: Final number of results
            use_hybrid: Use both vector and keyword search
            use_reranker: Apply reranking to results

        Returns:
            List of SearchResult ordered by relevance
        """
        candidates = self.settings.search.faiss_candidates

        # Vector search
        vector_store = get_vector_store()
        embedder = get_embedding_provider()

        try:
            query_vec = embedder.embed_single(query)
            vector_ids_scores = await vector_store.search("chunks", query_vec, candidates)

            vector_results = [
                SearchResult(
                    chunk_id=id_,
                    faiss_score=score,
                    faiss_rank=rank,
                )
                for rank, (id_, score) in enumerate(vector_ids_scores)
            ]
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))
            vector_results = []

        if not use_hybrid:
            return vector_results[:top_k]

        # Keyword search
        fts = get_fts_searcher()
        try:
            keyword_results = await fts.search_chunks(query, candidates)
        except Exception as e:
            logger.warning("keyword_search_failed", error=str(e))
            keyword_results = []

        # RRF fusion
        merged = reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=self.settings.search.rrf_k,
        )

        # Reranking
        if use_reranker and is_reranker_enabled() and merged:
            reranker = get_reranker()
            texts = [r.text for r in merged[:candidates]]

            reranked = await reranker.rerank(query, texts, top_k)

            results = []
            for final_rank, (orig_idx, score) in enumerate(reranked):
                result = merged[orig_idx]
                result.reranker_score = score
                result.final_score = score
                result.final_rank = final_rank
                results.append(result)

            return results

        return merged[:top_k]

    async def search_items(
        self,
        query: str,
        top_k: int = 20,
        use_hybrid: bool = True,
        use_reranker: bool = False,
    ) -> list[SearchResult]:
        """
        Search invoice items with hybrid approach.

        Args:
            query: Search query
            top_k: Final number of results
            use_hybrid: Use both vector and keyword search
            use_reranker: Apply reranking to results

        Returns:
            List of SearchResult ordered by relevance
        """
        candidates = self.settings.search.faiss_candidates

        # Vector search
        vector_store = get_vector_store()
        embedder = get_embedding_provider()

        try:
            query_vec = embedder.embed_single(query)
            vector_ids_scores = await vector_store.search("items", query_vec, candidates)

            vector_results = [
                SearchResult(
                    item_id=id_,
                    faiss_score=score,
                    faiss_rank=rank,
                )
                for rank, (id_, score) in enumerate(vector_ids_scores)
            ]
        except Exception as e:
            logger.warning("vector_search_failed", error=str(e))
            vector_results = []

        if not use_hybrid:
            return vector_results[:top_k]

        # Keyword search
        fts = get_fts_searcher()
        try:
            keyword_results = await fts.search_items(query, candidates)
        except Exception as e:
            logger.warning("keyword_search_failed", error=str(e))
            keyword_results = []

        # RRF fusion
        merged = reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=self.settings.search.rrf_k,
        )

        # Reranking (optional for items)
        if use_reranker and is_reranker_enabled() and merged:
            reranker = get_reranker()
            texts = [r.item_name or r.text for r in merged[:candidates]]

            reranked = await reranker.rerank(query, texts, top_k)

            results = []
            for final_rank, (orig_idx, score) in enumerate(reranked):
                result = merged[orig_idx]
                result.reranker_score = score
                result.final_score = score
                result.final_rank = final_rank
                results.append(result)

            return results

        return merged[:top_k]

    async def search(
        self,
        query: str,
        top_k: int = 10,
        search_type: str = "hybrid",
        use_reranker: bool = True,
    ) -> list[SearchResult]:
        """
        Universal search method that routes to appropriate searcher.

        Args:
            query: Search query
            top_k: Number of results
            search_type: 'vector', 'keyword', 'hybrid', or 'items'
            use_reranker: Apply reranking

        Returns:
            List of SearchResult
        """
        if search_type == "items":
            return await self.search_items(
                query=query,
                top_k=top_k,
                use_hybrid=True,
                use_reranker=use_reranker,
            )

        use_hybrid = search_type == "hybrid"
        return await self.search_chunks(
            query=query,
            top_k=top_k,
            use_hybrid=use_hybrid,
            use_reranker=use_reranker,
        )


# Singleton
_hybrid_searcher: HybridSearcher | None = None


def get_hybrid_searcher() -> HybridSearcher:
    """Get or create hybrid searcher singleton."""
    global _hybrid_searcher
    if _hybrid_searcher is None:
        _hybrid_searcher = HybridSearcher()
    return _hybrid_searcher
