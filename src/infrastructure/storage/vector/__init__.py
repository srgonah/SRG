"""Vector storage implementations."""

from src.infrastructure.storage.vector.faiss_store import (
    FAISS_AVAILABLE,
    FAISSVectorStore,
    get_vector_store,
    reset_vector_store,
)

# Aliases for backward compatibility
get_faiss_store = get_vector_store
FAISSStore = FAISSVectorStore

__all__ = [
    "FAISSVectorStore",
    "FAISSStore",
    "get_vector_store",
    "get_faiss_store",
    "reset_vector_store",
    "FAISS_AVAILABLE",
]
