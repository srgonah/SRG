"""Unit tests for document domain entities."""

from datetime import datetime

from src.core.entities.document import (
    Chunk,
    Document,
    DocumentStatus,
    IndexingState,
    Page,
    PageType,
    SearchResult,
)


class TestPageType:
    """Tests for PageType enum."""

    def test_all_page_types_exist(self):
        expected = {
            "invoice",
            "packing_list",
            "contract",
            "bank_form",
            "certificate",
            "cover_letter",
            "other",
        }
        actual = {t.value for t in PageType}
        assert actual == expected


class TestDocumentStatus:
    """Tests for DocumentStatus enum."""

    def test_all_statuses_exist(self):
        expected = {"pending", "processing", "indexed", "failed"}
        actual = {s.value for s in DocumentStatus}
        assert actual == expected


class TestDocument:
    """Tests for Document entity."""

    def test_required_fields(self):
        doc = Document(
            filename="test.pdf",
            original_filename="Test Document.pdf",
            file_path="/uploads/test.pdf",
        )
        assert doc.filename == "test.pdf"
        assert doc.original_filename == "Test Document.pdf"
        assert doc.file_path == "/uploads/test.pdf"

    def test_default_values(self):
        doc = Document(
            filename="test.pdf",
            original_filename="test.pdf",
            file_path="/test.pdf",
        )
        assert doc.id is None
        assert doc.file_hash is None
        assert doc.file_size == 0
        assert doc.mime_type == "application/pdf"
        assert doc.status == DocumentStatus.PENDING
        assert doc.error_message is None
        assert doc.version == 1
        assert doc.is_latest is True
        assert doc.previous_version_id is None
        assert doc.page_count == 0
        assert doc.company_key is None
        assert doc.metadata == {}
        assert doc.indexed_at is None

    def test_timestamps_auto_generated(self):
        before = datetime.utcnow()
        doc = Document(
            filename="test.pdf",
            original_filename="test.pdf",
            file_path="/test.pdf",
        )
        after = datetime.utcnow()
        assert before <= doc.created_at <= after
        assert before <= doc.updated_at <= after

    def test_metadata_dict(self):
        doc = Document(
            filename="test.pdf",
            original_filename="test.pdf",
            file_path="/test.pdf",
            metadata={"source": "email", "sender": "user@example.com"},
        )
        assert doc.metadata["source"] == "email"
        assert doc.metadata["sender"] == "user@example.com"


class TestPage:
    """Tests for Page entity."""

    def test_required_fields(self):
        page = Page(doc_id=1, page_no=1)
        assert page.doc_id == 1
        assert page.page_no == 1

    def test_default_values(self):
        page = Page(doc_id=1, page_no=1)
        assert page.id is None
        assert page.page_type == PageType.OTHER
        assert page.type_confidence == 0.0
        assert page.text == ""
        assert page.text_length == 0
        assert page.image_path is None
        assert page.image_hash is None
        assert page.metadata == {}

    def test_with_classification(self):
        page = Page(
            doc_id=1,
            page_no=1,
            page_type=PageType.INVOICE,
            type_confidence=0.95,
            text="Invoice content here",
        )
        assert page.page_type == PageType.INVOICE
        assert page.type_confidence == 0.95
        assert page.text == "Invoice content here"


class TestChunk:
    """Tests for Chunk entity."""

    def test_required_fields(self):
        chunk = Chunk(doc_id=1, page_id=1)
        assert chunk.doc_id == 1
        assert chunk.page_id == 1

    def test_default_values(self):
        chunk = Chunk(doc_id=1, page_id=1)
        assert chunk.id is None
        assert chunk.chunk_index == 0
        assert chunk.chunk_text == ""
        assert chunk.chunk_size == 0
        assert chunk.start_char == 0
        assert chunk.end_char == 0
        assert chunk.metadata == {}
        assert chunk.faiss_id is None

    def test_embedding_text_without_page_type(self):
        chunk = Chunk(
            doc_id=1,
            page_id=1,
            chunk_text="Sample chunk text",
        )
        assert chunk.embedding_text == "Sample chunk text"

    def test_embedding_text_with_page_type(self):
        chunk = Chunk(
            doc_id=1,
            page_id=1,
            chunk_text="Sample chunk text",
            metadata={"page_type": "invoice"},
        )
        assert chunk.embedding_text == "[invoice] Sample chunk text"

    def test_embedding_text_with_empty_page_type(self):
        chunk = Chunk(
            doc_id=1,
            page_id=1,
            chunk_text="Sample chunk text",
            metadata={"page_type": ""},
        )
        assert chunk.embedding_text == "Sample chunk text"


class TestIndexingState:
    """Tests for IndexingState entity."""

    def test_required_fields(self):
        state = IndexingState(index_name="chunks")
        assert state.index_name == "chunks"

    def test_default_values(self):
        state = IndexingState(index_name="chunks")
        assert state.id is None
        assert state.last_doc_id == 0
        assert state.last_chunk_id == 0
        assert state.last_item_id == 0
        assert state.total_indexed == 0
        assert state.pending_count == 0
        assert state.is_building is False
        assert state.last_error is None
        assert state.last_run_at is None

    def test_with_state_data(self):
        state = IndexingState(
            index_name="items",
            last_item_id=500,
            total_indexed=500,
            is_building=True,
        )
        assert state.index_name == "items"
        assert state.last_item_id == 500
        assert state.total_indexed == 500
        assert state.is_building is True


class TestSearchResult:
    """Tests for SearchResult entity."""

    def test_default_values(self):
        result = SearchResult()
        assert result.chunk_id is None
        assert result.item_id is None
        assert result.doc_id is None
        assert result.text == ""
        assert result.item_name is None
        assert result.faiss_score == 0.0
        assert result.fts_score == 0.0
        assert result.hybrid_score == 0.0
        assert result.reranker_score is None
        assert result.final_score == 0.0
        assert result.faiss_rank == 0
        assert result.final_rank == 0
        assert result.metadata == {}

    def test_with_scores(self):
        result = SearchResult(
            chunk_id=1,
            doc_id=1,
            text="Matching text",
            faiss_score=0.85,
            fts_score=0.7,
            hybrid_score=0.8,
            reranker_score=0.9,
            final_score=0.9,
            faiss_rank=1,
            final_rank=1,
        )
        assert result.faiss_score == 0.85
        assert result.fts_score == 0.7
        assert result.hybrid_score == 0.8
        assert result.reranker_score == 0.9
        assert result.final_score == 0.9

    def test_with_context_fields(self):
        result = SearchResult(
            item_id=1,
            item_name="Test Product",
            page_no=1,
            page_type="invoice",
            invoice_no="INV-001",
            invoice_date="2024-01-15",
            seller_name="Test Vendor",
            hs_code="8471.30",
            quantity=10.0,
            unit_price=50.0,
            total_price=500.0,
        )
        assert result.item_name == "Test Product"
        assert result.invoice_no == "INV-001"
        assert result.seller_name == "Test Vendor"
        assert result.hs_code == "8471.30"
        assert result.quantity == 10.0
