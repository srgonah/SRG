"""
Unit tests for DocumentIndexerService incremental indexing.

Tests:
- index_document() single document indexing
- index_pending() incremental batch indexing
- rebuild_index() full rebuild
- State tracking and locking
- Error handling and recovery
- Chunk creation and text splitting
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.entities.document import Chunk, Document, IndexingState, Page, PageType
from src.core.exceptions import IndexingError
from src.core.services.document_indexer import DocumentIndexerService


class MockDocumentStore:
    """Mock implementation of IDocumentStore."""

    def __init__(self):
        self.documents = {}
        self.pages = {}
        self.chunks = {}
        self._chunk_id = 0

    async def get_document(self, doc_id: int) -> Document | None:
        return self.documents.get(doc_id)

    async def update_document(self, document: Document) -> Document:
        self.documents[document.id] = document
        return document

    async def get_pages(self, doc_id: int) -> list[Page]:
        return self.pages.get(doc_id, [])

    async def create_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        for chunk in chunks:
            self._chunk_id += 1
            chunk.id = self._chunk_id
            if chunk.doc_id not in self.chunks:
                self.chunks[chunk.doc_id] = []
            self.chunks[chunk.doc_id].append(chunk)
        return chunks

    async def get_chunks(self, doc_id: int) -> list[Chunk]:
        return self.chunks.get(doc_id, [])

    async def get_chunks_for_indexing(self, last_chunk_id: int = 0, limit: int = 1000) -> list[Chunk]:
        all_chunks = []
        for chunks in self.chunks.values():
            all_chunks.extend(chunks)
        # Filter by ID and limit
        return [c for c in all_chunks if c.id and c.id > last_chunk_id][:limit]

    def add_document(self, doc: Document):
        """Helper to add test documents."""
        self.documents[doc.id] = doc

    def add_pages(self, doc_id: int, pages: list[Page]):
        """Helper to add test pages."""
        self.pages[doc_id] = pages


class MockVectorStore:
    """Mock implementation of IVectorStore."""

    def __init__(self):
        self.vectors = {}
        self.id_mappings = {}
        self.saved = False

    async def add_vectors(self, index_name: str, embeddings: list, ids: list[int]) -> bool:
        if index_name not in self.vectors:
            self.vectors[index_name] = []
        for emb, id_ in zip(embeddings, ids):
            self.vectors[index_name].append((id_, emb))
        return True

    async def save_id_mapping(self, index_name: str, faiss_id: int, entity_id: int) -> None:
        if index_name not in self.id_mappings:
            self.id_mappings[index_name] = {}
        self.id_mappings[index_name][faiss_id] = entity_id

    async def save_index(self, index_name: str) -> bool:
        self.saved = True
        return True

    async def get_index_stats(self, index_name: str) -> dict:
        return {
            "name": index_name,
            "vector_count": len(self.vectors.get(index_name, [])),
        }


class MockEmbeddingProvider:
    """Mock implementation of IEmbeddingProvider."""

    def __init__(self, dimension: int = 384):
        self.dimension = dimension
        self.calls = []

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        self.calls.append(texts)
        # Return fake embeddings
        return [[0.1] * self.dimension for _ in texts]

    def get_dimension(self) -> int:
        return self.dimension

    def is_loaded(self) -> bool:
        return True


class MockIndexingStateStore:
    """Mock implementation of IIndexingStateStore."""

    def __init__(self):
        self.states = {}

    async def get_state(self, index_name: str) -> IndexingState | None:
        return self.states.get(index_name)

    async def update_state(self, state: IndexingState) -> IndexingState:
        self.states[state.index_name] = state
        return state

    async def reset_state(self, index_name: str) -> bool:
        if index_name in self.states:
            del self.states[index_name]
        return True


class TestIndexDocument:
    """Tests for index_document() method."""

    @pytest.fixture
    def indexer(self):
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider()
        state_store = MockIndexingStateStore()

        return DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
            chunk_size=100,
            chunk_overlap=20,
        ), doc_store, vec_store, embedder

    @pytest.mark.asyncio
    async def test_index_document_success(self, indexer):
        """Should successfully index a document."""
        service, doc_store, vec_store, embedder = indexer

        # Setup test document
        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        doc_store.add_document(doc)
        doc_store.add_pages(1, [
            Page(id=1, doc_id=1, page_no=1, text="This is test content for the document."),
        ])

        result = await service.index_document(1)

        assert result["chunks_created"] > 0
        assert embedder.calls  # Embedding was called
        updated_doc = await doc_store.get_document(1)
        assert updated_doc.status == "indexed"
        assert updated_doc.indexed_at is not None

    @pytest.mark.asyncio
    async def test_index_document_not_found(self, indexer):
        """Should raise error when document not found."""
        service, _, _, _ = indexer

        with pytest.raises(IndexingError, match="Document not found"):
            await service.index_document(999)

    @pytest.mark.asyncio
    async def test_index_document_no_pages(self, indexer):
        """Should raise error when no pages found."""
        service, doc_store, _, _ = indexer

        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        doc_store.add_document(doc)
        # No pages added

        with pytest.raises(IndexingError, match="No pages found"):
            await service.index_document(1)

    @pytest.mark.asyncio
    async def test_index_document_empty_pages(self, indexer):
        """Should handle pages with no text."""
        service, doc_store, _, _ = indexer

        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        doc_store.add_document(doc)
        doc_store.add_pages(1, [
            Page(id=1, doc_id=1, page_no=1, text=""),  # Empty text
            Page(id=2, doc_id=1, page_no=2, text="   "),  # Whitespace only
        ])

        result = await service.index_document(1)

        assert result["chunks_created"] == 0


class TestIndexPending:
    """Tests for index_pending() incremental indexing."""

    @pytest.fixture
    def indexer(self):
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider()
        state_store = MockIndexingStateStore()

        return DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
        ), doc_store, vec_store, state_store

    @pytest.mark.asyncio
    async def test_index_pending_no_chunks(self, indexer):
        """Should handle empty chunk queue."""
        service, _, vec_store, _ = indexer

        result = await service.index_pending()

        assert result["chunks_indexed"] == 0
        assert vec_store.saved  # Still saves index

    @pytest.mark.asyncio
    async def test_index_pending_tracks_state(self, indexer):
        """Should track indexing state."""
        service, doc_store, _, state_store = indexer

        # Add document and create chunks manually
        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        doc_store.add_document(doc)
        doc_store.add_pages(1, [
            Page(id=1, doc_id=1, page_no=1, text="Test content"),
        ])

        # Pre-create some chunks
        chunks = [
            Chunk(id=1, doc_id=1, page_id=1, chunk_index=0, chunk_text="Test content", metadata={}),
        ]
        doc_store.chunks[1] = chunks

        await service.index_pending()

        # Check state was updated
        state = await state_store.get_state("chunks")
        assert state is not None
        assert state.is_building is False
        assert state.last_run_at is not None

    @pytest.mark.asyncio
    async def test_index_pending_prevents_concurrent(self, indexer):
        """Should prevent concurrent indexing."""
        service, _, _, state_store = indexer

        # Mark as building
        state = IndexingState(index_name="chunks", is_building=True)
        await state_store.update_state(state)

        with pytest.raises(IndexingError, match="already being built"):
            await service.index_pending()

    @pytest.mark.asyncio
    async def test_index_pending_incremental(self, indexer):
        """Should resume from last position."""
        service, doc_store, _, state_store = indexer

        # Set initial state
        state = IndexingState(index_name="chunks", last_chunk_id=5, total_indexed=5)
        await state_store.update_state(state)

        # Add chunks with IDs > 5
        doc_store.chunks[1] = [
            Chunk(id=6, doc_id=1, page_id=1, chunk_index=0, chunk_text="New chunk", metadata={}),
            Chunk(id=7, doc_id=1, page_id=1, chunk_index=1, chunk_text="Another chunk", metadata={}),
        ]

        result = await service.index_pending()

        # Should only process chunks > 5
        assert result["chunks_indexed"] == 2
        updated_state = await state_store.get_state("chunks")
        assert updated_state.last_chunk_id == 7


class TestRebuildIndex:
    """Tests for rebuild_index() full rebuild."""

    @pytest.mark.asyncio
    async def test_rebuild_resets_state(self):
        """Should reset state before rebuilding."""
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider()
        state_store = MockIndexingStateStore()

        # Set existing state
        state = IndexingState(index_name="chunks", last_chunk_id=100, total_indexed=100)
        await state_store.update_state(state)

        service = DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
        )

        await service.rebuild_index()

        # State should be reset (new state created after rebuild)
        new_state = await state_store.get_state("chunks")
        # After rebuild with no chunks, state should be fresh
        assert new_state.total_indexed == 0 or new_state is None


class TestChunkCreation:
    """Tests for text chunking logic."""

    @pytest.fixture
    def indexer(self):
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider()
        state_store = MockIndexingStateStore()

        return DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
            chunk_size=50,
            chunk_overlap=10,
        )

    def test_create_chunks_basic(self, indexer):
        """Should create chunks from pages."""
        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        pages = [
            Page(id=1, doc_id=1, page_no=1, text="This is a simple test text."),
        ]

        chunks = indexer._create_chunks(doc, pages)

        assert len(chunks) > 0
        assert all(c.doc_id == 1 for c in chunks)
        assert all(c.page_id == 1 for c in chunks)

    def test_create_chunks_multiple_pages(self, indexer):
        """Should create chunks from multiple pages."""
        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        pages = [
            Page(id=1, doc_id=1, page_no=1, text="Page one content."),
            Page(id=2, doc_id=1, page_no=2, text="Page two content."),
        ]

        chunks = indexer._create_chunks(doc, pages)

        # Should have chunks from both pages
        page_ids = set(c.page_id for c in chunks)
        assert len(page_ids) == 2

    def test_create_chunks_preserves_metadata(self, indexer):
        """Should include page metadata in chunks."""
        doc = Document(id=1, filename="invoice.pdf", original_filename="invoice.pdf", file_path="/invoice.pdf")
        pages = [
            Page(id=1, doc_id=1, page_no=3, page_type=PageType.INVOICE, text="Invoice content here."),
        ]

        chunks = indexer._create_chunks(doc, pages)

        assert len(chunks) > 0
        assert chunks[0].metadata["page_no"] == 3
        assert chunks[0].metadata["page_type"] == "invoice"
        assert chunks[0].metadata["filename"] == "invoice.pdf"

    def test_split_text_small(self, indexer):
        """Small text should stay in one chunk."""
        text = "Short text."

        chunks = indexer._split_text(text, chunk_size=100, overlap=10)

        assert len(chunks) == 1
        assert chunks[0] == "Short text."

    def test_split_text_with_overlap(self, indexer):
        """Should create overlapping chunks for long text."""
        text = "First sentence here. Second sentence here. Third sentence here. Fourth sentence here."

        chunks = indexer._split_text(text, chunk_size=50, overlap=10)

        assert len(chunks) >= 2
        # Check some overlap exists (last chars of previous in next)

    def test_split_text_respects_sentences(self, indexer):
        """Should try to split on sentence boundaries."""
        text = "This is sentence one. This is sentence two. This is sentence three."

        chunks = indexer._split_text(text, chunk_size=50, overlap=0)

        # Chunks should roughly align with sentences
        for chunk in chunks:
            assert chunk.strip()  # No empty chunks


class TestErrorHandling:
    """Tests for error handling and recovery."""

    @pytest.mark.asyncio
    async def test_index_document_marks_failed_on_error(self):
        """Should mark document as failed on error."""
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider()
        state_store = MockIndexingStateStore()

        # Make embedder fail
        embedder.embed_batch = MagicMock(side_effect=Exception("Embedding failed"))

        service = DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
        )

        doc = Document(id=1, filename="test.pdf", original_filename="test.pdf", file_path="/test.pdf")
        doc_store.add_document(doc)
        doc_store.add_pages(1, [
            Page(id=1, doc_id=1, page_no=1, text="Test content"),
        ])

        with pytest.raises(IndexingError):
            await service.index_document(1)

        # Document should be marked failed
        updated_doc = await doc_store.get_document(1)
        assert updated_doc.status == "failed"
        assert "Embedding failed" in updated_doc.error_message

    @pytest.mark.asyncio
    async def test_index_pending_releases_lock_on_error(self):
        """Should release building lock on error."""
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider()
        state_store = MockIndexingStateStore()

        # Add chunks that will cause embedding to be called
        doc_store.chunks[1] = [
            Chunk(id=1, doc_id=1, page_id=1, chunk_index=0, chunk_text="Test", metadata={}),
        ]

        # Make embedder fail
        embedder.embed_batch = MagicMock(side_effect=Exception("Embedding failed"))

        service = DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
        )

        with pytest.raises(IndexingError):
            await service.index_pending()

        # Lock should be released
        state = await state_store.get_state("chunks")
        assert state.is_building is False
        assert "Embedding failed" in state.last_error


class TestIndexingStats:
    """Tests for get_indexing_stats()."""

    @pytest.mark.asyncio
    async def test_get_indexing_stats(self):
        """Should return comprehensive stats."""
        doc_store = MockDocumentStore()
        vec_store = MockVectorStore()
        embedder = MockEmbeddingProvider(dimension=768)
        state_store = MockIndexingStateStore()

        # Set some state
        await state_store.update_state(
            IndexingState(index_name="chunks", total_indexed=100, last_chunk_id=100)
        )

        service = DocumentIndexerService(
            document_store=doc_store,
            vector_store=vec_store,
            embedding_provider=embedder,
            indexing_state_store=state_store,
        )

        stats = await service.get_indexing_stats()

        assert "chunks" in stats
        assert stats["chunks"]["total_indexed"] == 100
        assert stats["embedding_dimension"] == 768
        assert stats["embedding_loaded"] is True
