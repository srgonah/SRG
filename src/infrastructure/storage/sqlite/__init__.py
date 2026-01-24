"""SQLite storage implementations."""

from src.infrastructure.storage.sqlite.connection import (
    ConnectionPool,
    close_pool,
    get_connection,
    get_pool,
    get_transaction,
)
from src.infrastructure.storage.sqlite.document_store import SQLiteDocumentStore
from src.infrastructure.storage.sqlite.invoice_store import SQLiteInvoiceStore
from src.infrastructure.storage.sqlite.session_store import SQLiteSessionStore

# Type aliases for convenience
DocumentStore = SQLiteDocumentStore
InvoiceStore = SQLiteInvoiceStore
SessionStore = SQLiteSessionStore

# Aliases for backward compatibility
get_connection_pool = get_pool
close_connection_pool = close_pool

# Singleton instances
_document_store: SQLiteDocumentStore | None = None
_invoice_store: SQLiteInvoiceStore | None = None
_session_store: SQLiteSessionStore | None = None


async def get_document_store() -> SQLiteDocumentStore:
    """Get singleton document store instance."""
    global _document_store
    if _document_store is None:
        _document_store = SQLiteDocumentStore()
    return _document_store


async def get_invoice_store() -> SQLiteInvoiceStore:
    """Get singleton invoice store instance."""
    global _invoice_store
    if _invoice_store is None:
        _invoice_store = SQLiteInvoiceStore()
    return _invoice_store


async def get_session_store() -> SQLiteSessionStore:
    """Get singleton session store instance."""
    global _session_store
    if _session_store is None:
        _session_store = SQLiteSessionStore()
    return _session_store


__all__ = [
    # Connection
    "ConnectionPool",
    "get_pool",
    "close_pool",
    "get_connection",
    "get_transaction",
    # Aliases for connection
    "get_connection_pool",
    "close_connection_pool",
    # Store classes
    "SQLiteDocumentStore",
    "SQLiteInvoiceStore",
    "SQLiteSessionStore",
    # Type aliases
    "DocumentStore",
    "InvoiceStore",
    "SessionStore",
    # Factory functions
    "get_document_store",
    "get_invoice_store",
    "get_session_store",
]
