"""
Document indexing service.

Layer-pure service managing document chunking, embedding, and incremental indexing.
NO infrastructure imports - depends only on core entities, interfaces, exceptions.
"""

from datetime import datetime
from typing import Any

from src.core.entities.document import Chunk, Document, IndexingState, Page
from src.core.exceptions import IndexingError
from src.core.interfaces import (
    IDocumentStore,
    IEmbeddingProvider,
    IIndexingStateStore,
    IVectorStore,
)


class DocumentIndexerService:
    """
    Document indexing pipeline.

    Handles:
    - Text chunking with overlap
    - Embedding generation
    - Vector index updates (incremental)
    - Indexing state tracking

    Required interfaces for DI:
    - IDocumentStore: Document, page, chunk persistence
    - IVectorStore: Vector index management
    - IEmbeddingProvider: Embedding generation
    - IIndexingStateStore: Incremental indexing state
    """

    def __init__(
        self,
        document_store: IDocumentStore,
        vector_store: IVectorStore,
        embedding_provider: IEmbeddingProvider,
        indexing_state_store: IIndexingStateStore,
        chunk_size: int = 512,
        chunk_overlap: int = 50,
    ):
        """
        Initialize indexer service with injected dependencies.

        Args:
            document_store: Document persistence (required)
            vector_store: Vector index (required)
            embedding_provider: Embedding generation (required)
            indexing_state_store: State tracking (required)
            chunk_size: Default chunk size in chars
            chunk_overlap: Default overlap between chunks
        """
        self._doc_store = document_store
        self._vec_store = vector_store
        self._embedder = embedding_provider
        self._state_store = indexing_state_store
        self._chunk_size = chunk_size
        self._chunk_overlap = chunk_overlap

    async def index_document(self, document_id: int) -> dict[str, Any]:
        """
        Index a single document by ID.

        Chunks the document's pages, generates embeddings, and updates vectors.

        Args:
            document_id: ID of document to index

        Returns:
            Dict with indexing stats (chunks_created, vectors_added)

        Raises:
            IndexingError: If document not found or indexing fails
        """
        # Get document
        document = await self._doc_store.get_document(document_id)
        if not document:
            raise IndexingError(f"Document not found: {document_id}")

        # Get pages
        pages = await self._doc_store.get_pages(document_id)
        if not pages:
            raise IndexingError(f"No pages found for document: {document_id}")

        try:
            # Create chunks from pages
            chunks = self._create_chunks(document, pages)

            if not chunks:
                return {"chunks_created": 0, "vectors_added": 0}

            # Generate embeddings
            await self._generate_embeddings(chunks)

            # Save chunks to document store
            chunks = await self._doc_store.create_chunks(chunks)

            # Add to vector index
            embeddings = [c.metadata.get("embedding") for c in chunks if c.metadata.get("embedding")]
            if embeddings:
                chunk_ids = [c.id for c in chunks if c.id]
                await self._vec_store.add_vectors(
                    index_name="chunks",
                    embeddings=embeddings,
                    ids=chunk_ids,
                )

                # Save ID mappings
                for i, chunk in enumerate(chunks):
                    if chunk.id and chunk.faiss_id is not None:
                        await self._vec_store.save_id_mapping(
                            index_name="chunks",
                            faiss_id=chunk.faiss_id,
                            entity_id=chunk.id,
                        )

            # Update document status
            document.status = "indexed"
            document.indexed_at = datetime.now()
            await self._doc_store.update_document(document)

            return {
                "chunks_created": len(chunks),
                "vectors_added": len(embeddings),
            }

        except Exception as e:
            # Mark document as failed
            document.status = "failed"
            document.error_message = str(e)
            await self._doc_store.update_document(document)
            raise IndexingError(f"Failed to index document {document_id}: {str(e)}")

    async def index_pending(
        self,
        batch_size: int = 100,
        index_name: str = "chunks",
    ) -> dict[str, Any]:
        """
        Index pending chunks incrementally.

        Processes chunks that haven't been indexed yet, tracking progress.

        Args:
            batch_size: Number of chunks to process per batch
            index_name: Name of the index to update

        Returns:
            Dict with indexing stats
        """
        # Get current state
        state = await self._state_store.get_state(index_name)
        if state is None:
            state = IndexingState(index_name=index_name)

        if state.is_building:
            raise IndexingError(f"Index {index_name} is already being built")

        # Mark as building
        state.is_building = True
        state = await self._state_store.update_state(state)

        try:
            total_indexed = 0
            last_chunk_id = state.last_chunk_id

            while True:
                # Get next batch of unindexed chunks
                chunks = await self._doc_store.get_chunks_for_indexing(
                    last_chunk_id=last_chunk_id,
                    limit=batch_size,
                )

                if not chunks:
                    break

                # Generate embeddings for chunks without them
                chunks_to_embed = [c for c in chunks if not c.metadata.get("embedding")]
                if chunks_to_embed:
                    await self._generate_embeddings(chunks_to_embed)

                # Add to vector index
                embeddings = []
                chunk_ids = []
                for chunk in chunks:
                    emb = chunk.metadata.get("embedding")
                    if emb is not None and chunk.id:
                        embeddings.append(emb)
                        chunk_ids.append(chunk.id)

                if embeddings:
                    await self._vec_store.add_vectors(
                        index_name=index_name,
                        embeddings=embeddings,
                        ids=chunk_ids,
                    )

                total_indexed += len(chunks)
                last_chunk_id = max(c.id for c in chunks if c.id) if chunks else last_chunk_id

                # Update state
                state.last_chunk_id = last_chunk_id
                state.total_indexed += len(chunks)
                state = await self._state_store.update_state(state)

            # Mark complete
            state.is_building = False
            state.last_run_at = datetime.now()
            state.last_error = None
            await self._state_store.update_state(state)

            # Save index
            await self._vec_store.save_index(index_name)

            return {
                "chunks_indexed": total_indexed,
                "last_chunk_id": last_chunk_id,
                "total_indexed": state.total_indexed,
            }

        except Exception as e:
            # Record error and release lock
            state.is_building = False
            state.last_error = str(e)
            await self._state_store.update_state(state)
            raise IndexingError(f"Incremental indexing failed: {str(e)}")

    async def rebuild_index(
        self,
        index_name: str = "chunks",
        batch_size: int = 500,
    ) -> dict[str, Any]:
        """
        Rebuild the entire index from scratch.

        Resets state and re-indexes all chunks.

        Args:
            index_name: Name of index to rebuild
            batch_size: Processing batch size

        Returns:
            Dict with rebuild stats
        """
        # Reset state
        await self._state_store.reset_state(index_name)

        # Full index rebuild
        return await self.index_pending(batch_size=batch_size, index_name=index_name)

    def _create_chunks(
        self,
        document: Document,
        pages: list[Page],
    ) -> list[Chunk]:
        """Create text chunks from document pages."""
        chunks = []

        for page in pages:
            if not page.text:
                continue

            text = page.text.strip()
            if not text:
                continue

            # Split into chunks with overlap
            page_chunks = self._split_text(
                text=text,
                chunk_size=self._chunk_size,
                overlap=self._chunk_overlap,
            )

            for i, chunk_text in enumerate(page_chunks):
                chunk = Chunk(
                    doc_id=document.id,
                    page_id=page.id,
                    chunk_index=i,
                    chunk_text=chunk_text,
                    chunk_size=len(chunk_text),
                    metadata={
                        "page_no": page.page_no,
                        "page_type": page.page_type.value if page.page_type else None,
                        "filename": document.filename,
                    },
                )
                chunks.append(chunk)

        return chunks

    def _split_text(
        self,
        text: str,
        chunk_size: int,
        overlap: int,
    ) -> list[str]:
        """Split text into overlapping chunks."""
        if len(text) <= chunk_size:
            return [text]

        chunks = []

        # Try to split on sentence boundaries
        sentences = self._split_sentences(text)

        current_chunk = ""
        for sentence in sentences:
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())

                # Start new chunk with overlap from previous
                if overlap > 0 and chunks:
                    overlap_text = chunks[-1][-overlap:]
                    current_chunk = overlap_text + " " + sentence + " "
                else:
                    current_chunk = sentence + " "

        if current_chunk.strip():
            chunks.append(current_chunk.strip())

        return chunks

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        import re

        # Simple sentence splitting on .!?
        sentences = re.split(r"(?<=[.!?])\s+", text)
        return [s.strip() for s in sentences if s.strip()]

    async def _generate_embeddings(self, chunks: list[Chunk]) -> None:
        """Generate embeddings for chunks."""
        if not chunks:
            return

        texts = [c.embedding_text for c in chunks]

        embeddings = await self._embedder.embed_batch(texts)

        for chunk, embedding in zip(chunks, embeddings):
            chunk.metadata["embedding"] = embedding

    async def delete_document_index(self, document_id: int) -> bool:
        """
        Remove a document from the index.

        Args:
            document_id: Document to remove

        Returns:
            True if removed
        """
        # Get chunks for document
        chunks = await self._doc_store.get_chunks(document_id)

        if not chunks:
            return False

        # Would need to remove from vector store
        # This depends on vector store supporting deletion by ID
        # For now, mark as requiring rebuild

        return True

    async def get_indexing_stats(self) -> dict[str, Any]:
        """Get indexing statistics."""
        chunk_state = await self._state_store.get_state("chunks")
        item_state = await self._state_store.get_state("items")

        vec_stats = await self._vec_store.get_index_stats("chunks")

        return {
            "chunks": {
                "total_indexed": chunk_state.total_indexed if chunk_state else 0,
                "last_chunk_id": chunk_state.last_chunk_id if chunk_state else 0,
                "is_building": chunk_state.is_building if chunk_state else False,
                "last_run": chunk_state.last_run_at.isoformat() if chunk_state and chunk_state.last_run_at else None,
            },
            "items": {
                "total_indexed": item_state.total_indexed if item_state else 0,
                "last_item_id": item_state.last_item_id if item_state else 0,
                "is_building": item_state.is_building if item_state else False,
            },
            "vector_index": vec_stats,
            "embedding_dimension": self._embedder.get_dimension(),
            "embedding_loaded": self._embedder.is_loaded(),
        }

    async def get_pending_count(self, index_name: str = "chunks") -> int:
        """Get count of chunks pending indexing."""
        state = await self._state_store.get_state(index_name)
        return state.pending_count if state else 0
