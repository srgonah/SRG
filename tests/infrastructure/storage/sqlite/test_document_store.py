"""Unit tests for SQLiteDocumentStore."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from src.core.entities import Chunk, Document, DocumentStatus, Page, PageType
from src.infrastructure.storage.sqlite.document_store import SQLiteDocumentStore


class TestSQLiteDocumentStoreCreateDocument:
    """Tests for SQLiteDocumentStore.create_document()."""

    @pytest.mark.asyncio
    async def test_create_document_returns_document_with_id(
        self, initialized_db, sample_document, mock_settings
    ):
        """create_document() assigns ID to document."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            result = await store.create_document(sample_document)

            assert result.id is not None
            assert result.id > 0
            assert result.filename == sample_document.filename

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_create_document_persists_all_fields(
        self, initialized_db, sample_document, mock_settings
    ):
        """create_document() persists all document fields."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)

            # Retrieve and verify
            retrieved = await store.get_document(created.id)
            assert retrieved is not None
            assert retrieved.filename == sample_document.filename
            assert retrieved.file_hash == sample_document.file_hash
            assert retrieved.file_size == sample_document.file_size
            assert retrieved.status == sample_document.status
            assert retrieved.company_key == sample_document.company_key
            assert retrieved.metadata == sample_document.metadata

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreGetDocument:
    """Tests for SQLiteDocumentStore.get_document()."""

    @pytest.mark.asyncio
    async def test_get_document_returns_document(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_document() returns document by ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)

            result = await store.get_document(created.id)
            assert result is not None
            assert result.id == created.id

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_document_returns_none_for_missing(
        self, initialized_db, mock_settings
    ):
        """get_document() returns None for non-existent ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            result = await store.get_document(99999)

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_document_converts_status_enum(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_document() converts status string to enum."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            sample_document.status = DocumentStatus.INDEXED
            created = await store.create_document(sample_document)

            result = await store.get_document(created.id)
            assert isinstance(result.status, DocumentStatus)
            assert result.status == DocumentStatus.INDEXED

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreGetDocumentByHash:
    """Tests for SQLiteDocumentStore.get_document_by_hash()."""

    @pytest.mark.asyncio
    async def test_get_document_by_hash_returns_latest(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_document_by_hash() returns latest version only."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)

            result = await store.get_document_by_hash(sample_document.file_hash)
            assert result is not None
            assert result.id == created.id
            assert result.file_hash == sample_document.file_hash

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_document_by_hash_returns_none_for_missing(
        self, initialized_db, mock_settings
    ):
        """get_document_by_hash() returns None for unknown hash."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            result = await store.get_document_by_hash("nonexistent_hash")

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreUpdateDocument:
    """Tests for SQLiteDocumentStore.update_document()."""

    @pytest.mark.asyncio
    async def test_update_document_modifies_fields(
        self, initialized_db, sample_document, mock_settings
    ):
        """update_document() modifies document fields."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)

            # Modify and update
            created.status = DocumentStatus.INDEXED
            created.page_count = 5
            created.company_key = "NEW_COMPANY"

            updated = await store.update_document(created)

            # Verify
            result = await store.get_document(created.id)
            assert result.status == DocumentStatus.INDEXED
            assert result.page_count == 5
            assert result.company_key == "NEW_COMPANY"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_update_document_updates_timestamp(
        self, initialized_db, sample_document, mock_settings
    ):
        """update_document() updates the updated_at timestamp."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)
            original_updated = created.updated_at

            # Small delay to ensure timestamp difference
            import asyncio

            await asyncio.sleep(0.01)

            created.status = DocumentStatus.FAILED
            updated = await store.update_document(created)

            assert updated.updated_at > original_updated

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreDeleteDocument:
    """Tests for SQLiteDocumentStore.delete_document()."""

    @pytest.mark.asyncio
    async def test_delete_document_returns_true(
        self, initialized_db, sample_document, mock_settings
    ):
        """delete_document() returns True on success."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)

            result = await store.delete_document(created.id)
            assert result is True

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_document_removes_document(
        self, initialized_db, sample_document, mock_settings
    ):
        """delete_document() removes document from database."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            created = await store.create_document(sample_document)

            await store.delete_document(created.id)
            result = await store.get_document(created.id)

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_document_returns_false_for_missing(
        self, initialized_db, mock_settings
    ):
        """delete_document() returns False for non-existent ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            result = await store.delete_document(99999)

            assert result is False

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreListDocuments:
    """Tests for SQLiteDocumentStore.list_documents()."""

    @pytest.mark.asyncio
    async def test_list_documents_returns_list(
        self, initialized_db, sample_document, mock_settings
    ):
        """list_documents() returns list of documents."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            await store.create_document(sample_document)

            result = await store.list_documents()
            assert isinstance(result, list)
            assert len(result) >= 1

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_list_documents_respects_limit(
        self, initialized_db, sample_document, mock_settings
    ):
        """list_documents() respects limit parameter."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()

            # Create multiple documents
            for i in range(5):
                doc = Document(
                    filename=f"doc_{i}.pdf",
                    original_filename=f"doc_{i}.pdf",
                    file_path=f"/uploads/doc_{i}.pdf",
                    file_hash=f"hash_{i}",
                    file_size=100,
                    status=DocumentStatus.PENDING,
                )
                await store.create_document(doc)

            result = await store.list_documents(limit=3)
            assert len(result) == 3

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_list_documents_filters_by_status(
        self, initialized_db, mock_settings
    ):
        """list_documents() filters by status."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()

            # Create documents with different statuses
            pending_doc = Document(
                filename="pending.pdf",
                original_filename="pending.pdf",
                file_path="/uploads/pending.pdf",
                status=DocumentStatus.PENDING,
            )
            indexed_doc = Document(
                filename="indexed.pdf",
                original_filename="indexed.pdf",
                file_path="/uploads/indexed.pdf",
                status=DocumentStatus.INDEXED,
            )

            await store.create_document(pending_doc)
            await store.create_document(indexed_doc)

            # Filter by status
            result = await store.list_documents(status="indexed")
            assert all(d.status == DocumentStatus.INDEXED for d in result)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStorePageOperations:
    """Tests for page operations."""

    @pytest.mark.asyncio
    async def test_create_page_returns_page_with_id(
        self, initialized_db, sample_document, sample_page, mock_settings
    ):
        """create_page() assigns ID to page."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            sample_page.doc_id = doc.id
            page = await store.create_page(sample_page)

            assert page.id is not None
            assert page.id > 0

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_pages_returns_all_pages(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_pages() returns all pages for a document."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            # Create multiple pages
            for i in range(3):
                page = Page(
                    doc_id=doc.id,
                    page_no=i + 1,
                    page_type=PageType.INVOICE,
                    text=f"Page {i + 1} content",
                )
                await store.create_page(page)

            pages = await store.get_pages(doc.id)
            assert len(pages) == 3
            assert pages[0].page_no == 1
            assert pages[1].page_no == 2
            assert pages[2].page_no == 3

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_update_page_modifies_fields(
        self, initialized_db, sample_document, sample_page, mock_settings
    ):
        """update_page() modifies page fields."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            sample_page.doc_id = doc.id
            page = await store.create_page(sample_page)

            # Update page
            page.page_type = PageType.PACKING_LIST
            page.text = "Updated content"
            await store.update_page(page)

            # Verify
            pages = await store.get_pages(doc.id)
            updated_page = pages[0]
            assert updated_page.page_type == PageType.PACKING_LIST
            assert updated_page.text == "Updated content"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreChunkOperations:
    """Tests for chunk operations."""

    @pytest.mark.asyncio
    async def test_create_chunks_batch_insert(
        self, initialized_db, sample_document, mock_settings
    ):
        """create_chunks() inserts multiple chunks."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            # Create a page first
            page = Page(
                doc_id=doc.id,
                page_no=1,
                page_type=PageType.INVOICE,
                text="Test page content",
            )
            created_page = await store.create_page(page)

            chunks = [
                Chunk(
                    doc_id=doc.id,
                    page_id=created_page.id,
                    chunk_index=i,
                    chunk_text=f"Chunk {i} text content",
                    chunk_size=20,
                )
                for i in range(5)
            ]

            created = await store.create_chunks(chunks)
            assert len(created) == 5
            assert all(c.id is not None for c in created)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_create_chunks_empty_list(self, initialized_db, mock_settings):
        """create_chunks() handles empty list."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            result = await store.create_chunks([])

            assert result == []

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_chunks_returns_ordered_chunks(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_chunks() returns chunks ordered by chunk_index."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            # Create a page first
            page = Page(
                doc_id=doc.id,
                page_no=1,
                page_type=PageType.INVOICE,
                text="Test page",
            )
            created_page = await store.create_page(page)

            # Create chunks in reverse order
            chunks = [
                Chunk(
                    doc_id=doc.id,
                    page_id=created_page.id,
                    chunk_index=i,
                    chunk_text=f"Chunk {i}",
                    chunk_size=8,
                )
                for i in [2, 0, 1]  # Out of order
            ]
            await store.create_chunks(chunks)

            result = await store.get_chunks(doc.id)
            # Should be ordered by chunk_index
            assert result[0].chunk_index == 0
            assert result[1].chunk_index == 1
            assert result[2].chunk_index == 2

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_chunk_by_id_returns_chunk(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_chunk_by_id() returns specific chunk."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            # Create a page first
            page = Page(
                doc_id=doc.id,
                page_no=1,
                page_type=PageType.INVOICE,
                text="Test page",
            )
            created_page = await store.create_page(page)

            chunk = Chunk(
                doc_id=doc.id,
                page_id=created_page.id,
                chunk_index=0,
                chunk_text="Test chunk text content",
                chunk_size=23,
            )
            chunks = await store.create_chunks([chunk])
            chunk_id = chunks[0].id

            result = await store.get_chunk_by_id(chunk_id)
            assert result is not None
            assert result.id == chunk_id
            assert result.chunk_text == chunk.chunk_text

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_chunk_by_id_returns_none_for_missing(
        self, initialized_db, mock_settings
    ):
        """get_chunk_by_id() returns None for non-existent ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            result = await store.get_chunk_by_id(99999)

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_chunks_for_indexing_incremental(
        self, initialized_db, sample_document, mock_settings
    ):
        """get_chunks_for_indexing() supports incremental indexing."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            doc = await store.create_document(sample_document)

            # Create a page first
            page = Page(
                doc_id=doc.id,
                page_no=1,
                page_type=PageType.INVOICE,
                text="Test page",
            )
            created_page = await store.create_page(page)

            chunks = [
                Chunk(
                    doc_id=doc.id,
                    page_id=created_page.id,
                    chunk_index=i,
                    chunk_text=f"Chunk {i}",
                    chunk_size=8,
                )
                for i in range(10)
            ]
            created = await store.create_chunks(chunks)

            # Get first batch
            first_batch = await store.get_chunks_for_indexing(last_chunk_id=0, limit=5)
            assert len(first_batch) == 5

            # Get second batch
            last_id = first_batch[-1].id
            second_batch = await store.get_chunks_for_indexing(
                last_chunk_id=last_id, limit=5
            )
            assert len(second_batch) == 5
            assert second_batch[0].id > last_id

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteDocumentStoreRowConversion:
    """Tests for row-to-entity conversion methods."""

    @pytest.mark.asyncio
    async def test_row_to_document_converts_metadata_json(
        self, initialized_db, sample_document, mock_settings
    ):
        """_row_to_document() parses metadata JSON."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()
            sample_document.metadata = {"key1": "value1", "key2": 123}
            created = await store.create_document(sample_document)

            result = await store.get_document(created.id)
            assert result.metadata == {"key1": "value1", "key2": 123}

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_row_to_document_handles_null_metadata(
        self, initialized_db, mock_settings
    ):
        """_row_to_document() handles null metadata_json."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteDocumentStore()

            doc = Document(
                filename="test.pdf",
                original_filename="test.pdf",
                file_path="/uploads/test.pdf",
                metadata={},
            )
            created = await store.create_document(doc)

            result = await store.get_document(created.id)
            assert result.metadata == {}

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()
