"""
BGE-Reranker integration for result re-ranking.

Improves search precision by re-scoring candidate results.
"""

from typing import Any

from src.config import get_logger, get_settings

logger = get_logger(__name__)

# Try to import sentence-transformers for reranking
try:
    from sentence_transformers import CrossEncoder

    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    CrossEncoder = None  # type: ignore[misc]


class Reranker:
    """
    BGE-Reranker for search result re-scoring.

    Uses a cross-encoder model to compute relevance scores
    between query and documents.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.model_name = settings.search.reranker_model
        self.top_k = settings.search.reranker_top_k
        self._enabled = settings.search.reranker_enabled
        self._model: Any = None

    def is_enabled(self) -> bool:
        """Check if reranker is enabled and available."""
        return self._enabled and RERANKER_AVAILABLE

    def _load_model(self) -> None:
        """Load the reranker model if not already loaded."""
        if self._model is not None:
            return

        if not RERANKER_AVAILABLE:
            logger.warning("reranker_not_available")
            return

        logger.info("loading_reranker", model=self.model_name)

        try:
            self._model = CrossEncoder(
                self.model_name,
                max_length=512,
            )
            logger.info("reranker_loaded", model=self.model_name)
        except Exception as e:
            logger.error("reranker_load_failed", error=str(e))
            self._model = None

    async def rerank(
        self,
        query: str,
        documents: list[str],
        top_k: int | None = None,
    ) -> list[tuple[int, float]]:
        """
        Rerank documents by relevance to query.

        Args:
            query: Search query
            documents: List of document texts
            top_k: Number of top results to return

        Returns:
            List of (original_index, score) tuples, sorted by score descending
        """
        if not documents:
            return []

        top_k = top_k or self.top_k

        self._load_model()

        if self._model is None:
            # Fallback: return original order with dummy scores
            return [(i, 1.0 - i * 0.01) for i in range(min(top_k, len(documents)))]

        try:
            # Create query-document pairs
            pairs = [[query, doc] for doc in documents]

            # Score all pairs
            scores = self._model.predict(pairs)

            # Create indexed scores
            indexed = [(i, float(score)) for i, score in enumerate(scores)]

            # Sort by score descending
            indexed.sort(key=lambda x: x[1], reverse=True)

            logger.debug(
                "rerank_complete",
                query_len=len(query),
                docs=len(documents),
                top_score=indexed[0][1] if indexed else 0,
            )

            return indexed[:top_k]

        except Exception as e:
            logger.error("rerank_failed", error=str(e))
            # Fallback: return original order
            return [(i, 1.0 - i * 0.01) for i in range(min(top_k, len(documents)))]


# Singleton
_reranker: Reranker | None = None


def get_reranker() -> Reranker:
    """Get or create reranker singleton."""
    global _reranker
    if _reranker is None:
        _reranker = Reranker()
    return _reranker


def is_reranker_enabled() -> bool:
    """Check if reranker is enabled in settings."""
    settings = get_settings()
    return settings.search.reranker_enabled and RERANKER_AVAILABLE
