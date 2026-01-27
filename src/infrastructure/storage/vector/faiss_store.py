"""
FAISS vector store implementation.

Manages FAISS indexes for document chunks and invoice items.
Supports both CPU and GPU backends.
"""

import asyncio
from pathlib import Path
from typing import Any

import numpy as np

from src.config import get_logger, get_settings
from src.core.exceptions import IndexNotReadyError
from src.core.interfaces import IVectorStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)

# Try to import faiss
try:
    import faiss

    FAISS_AVAILABLE = True
except ImportError:
    FAISS_AVAILABLE = False
    faiss = None


class FAISSVectorStore(IVectorStore):
    """
    FAISS-based vector store implementation.

    Manages two indexes:
    - chunks: Document chunks for RAG
    - items: Invoice line items for search
    """

    def __init__(self, use_gpu: bool = False):
        if not FAISS_AVAILABLE:
            raise ImportError(
                "faiss not installed. Install with: pip install faiss-cpu (or faiss-gpu)"
            )

        self.settings = get_settings()
        self.use_gpu = use_gpu and self._check_gpu()

        self._indexes: dict[str, faiss.Index] = {}
        self._index_paths = {
            "chunks": self.settings.storage.chunks_index_path,
            "items": self.settings.storage.items_index_path,
        }

    def _check_gpu(self) -> bool:
        """Check if GPU is available."""
        try:
            return bool(faiss.get_num_gpus() > 0)
        except Exception:
            return False

    def _get_index(self, index_name: str) -> faiss.Index | None:
        """Get an index by name, loading from disk if needed."""
        if index_name in self._indexes:
            return self._indexes[index_name]

        # Try to load from disk
        path = self._index_paths.get(index_name)
        if path and path.exists():
            try:
                index = faiss.read_index(str(path))
                if self.use_gpu:
                    index = faiss.index_cpu_to_gpu(faiss.StandardGpuResources(), 0, index)
                self._indexes[index_name] = index
                logger.info("index_loaded", index_name=index_name, size=index.ntotal)
                return index
            except Exception as e:
                logger.error("index_load_failed", index_name=index_name, error=str(e))

        return None

    async def build_index(
        self,
        index_name: str,
        embeddings: np.ndarray,
        ids: list[int],
        force_rebuild: bool = False,
    ) -> bool:
        """Build or rebuild a FAISS index."""
        path = self._index_paths.get(index_name)
        if not path:
            raise ValueError(f"Unknown index: {index_name}")

        if path.exists() and not force_rebuild:
            logger.info("index_exists_skipping", index_name=index_name)
            return True

        if len(embeddings) == 0:
            logger.warning("no_embeddings_to_index", index_name=index_name)
            return False

        logger.info(
            "building_index",
            index_name=index_name,
            vectors=len(embeddings),
            dimension=embeddings.shape[1],
        )

        # Create index (IndexFlatIP for cosine similarity with normalized vectors)
        dimension = embeddings.shape[1]
        index = faiss.IndexFlatIP(dimension)

        # Add vectors
        embeddings = embeddings.astype("float32")
        faiss.normalize_L2(embeddings)  # Normalize for cosine similarity
        index.add(embeddings)

        # Save index
        faiss.write_index(index, str(path))
        logger.info("index_saved", index_name=index_name, path=str(path))

        # Store ID mappings
        await self._save_id_mappings(index_name, ids)

        # Cache in memory
        if self.use_gpu:
            index = faiss.index_cpu_to_gpu(faiss.StandardGpuResources(), 0, index)
        self._indexes[index_name] = index

        return True

    async def add_vectors(
        self,
        index_name: str,
        embeddings: np.ndarray,
        ids: list[int],
    ) -> bool:
        """Add vectors to existing index (incremental)."""
        index = self._get_index(index_name)
        if index is None:
            raise IndexNotReadyError(index_name)

        if len(embeddings) == 0:
            return True

        # Get current size for FAISS ID offset
        start_id = index.ntotal

        # Add vectors
        embeddings = embeddings.astype("float32")
        faiss.normalize_L2(embeddings)
        index.add(embeddings)

        # Save ID mappings with offset
        await self._save_id_mappings(index_name, ids, start_faiss_id=start_id)

        # Save updated index
        path = self._index_paths[index_name]
        if self.use_gpu:
            # Convert back to CPU for saving
            cpu_index = faiss.index_gpu_to_cpu(index)
            faiss.write_index(cpu_index, str(path))
        else:
            faiss.write_index(index, str(path))

        logger.info(
            "vectors_added",
            index_name=index_name,
            added=len(embeddings),
            total=index.ntotal,
        )

        return True

    async def search(
        self,
        index_name: str,
        query_vector: np.ndarray,
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """Search index for similar vectors."""
        index = self._get_index(index_name)
        if index is None:
            raise IndexNotReadyError(index_name)

        # Prepare query
        query = query_vector.astype("float32").reshape(1, -1)
        faiss.normalize_L2(query)

        # Search
        k = min(top_k, index.ntotal)
        scores, faiss_ids = index.search(query, k)

        # Get entity IDs
        valid_results = []
        entity_ids = await self.get_entity_ids(
            index_name,
            [int(fid) for fid in faiss_ids[0] if fid >= 0],
        )

        for score, fid in zip(scores[0], faiss_ids[0]):
            if fid < 0:
                continue
            entity_id = entity_ids.get(int(fid))
            if entity_id:
                valid_results.append((entity_id, float(score)))

        return valid_results

    def count(self) -> int:
        """Get total vector count across all indexes."""
        total = 0
        for index in self._indexes.values():
            if index is not None:
                total += index.ntotal
        return total

    async def get_index_stats(self, index_name: str) -> dict[str, Any]:
        """Get index statistics."""
        index = self._get_index(index_name)
        if index is None:
            return {
                "loaded": False,
                "exists": self._index_paths.get(index_name, Path()).exists(),
            }

        return {
            "loaded": True,
            "size": index.ntotal,
            "dimension": index.d,
            "is_gpu": self.use_gpu,
            "path": str(self._index_paths.get(index_name)),
        }

    def save(self) -> None:
        """Save all indexes to disk (synchronous)."""
        for index_name, index in self._indexes.items():
            if index is None:
                continue
            path = self._index_paths.get(index_name)
            if not path:
                continue
            try:
                if self.use_gpu:
                    cpu_index = faiss.index_gpu_to_cpu(index)
                    faiss.write_index(cpu_index, str(path))
                else:
                    faiss.write_index(index, str(path))
                logger.info("index_saved", index_name=index_name)
            except Exception as e:
                logger.warning("index_save_failed", index_name=index_name, error=str(e))

    async def save_index(self, index_name: str) -> bool:
        """Save index to disk."""
        index = self._indexes.get(index_name)
        if index is None:
            return False

        path = self._index_paths.get(index_name)
        if not path:
            return False

        if self.use_gpu:
            cpu_index = faiss.index_gpu_to_cpu(index)
            faiss.write_index(cpu_index, str(path))
        else:
            faiss.write_index(index, str(path))

        logger.info("index_saved", index_name=index_name)
        return True

    async def load_index(self, index_name: str) -> bool:
        """Load index from disk."""
        index = self._get_index(index_name)
        return index is not None

    async def _save_id_mappings(
        self,
        index_name: str,
        entity_ids: list[int],
        start_faiss_id: int = 0,
    ) -> None:
        """Save FAISS ID to entity ID mappings."""
        table = "doc_chunks_faiss_map" if index_name == "chunks" else "line_items_faiss_map"
        id_col = "chunk_id" if index_name == "chunks" else "item_id"

        async with get_transaction() as conn:
            if start_faiss_id == 0:
                # Full rebuild - clear existing mappings
                await conn.execute(f"DELETE FROM {table}")

            for i, entity_id in enumerate(entity_ids):
                faiss_id = start_faiss_id + i
                await conn.execute(
                    f"INSERT OR REPLACE INTO {table} (faiss_id, {id_col}) VALUES (?, ?)",
                    (faiss_id, entity_id),
                )

    async def save_id_mapping(
        self,
        index_name: str,
        faiss_id: int,
        entity_id: int,
    ) -> None:
        """Save a single FAISS ID to entity ID mapping."""
        table = "doc_chunks_faiss_map" if index_name == "chunks" else "line_items_faiss_map"
        id_col = "chunk_id" if index_name == "chunks" else "item_id"

        async with get_transaction() as conn:
            await conn.execute(
                f"INSERT OR REPLACE INTO {table} (faiss_id, {id_col}) VALUES (?, ?)",
                (faiss_id, entity_id),
            )

    async def get_entity_id(
        self,
        index_name: str,
        faiss_id: int,
    ) -> int | None:
        """Get entity ID from FAISS ID."""
        result = await self.get_entity_ids(index_name, [faiss_id])
        return result.get(faiss_id)

    async def get_entity_ids(
        self,
        index_name: str,
        faiss_ids: list[int],
    ) -> dict[int, int]:
        """Get multiple entity IDs from FAISS IDs."""
        if not faiss_ids:
            return {}

        table = "doc_chunks_faiss_map" if index_name == "chunks" else "line_items_faiss_map"
        id_col = "chunk_id" if index_name == "chunks" else "item_id"

        async with get_connection() as conn:
            placeholders = ",".join("?" * len(faiss_ids))
            cursor = await conn.execute(
                f"SELECT faiss_id, {id_col} FROM {table} WHERE faiss_id IN ({placeholders})",
                faiss_ids,
            )
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}


# Singleton
_vector_store: FAISSVectorStore | None = None


def get_vector_store(use_gpu: bool = False) -> FAISSVectorStore:
    """Get or create the global vector store."""
    global _vector_store
    if _vector_store is None:
        _vector_store = FAISSVectorStore(use_gpu=use_gpu)
    return _vector_store


def reset_vector_store() -> None:
    """Reset the global vector store (for testing)."""
    global _vector_store
    _vector_store = None


async def rebuild_indexes() -> None:
    """CLI command to rebuild all indexes."""
    from src.infrastructure.embeddings.bge_m3 import get_embedding_provider
    from src.infrastructure.storage.sqlite import SQLiteDocumentStore, SQLiteInvoiceStore

    store = get_vector_store()
    doc_store = SQLiteDocumentStore()
    invoice_store = SQLiteInvoiceStore()
    embedder = get_embedding_provider()

    # Rebuild chunks index
    logger.info("rebuilding_chunks_index")
    chunks = await doc_store.get_chunks_for_indexing(limit=100000)
    if chunks:
        texts = [c.embedding_text for c in chunks]
        chunk_ids = [c.id for c in chunks if c.id is not None]
        embeddings = embedder.embed_batch(texts)
        await store.build_index("chunks", embeddings, chunk_ids, force_rebuild=True)

    # Rebuild items index
    logger.info("rebuilding_items_index")
    items = await invoice_store.get_items_for_indexing(limit=100000)
    if items:
        texts = [
            f"{item['item_name']} {item.get('hs_code', '')} {item.get('brand', '')} {item.get('model', '')}"
            for item in items
        ]
        item_ids: list[int] = [item["id"] for item in items]
        embeddings = embedder.embed_batch(texts)
        await store.build_index("items", embeddings, item_ids, force_rebuild=True)

    logger.info("index_rebuild_complete")


if __name__ == "__main__":
    asyncio.run(rebuild_indexes())
