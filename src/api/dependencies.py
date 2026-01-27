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
    AuditInvoiceUseCase,
    ChatWithContextUseCase,
    SearchDocumentsUseCase,
    UploadInvoiceUseCase,
)
from src.config import Settings, get_settings
from src.core.services import (
    ChatService,
    DocumentIndexerService,
    InvoiceAuditorService,
    InvoiceParserService,
    SearchService,
)
from src.infrastructure.llm import get_llm_provider
from src.infrastructure.storage.sqlite import (
    get_document_store,
    get_invoice_store,
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
async def get_doc_store():
    """Get document store."""
    return await get_document_store()


async def get_inv_store():
    """Get invoice store."""
    return await get_invoice_store()


async def get_sess_store():
    """Get session store."""
    return await get_session_store()


# LLM dependency
def get_llm():
    """Get LLM provider."""
    return get_llm_provider()
