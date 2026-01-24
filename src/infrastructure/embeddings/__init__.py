"""Embedding infrastructure implementations."""

from src.core.interfaces.llm import IEmbeddingProvider
from src.infrastructure.embeddings.bge_m3 import (
    SENTENCE_TRANSFORMERS_AVAILABLE,
    BGEM3EmbeddingProvider,
    get_embedding_provider,
    reset_embedding_provider,
)

__all__ = [
    "IEmbeddingProvider",
    "BGEM3EmbeddingProvider",
    "get_embedding_provider",
    "reset_embedding_provider",
    "SENTENCE_TRANSFORMERS_AVAILABLE",
]
