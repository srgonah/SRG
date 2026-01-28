"""Unit tests for storage interface abstract classes."""

import pytest

from src.core.interfaces.storage import (
    IDocumentStore,
    IIndexingStateStore,
    IInvoiceStore,
    ISessionStore,
    IVectorStore,
)


class TestIDocumentStoreInterface:
    """Tests for IDocumentStore abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IDocumentStore()

    def test_document_operations_defined(self):
        """Verify document CRUD operations are defined."""
        document_methods = {
            "create_document",
            "get_document",
            "get_document_by_hash",
            "update_document",
            "delete_document",
            "list_documents",
        }
        actual = set(IDocumentStore.__abstractmethods__)
        assert document_methods.issubset(actual)

    def test_page_operations_defined(self):
        """Verify page operations are defined."""
        page_methods = {
            "create_page",
            "get_pages",
            "update_page",
        }
        actual = set(IDocumentStore.__abstractmethods__)
        assert page_methods.issubset(actual)

    def test_chunk_operations_defined(self):
        """Verify chunk operations are defined."""
        chunk_methods = {
            "create_chunks",
            "get_chunks",
            "get_chunk_by_id",
            "get_chunks_for_indexing",
        }
        actual = set(IDocumentStore.__abstractmethods__)
        assert chunk_methods.issubset(actual)

    def test_all_abstract_methods(self):
        """Verify complete list of abstract methods."""
        expected = {
            "create_document",
            "get_document",
            "get_document_by_hash",
            "update_document",
            "delete_document",
            "list_documents",
            "create_page",
            "get_pages",
            "update_page",
            "create_chunks",
            "get_chunks",
            "get_chunk_by_id",
            "get_chunks_for_indexing",
        }
        actual = set(IDocumentStore.__abstractmethods__)
        assert expected == actual


class TestIInvoiceStoreInterface:
    """Tests for IInvoiceStore abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IInvoiceStore()

    def test_invoice_operations_defined(self):
        """Verify invoice CRUD operations are defined."""
        invoice_methods = {
            "create_invoice",
            "get_invoice",
            "get_invoice_by_doc_id",
            "update_invoice",
            "delete_invoice",
            "list_invoices",
            "search_invoices",
        }
        actual = set(IInvoiceStore.__abstractmethods__)
        assert invoice_methods.issubset(actual)

    def test_audit_operations_defined(self):
        """Verify audit operations are defined."""
        audit_methods = {
            "create_audit_result",
            "get_audit_result",
            "list_audit_results",
        }
        actual = set(IInvoiceStore.__abstractmethods__)
        assert audit_methods.issubset(actual)

    def test_indexing_operations_defined(self):
        """Verify item indexing operations are defined."""
        assert "get_items_for_indexing" in IInvoiceStore.__abstractmethods__

    def test_all_abstract_methods(self):
        expected = {
            "create_invoice",
            "get_invoice",
            "get_invoice_by_doc_id",
            "update_invoice",
            "delete_invoice",
            "list_invoices",
            "search_invoices",
            "create_audit_result",
            "get_audit_result",
            "list_audit_results",
            "get_items_for_indexing",
            "update_item_material_id",
            "list_unmatched_items",
        }
        actual = set(IInvoiceStore.__abstractmethods__)
        assert expected == actual


class TestISessionStoreInterface:
    """Tests for ISessionStore abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ISessionStore()

    def test_session_operations_defined(self):
        """Verify session CRUD operations are defined."""
        session_methods = {
            "create_session",
            "get_session",
            "update_session",
            "delete_session",
            "list_sessions",
        }
        actual = set(ISessionStore.__abstractmethods__)
        assert session_methods.issubset(actual)

    def test_message_operations_defined(self):
        """Verify message operations are defined."""
        message_methods = {
            "add_message",
            "get_messages",
        }
        actual = set(ISessionStore.__abstractmethods__)
        assert message_methods.issubset(actual)

    def test_memory_operations_defined(self):
        """Verify memory fact operations are defined."""
        memory_methods = {
            "save_memory_fact",
            "get_memory_facts",
            "delete_memory_fact",
        }
        actual = set(ISessionStore.__abstractmethods__)
        assert memory_methods.issubset(actual)

    def test_all_abstract_methods(self):
        expected = {
            "create_session",
            "get_session",
            "update_session",
            "delete_session",
            "list_sessions",
            "add_message",
            "get_messages",
            "save_memory_fact",
            "get_memory_facts",
            "delete_memory_fact",
        }
        actual = set(ISessionStore.__abstractmethods__)
        assert expected == actual


class TestIVectorStoreInterface:
    """Tests for IVectorStore abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IVectorStore()

    def test_index_management_defined(self):
        """Verify index management operations are defined."""
        index_methods = {
            "build_index",
            "add_vectors",
            "save_index",
            "load_index",
            "get_index_stats",
        }
        actual = set(IVectorStore.__abstractmethods__)
        assert index_methods.issubset(actual)

    def test_search_defined(self):
        """Verify search operation is defined."""
        assert "search" in IVectorStore.__abstractmethods__

    def test_id_mapping_operations_defined(self):
        """Verify ID mapping operations are defined."""
        mapping_methods = {
            "save_id_mapping",
            "get_entity_id",
            "get_entity_ids",
        }
        actual = set(IVectorStore.__abstractmethods__)
        assert mapping_methods.issubset(actual)

    def test_all_abstract_methods(self):
        expected = {
            "build_index",
            "add_vectors",
            "search",
            "get_index_stats",
            "save_index",
            "load_index",
            "save_id_mapping",
            "get_entity_id",
            "get_entity_ids",
        }
        actual = set(IVectorStore.__abstractmethods__)
        assert expected == actual


class TestIIndexingStateStoreInterface:
    """Tests for IIndexingStateStore abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IIndexingStateStore()

    def test_all_abstract_methods(self):
        expected = {
            "get_state",
            "update_state",
            "reset_state",
        }
        actual = set(IIndexingStateStore.__abstractmethods__)
        assert expected == actual
