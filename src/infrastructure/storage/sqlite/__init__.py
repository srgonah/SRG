"""SQLite storage implementations."""

from src.infrastructure.storage.sqlite.company_document_store import (
    SQLiteCompanyDocumentStore,
)
from src.infrastructure.storage.sqlite.connection import (
    ConnectionPool,
    close_pool,
    get_connection,
    get_pool,
    get_transaction,
)
from src.infrastructure.storage.sqlite.document_store import SQLiteDocumentStore
from src.infrastructure.storage.sqlite.indexing_state_store import SQLiteIndexingStateStore
from src.infrastructure.storage.sqlite.inventory_store import SQLiteInventoryStore
from src.infrastructure.storage.sqlite.invoice_store import SQLiteInvoiceStore
from src.infrastructure.storage.sqlite.material_store import SQLiteMaterialStore
from src.infrastructure.storage.sqlite.price_history_store import SQLitePriceHistoryStore
from src.infrastructure.storage.sqlite.reminder_store import SQLiteReminderStore
from src.infrastructure.storage.sqlite.sales_store import SQLiteSalesStore
from src.infrastructure.storage.sqlite.session_store import SQLiteSessionStore

# Type aliases for convenience
DocumentStore = SQLiteDocumentStore
InvoiceStore = SQLiteInvoiceStore
SessionStore = SQLiteSessionStore
MaterialStore = SQLiteMaterialStore
PriceHistoryStore = SQLitePriceHistoryStore
CompanyDocumentStore = SQLiteCompanyDocumentStore
InventoryStore = SQLiteInventoryStore
SalesStore = SQLiteSalesStore
ReminderStore = SQLiteReminderStore

# Aliases for backward compatibility
get_connection_pool = get_pool
close_connection_pool = close_pool

# Singleton instances
_document_store: SQLiteDocumentStore | None = None
_invoice_store: SQLiteInvoiceStore | None = None
_session_store: SQLiteSessionStore | None = None
_material_store: SQLiteMaterialStore | None = None
_price_history_store: SQLitePriceHistoryStore | None = None
_company_document_store: SQLiteCompanyDocumentStore | None = None
_inventory_store: SQLiteInventoryStore | None = None
_sales_store: SQLiteSalesStore | None = None
_reminder_store: SQLiteReminderStore | None = None
_indexing_state_store: SQLiteIndexingStateStore | None = None


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


async def get_material_store() -> SQLiteMaterialStore:
    """Get singleton material store instance."""
    global _material_store
    if _material_store is None:
        _material_store = SQLiteMaterialStore()
    return _material_store


async def get_price_history_store() -> SQLitePriceHistoryStore:
    """Get singleton price history store instance."""
    global _price_history_store
    if _price_history_store is None:
        _price_history_store = SQLitePriceHistoryStore()
    return _price_history_store


async def get_company_document_store() -> SQLiteCompanyDocumentStore:
    """Get singleton company document store instance."""
    global _company_document_store
    if _company_document_store is None:
        _company_document_store = SQLiteCompanyDocumentStore()
    return _company_document_store


async def get_inventory_store() -> SQLiteInventoryStore:
    """Get singleton inventory store instance."""
    global _inventory_store
    if _inventory_store is None:
        _inventory_store = SQLiteInventoryStore()
    return _inventory_store


async def get_sales_store() -> SQLiteSalesStore:
    """Get singleton sales store instance."""
    global _sales_store
    if _sales_store is None:
        _sales_store = SQLiteSalesStore()
    return _sales_store


async def get_reminder_store() -> SQLiteReminderStore:
    """Get singleton reminder store instance."""
    global _reminder_store
    if _reminder_store is None:
        _reminder_store = SQLiteReminderStore()
    return _reminder_store


async def get_indexing_state_store() -> SQLiteIndexingStateStore:
    """Get singleton indexing state store instance."""
    global _indexing_state_store
    if _indexing_state_store is None:
        _indexing_state_store = SQLiteIndexingStateStore()
    return _indexing_state_store


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
    "SQLiteIndexingStateStore",
    "SQLiteInventoryStore",
    "SQLiteInvoiceStore",
    "SQLiteSessionStore",
    "SQLiteMaterialStore",
    "SQLitePriceHistoryStore",
    "SQLiteCompanyDocumentStore",
    "SQLiteReminderStore",
    "SQLiteSalesStore",
    # Type aliases
    "DocumentStore",
    "InventoryStore",
    "InvoiceStore",
    "SessionStore",
    "MaterialStore",
    "PriceHistoryStore",
    "CompanyDocumentStore",
    "ReminderStore",
    "SalesStore",
    # Factory functions
    "get_document_store",
    "get_indexing_state_store",
    "get_inventory_store",
    "get_invoice_store",
    "get_session_store",
    "get_material_store",
    "get_price_history_store",
    "get_company_document_store",
    "get_reminder_store",
    "get_sales_store",
]
