"""FastAPI dependencies for dependency injection."""

from typing import Annotated

from fastapi import Depends

from src.application.services import (
    get_chat_service,
    get_document_indexer_service,
    get_invoice_auditor_service,
    get_invoice_parser_service,
    get_search_service,
)
from src.core.services import (
    ChatService,
    DocumentIndexerService,
    InvoiceAuditorService,
    InvoiceParserService,
    SearchService,
)
from src.infrastructure.storage.sqlite import (
    DocumentStore,
    InvoiceStore,
    SessionStore,
    get_document_store,
    get_invoice_store,
    get_session_store,
)
from src.srg.config import Settings, get_settings

# Settings dependency
SettingsDep = Annotated[Settings, Depends(get_settings)]


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


# Typed dependencies
ParserServiceDep = Annotated[InvoiceParserService, Depends(get_parser_service)]
AuditorServiceDep = Annotated[InvoiceAuditorService, Depends(get_auditor_service)]
SearchServiceDep = Annotated[SearchService, Depends(get_search)]
ChatServiceDep = Annotated[ChatService, Depends(get_chat)]
IndexerServiceDep = Annotated[DocumentIndexerService, Depends(get_indexer)]


# Store dependencies
async def get_doc_store() -> DocumentStore:
    """Get document store."""
    return await get_document_store()


async def get_inv_store() -> InvoiceStore:
    """Get invoice store."""
    return await get_invoice_store()


async def get_sess_store() -> SessionStore:
    """Get session store."""
    return await get_session_store()


DocumentStoreDep = Annotated[DocumentStore, Depends(get_doc_store)]
InvoiceStoreDep = Annotated[InvoiceStore, Depends(get_inv_store)]
SessionStoreDep = Annotated[SessionStore, Depends(get_sess_store)]
