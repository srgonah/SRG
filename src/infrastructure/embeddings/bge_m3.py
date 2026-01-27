"""
BGE-M3 embedding provider implementation.

Provides dense embeddings using sentence-transformers.
"""

from typing import Any

import numpy as np

from src.config import get_logger, get_settings
from src.core.exceptions import EmbeddingError
from src.core.interfaces import IEmbeddingProvider

logger = get_logger(__name__)

# Try to import sentence-transformers
try:
    from sentence_transformers import SentenceTransformer

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    SentenceTransformer = None  # type: ignore[misc, assignment]


class BGEM3EmbeddingProvider(IEmbeddingProvider):
    """
    BGE-M3 embedding provider using sentence-transformers.

    Provides multilingual dense embeddings optimized for retrieval.
    """

    def __init__(self) -> None:
        if not SENTENCE_TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "sentence-transformers not installed. "
                "Install with: pip install sentence-transformers"
            )

        settings = get_settings()
        self.model_name = settings.embedding.model_name
        self.dimension = settings.embedding.dimension
        self.batch_size = settings.embedding.batch_size
        self.device = settings.embedding.device
        self.normalize = settings.embedding.normalize

        self._model: Any = None

    def _load_model(self) -> None:
        """Load the model if not already loaded."""
        if self._model is not None:
            return

        logger.info("loading_embedding_model", model=self.model_name, device=self.device)

        try:
            self._model = SentenceTransformer(
                self.model_name,
                device=self.device,
            )
            logger.info("embedding_model_loaded", model=self.model_name)
        except Exception as e:
            # Fall back to CPU
            logger.warning("gpu_fallback", error=str(e))
            self._model = SentenceTransformer(
                self.model_name,
                device="cpu",
            )
            self.device = "cpu"

    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        self._load_model()

        if not text or not text.strip():
            return np.zeros(self.dimension, dtype=np.float32)

        try:
            assert self._model is not None
            embedding = self._model.encode(
                text,
                normalize_embeddings=self.normalize,
                show_progress_bar=False,
            )
            return np.asarray(embedding, dtype=np.float32)

        except Exception as e:
            logger.error("embedding_error", text_len=len(text), error=str(e))
            raise EmbeddingError(str(e))

    def embed_batch(
        self,
        texts: list[str],
        batch_size: int | None = None,
    ) -> np.ndarray:
        """Generate embeddings for multiple texts."""
        self._load_model()

        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32)

        batch_size = batch_size or self.batch_size

        # Filter empty texts
        valid_texts = []
        valid_indices = []
        for i, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(i)

        if not valid_texts:
            return np.zeros((len(texts), self.dimension), dtype=np.float32)

        try:
            logger.info(
                "embedding_batch",
                total=len(texts),
                valid=len(valid_texts),
                batch_size=batch_size,
            )

            assert self._model is not None
            embeddings = self._model.encode(
                valid_texts,
                batch_size=batch_size,
                normalize_embeddings=self.normalize,
                show_progress_bar=len(valid_texts) > 100,
            )

            # Create full result array with zeros for empty texts
            result = np.zeros((len(texts), self.dimension), dtype=np.float32)
            for i, idx in enumerate(valid_indices):
                result[idx] = embeddings[i]

            return result.astype(np.float32)

        except Exception as e:
            logger.error("batch_embedding_error", count=len(texts), error=str(e))
            raise EmbeddingError(str(e))

    def get_dimension(self) -> int:
        """Get the embedding dimension."""
        return self.dimension

    def is_loaded(self) -> bool:
        """Check if the model is loaded."""
        return self._model is not None


# Singleton
_embedding_provider: BGEM3EmbeddingProvider | None = None


def get_embedding_provider() -> BGEM3EmbeddingProvider:
    """Get or create the embedding provider singleton."""
    global _embedding_provider
    if _embedding_provider is None:
        _embedding_provider = BGEM3EmbeddingProvider()
    return _embedding_provider


def reset_embedding_provider() -> None:
    """Reset the embedding provider (for testing)."""
    global _embedding_provider
    _embedding_provider = None
