"""Unit tests for SQLiteInvoiceStore."""

from unittest.mock import patch

import pytest

from src.core.entities import (
    ArithmeticCheckContainer,
    AuditIssue,
    AuditResult,
    AuditStatus,
    Document,
    DocumentStatus,
    Invoice,
    LineItem,
    ParsingStatus,
    RowType,
)
from src.infrastructure.storage.sqlite.invoice_store import SQLiteInvoiceStore


class TestSQLiteInvoiceStoreCreateInvoice:
    """Tests for SQLiteInvoiceStore.create_invoice()."""

    @pytest.mark.asyncio
    async def test_create_invoice_returns_invoice_with_id(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """create_invoice() assigns ID to invoice."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            # Create document first (for foreign key)
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(
                filename="test.pdf",
                original_filename="test.pdf",
                file_path="/uploads/test.pdf",
                status=DocumentStatus.PENDING,
            )
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            result = await store.create_invoice(sample_invoice)

            assert result.id is not None
            assert result.id > 0

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_create_invoice_creates_items(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """create_invoice() creates line items with IDs."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(
                filename="test.pdf",
                original_filename="test.pdf",
                file_path="/uploads/test.pdf",
                status=DocumentStatus.PENDING,
            )
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id

            # Ensure items exist
            assert len(sample_invoice.items) == 2

            result = await store.create_invoice(sample_invoice)

            # Items should have IDs
            assert all(item.id is not None for item in result.items)
            assert all(item.invoice_id == result.id for item in result.items)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_create_invoice_persists_bank_details(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """create_invoice() persists bank details as JSON."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created = await store.create_invoice(sample_invoice)

            # Retrieve and verify
            retrieved = await store.get_invoice(created.id)
            assert retrieved.bank_details is not None
            assert retrieved.bank_details.bank_name == "Test Bank"
            assert retrieved.bank_details.account_number == "1234567890"
            assert retrieved.bank_details.swift == "TESTSWFT"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreGetInvoice:
    """Tests for SQLiteInvoiceStore.get_invoice()."""

    @pytest.mark.asyncio
    async def test_get_invoice_returns_invoice_with_items(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """get_invoice() returns invoice with items loaded."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created = await store.create_invoice(sample_invoice)

            result = await store.get_invoice(created.id)
            assert result is not None
            assert len(result.items) == 2
            assert result.items[0].item_name == "Widget A"
            assert result.items[1].item_name == "Widget B"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_invoice_returns_none_for_missing(
        self, initialized_db, mock_settings
    ):
        """get_invoice() returns None for non-existent ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteInvoiceStore()
            result = await store.get_invoice(99999)

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreGetInvoiceByDocId:
    """Tests for SQLiteInvoiceStore.get_invoice_by_doc_id()."""

    @pytest.mark.asyncio
    async def test_get_invoice_by_doc_id_returns_invoice(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """get_invoice_by_doc_id() finds invoice by document ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created = await store.create_invoice(sample_invoice)

            result = await store.get_invoice_by_doc_id(created_doc.id)
            assert result is not None
            assert result.id == created.id
            assert result.doc_id == created_doc.id

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreUpdateInvoice:
    """Tests for SQLiteInvoiceStore.update_invoice()."""

    @pytest.mark.asyncio
    async def test_update_invoice_modifies_fields(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """update_invoice() modifies invoice fields."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created = await store.create_invoice(sample_invoice)

            # Modify
            created.total_amount = 2000.00
            created.seller_name = "Updated Seller"
            created.parsing_status = ParsingStatus.PARTIAL

            await store.update_invoice(created)

            # Verify
            result = await store.get_invoice(created.id)
            assert result.total_amount == 2000.00
            assert result.seller_name == "Updated Seller"
            assert result.parsing_status == ParsingStatus.PARTIAL

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreDeleteInvoice:
    """Tests for SQLiteInvoiceStore.delete_invoice()."""

    @pytest.mark.asyncio
    async def test_delete_invoice_returns_true(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """delete_invoice() returns True on success."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created = await store.create_invoice(sample_invoice)

            result = await store.delete_invoice(created.id)
            assert result is True

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_invoice_removes_invoice(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """delete_invoice() removes invoice from database."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created = await store.create_invoice(sample_invoice)

            await store.delete_invoice(created.id)
            result = await store.get_invoice(created.id)

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_invoice_returns_false_for_missing(
        self, initialized_db, mock_settings
    ):
        """delete_invoice() returns False for non-existent ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteInvoiceStore()
            result = await store.delete_invoice(99999)

            assert result is False

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreListInvoices:
    """Tests for SQLiteInvoiceStore.list_invoices()."""

    @pytest.mark.asyncio
    async def test_list_invoices_returns_list(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """list_invoices() returns list of invoices."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            await store.create_invoice(sample_invoice)

            result = await store.list_invoices()
            assert isinstance(result, list)
            assert len(result) >= 1

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_list_invoices_filters_by_company_key(
        self, initialized_db, mock_settings
    ):
        """list_invoices() filters by company_key."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            store = SQLiteInvoiceStore()

            # Create invoices for different companies
            for company in ["ACME", "BETA", "ACME"]:
                doc = Document(filename=f"{company}.pdf", original_filename=f"{company}.pdf", file_path=f"/uploads/{company}.pdf")
                created_doc = await doc_store.create_document(doc)

                invoice = Invoice(
                    doc_id=created_doc.id,
                    invoice_no=f"INV-{company}",
                    company_key=company,
                )
                await store.create_invoice(invoice)

            # Filter by company
            result = await store.list_invoices(company_key="ACME")
            assert len(result) == 2
            assert all(inv.company_key == "ACME" for inv in result)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreCountInvoices:
    """Tests for SQLiteInvoiceStore.count_invoices()."""

    @pytest.mark.asyncio
    async def test_count_invoices_returns_count(
        self, initialized_db, mock_settings
    ):
        """count_invoices() returns total count."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            store = SQLiteInvoiceStore()

            # Create multiple invoices
            for i in range(3):
                doc = Document(filename=f"doc_{i}.pdf", original_filename=f"doc_{i}.pdf", file_path=f"/uploads/doc_{i}.pdf")
                created_doc = await doc_store.create_document(doc)

                invoice = Invoice(doc_id=created_doc.id, invoice_no=f"INV-{i}")
                await store.create_invoice(invoice)

            count = await store.count_invoices()
            assert count == 3

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreSearchInvoices:
    """Tests for SQLiteInvoiceStore.search_invoices()."""

    @pytest.mark.asyncio
    async def test_search_invoices_by_invoice_no(
        self, initialized_db, mock_settings
    ):
        """search_invoices() finds by invoice number."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            store = SQLiteInvoiceStore()

            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            invoice = Invoice(
                doc_id=created_doc.id,
                invoice_no="UNIQUE-12345",
                seller_name="Test Seller",
            )
            await store.create_invoice(invoice)

            result = await store.search_invoices("UNIQUE")
            assert len(result) == 1
            assert result[0].invoice_no == "UNIQUE-12345"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_search_invoices_by_seller_name(
        self, initialized_db, mock_settings
    ):
        """search_invoices() finds by seller name."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            store = SQLiteInvoiceStore()

            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            invoice = Invoice(
                doc_id=created_doc.id,
                invoice_no="INV-001",
                seller_name="UniqueSellerCorp",
            )
            await store.create_invoice(invoice)

            result = await store.search_invoices("UniqueSeller")
            assert len(result) == 1
            assert result[0].seller_name == "UniqueSellerCorp"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreAuditOperations:
    """Tests for audit result operations."""

    @pytest.mark.asyncio
    async def test_create_audit_result_returns_with_id(
        self, initialized_db, sample_invoice, sample_audit_result, mock_settings
    ):
        """create_audit_result() assigns ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created_invoice = await store.create_invoice(sample_invoice)

            sample_audit_result.invoice_id = created_invoice.id
            result = await store.create_audit_result(sample_audit_result)

            assert result.id is not None
            assert result.id > 0

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_audit_result_returns_latest(
        self, initialized_db, sample_invoice, sample_audit_result, mock_settings
    ):
        """get_audit_result() returns latest audit for invoice."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created_invoice = await store.create_invoice(sample_invoice)

            sample_audit_result.invoice_id = created_invoice.id
            await store.create_audit_result(sample_audit_result)

            result = await store.get_audit_result(created_invoice.id)
            assert result is not None
            assert result.invoice_id == created_invoice.id
            assert result.status == AuditStatus.PASS

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_audit_result_reconstructs_nested_objects(
        self, initialized_db, sample_invoice, sample_audit_result, mock_settings
    ):
        """get_audit_result() reconstructs ArithmeticCheck and AuditIssue."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created_invoice = await store.create_invoice(sample_invoice)

            sample_audit_result.invoice_id = created_invoice.id
            await store.create_audit_result(sample_audit_result)

            result = await store.get_audit_result(created_invoice.id)

            # Verify ArithmeticCheckContainer
            assert isinstance(result.arithmetic_check, ArithmeticCheckContainer)
            assert result.arithmetic_check.overall_status == "PASS"

            # Verify issues
            assert len(result.issues) == 1
            assert isinstance(result.issues[0], AuditIssue)
            assert result.issues[0].level == "warning"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_list_audit_results_returns_history(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """list_audit_results() returns audit history."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            created_invoice = await store.create_invoice(sample_invoice)

            # Create multiple audit results
            for i in range(3):
                audit = AuditResult(
                    invoice_id=created_invoice.id,
                    trace_id=f"trace-{i}",
                    success=True,
                    status=AuditStatus.PASS,
                )
                await store.create_audit_result(audit)

            results = await store.list_audit_results(invoice_id=created_invoice.id)
            assert len(results) == 3

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreGetItemsForIndexing:
    """Tests for get_items_for_indexing()."""

    @pytest.mark.asyncio
    async def test_get_items_for_indexing_returns_items(
        self, initialized_db, sample_invoice, mock_settings
    ):
        """get_items_for_indexing() returns line items."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()
            sample_invoice.doc_id = created_doc.id
            await store.create_invoice(sample_invoice)

            items = await store.get_items_for_indexing(last_item_id=0, limit=10)

            assert isinstance(items, list)
            assert len(items) == 2  # Two line items from sample_invoice
            assert items[0]["item_name"] == "Widget A"
            assert items[1]["item_name"] == "Widget B"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_items_for_indexing_incremental(
        self, initialized_db, mock_settings
    ):
        """get_items_for_indexing() supports incremental indexing."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()

            # Create invoice with many items
            invoice = Invoice(
                doc_id=created_doc.id,
                invoice_no="INV-001",
                items=[
                    LineItem(
                        line_number=i,
                        item_name=f"Item {i}",
                        quantity=1,
                        unit_price=10,
                        total_price=10,
                        row_type=RowType.LINE_ITEM,
                    )
                    for i in range(10)
                ],
            )
            await store.create_invoice(invoice)

            # Get first batch
            first_batch = await store.get_items_for_indexing(last_item_id=0, limit=5)
            assert len(first_batch) == 5

            # Get second batch
            last_id = first_batch[-1]["id"]
            second_batch = await store.get_items_for_indexing(last_item_id=last_id, limit=5)
            assert len(second_batch) == 5
            assert all(item["id"] > last_id for item in second_batch)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteInvoiceStoreRowConversion:
    """Tests for row-to-entity conversion methods."""

    @pytest.mark.asyncio
    async def test_row_to_invoice_converts_enums(
        self, initialized_db, mock_settings
    ):
        """_row_to_invoice() converts status enums correctly."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()

            invoice = Invoice(
                doc_id=created_doc.id,
                invoice_no="INV-001",
                parsing_status=ParsingStatus.PARTIAL,
            )
            created = await store.create_invoice(invoice)

            result = await store.get_invoice(created.id)
            assert isinstance(result.parsing_status, ParsingStatus)
            assert result.parsing_status == ParsingStatus.PARTIAL

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_row_to_item_converts_row_type(
        self, initialized_db, mock_settings
    ):
        """_row_to_item() converts row_type enum correctly."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            from src.infrastructure.storage.sqlite.document_store import (
                SQLiteDocumentStore,
            )

            doc_store = SQLiteDocumentStore()
            doc = Document(filename="test.pdf", original_filename="test.pdf", file_path="/uploads/test.pdf")
            created_doc = await doc_store.create_document(doc)

            store = SQLiteInvoiceStore()

            invoice = Invoice(
                doc_id=created_doc.id,
                invoice_no="INV-001",
                items=[
                    LineItem(
                        line_number=1,
                        item_name="Test",
                        quantity=1,
                        unit_price=10,
                        total_price=10,
                        row_type=RowType.SUBTOTAL,
                    ),
                ],
            )
            created = await store.create_invoice(invoice)

            result = await store.get_invoice(created.id)
            assert isinstance(result.items[0].row_type, RowType)
            assert result.items[0].row_type == RowType.SUBTOTAL

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()
