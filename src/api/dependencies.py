"""
Dependency injection container for FastAPI.

Provides service instances to route handlers.
"""

from functools import lru_cache

from src.application.services import (
    get_chat_service,
    get_document_indexer_service,
    get_invoice_auditor_service,
    get_invoice_parser_service,
    get_search_service,
)
from src.application.use_cases import (
    AddToCatalogUseCase,
    AuditInvoiceUseCase,
    ChatWithContextUseCase,
    CheckExpiringDocumentsUseCase,
    CreateSalesInvoiceUseCase,
    CreateSalesPdfUseCase,
    EvaluateReminderInsightsUseCase,
    GenerateProformaPdfUseCase,
    IngestMaterialUseCase,
    IssueStockUseCase,
    ReceiveStockUseCase,
    SearchDocumentsUseCase,
    UploadInvoiceUseCase,
)
from src.config import Settings, get_settings
from src.core.interfaces import ILLMProvider
from src.core.services import (
    CatalogMatcher,
    ChatService,
    DocumentIndexerService,
    InvoiceAuditorService,
    InvoiceParserService,
    SearchService,
)
from src.infrastructure.llm import get_llm_provider
from src.infrastructure.storage.sqlite import (
    SQLiteCompanyDocumentStore,
    SQLiteDocumentStore,
    SQLiteInventoryStore,
    SQLiteInvoiceStore,
    SQLiteMaterialStore,
    SQLitePriceHistoryStore,
    SQLiteReminderStore,
    SQLiteSalesStore,
    SQLiteSessionStore,
    get_company_document_store,
    get_document_store,
    get_inventory_store,
    get_invoice_store,
    get_material_store,
    get_price_history_store,
    get_reminder_store,
    get_sales_store,
    get_session_store,
)


@lru_cache
def get_app_settings() -> Settings:
    """Get cached application settings."""
    return get_settings()


# Service dependencies
def get_parser_service() -> InvoiceParserService:
    """Get invoice parser service."""
    return get_invoice_parser_service()


def get_auditor_service() -> InvoiceAuditorService:
    """Get invoice auditor service."""
    return get_invoice_auditor_service()


def get_search() -> SearchService:
    """Get search service."""
    return get_search_service()


async def get_chat() -> ChatService:
    """Get chat service."""
    return await get_chat_service()


async def get_indexer() -> DocumentIndexerService:
    """Get document indexer service."""
    return await get_document_indexer_service()


# Use case dependencies
def get_upload_invoice_use_case() -> UploadInvoiceUseCase:
    """Get upload invoice use case."""
    return UploadInvoiceUseCase()


def get_audit_invoice_use_case() -> AuditInvoiceUseCase:
    """Get audit invoice use case."""
    return AuditInvoiceUseCase()


def get_search_documents_use_case() -> SearchDocumentsUseCase:
    """Get search documents use case."""
    return SearchDocumentsUseCase()


async def get_chat_use_case() -> ChatWithContextUseCase:
    """Get chat use case."""
    return ChatWithContextUseCase()


# Store dependencies
async def get_doc_store() -> SQLiteDocumentStore:
    """Get document store."""
    return await get_document_store()


async def get_inv_store() -> SQLiteInvoiceStore:
    """Get invoice store."""
    return await get_invoice_store()


async def get_sess_store() -> SQLiteSessionStore:
    """Get session store."""
    return await get_session_store()


# Catalog dependencies
async def get_mat_store() -> SQLiteMaterialStore:
    """Get material store."""
    return await get_material_store()


async def get_price_store() -> SQLitePriceHistoryStore:
    """Get price history store."""
    return await get_price_history_store()


def get_add_to_catalog_use_case() -> AddToCatalogUseCase:
    """Get add to catalog use case."""
    return AddToCatalogUseCase()


async def get_catalog_matcher() -> CatalogMatcher:
    """Get catalog matcher service."""
    mat_store = await get_material_store()
    return CatalogMatcher(material_store=mat_store)


# Company document store dependency
async def get_company_doc_store() -> SQLiteCompanyDocumentStore:
    """Get company document store."""
    return await get_company_document_store()


# Reminder store dependency
async def get_rem_store() -> SQLiteReminderStore:
    """Get reminder store."""
    return await get_reminder_store()


# Proforma PDF use case dependency
def get_generate_proforma_pdf_use_case() -> GenerateProformaPdfUseCase:
    """Get generate proforma PDF use case."""
    return GenerateProformaPdfUseCase()


# Ingestion use case dependency
def get_ingest_material_use_case() -> IngestMaterialUseCase:
    """Get ingest material use case."""
    return IngestMaterialUseCase()


# Evaluate insights use case dependency
def get_evaluate_insights_use_case() -> EvaluateReminderInsightsUseCase:
    """Get evaluate reminder insights use case."""
    return EvaluateReminderInsightsUseCase()


# Expiry check use case dependency
def get_check_expiring_documents_use_case() -> CheckExpiringDocumentsUseCase:
    """Get check expiring documents use case."""
    return CheckExpiringDocumentsUseCase()


# Inventory store dependency
async def get_inv_item_store() -> SQLiteInventoryStore:
    """Get inventory store."""
    return await get_inventory_store()


# Sales store dependency
async def get_sales_inv_store() -> SQLiteSalesStore:
    """Get sales store."""
    return await get_sales_store()


# Inventory use case dependencies
def get_receive_stock_use_case() -> ReceiveStockUseCase:
    """Get receive stock use case."""
    return ReceiveStockUseCase()


def get_issue_stock_use_case() -> IssueStockUseCase:
    """Get issue stock use case."""
    return IssueStockUseCase()


# Sales use case dependency
def get_create_sales_invoice_use_case() -> CreateSalesInvoiceUseCase:
    """Get create sales invoice use case."""
    return CreateSalesInvoiceUseCase()


# Sales PDF use case dependency
def get_create_sales_pdf_use_case() -> CreateSalesPdfUseCase:
    """Get create sales PDF use case."""
    return CreateSalesPdfUseCase()


# LLM dependency
def get_llm() -> ILLMProvider:
    """Get LLM provider."""
    return get_llm_provider()
