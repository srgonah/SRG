"""
Application layer - Use cases, DTOs, and service factories.

This layer orchestrates business logic by:
1. Defining request/response DTOs for API contracts
2. Implementing use cases that coordinate core services
3. Providing factory functions for dependency injection

Use cases are the only entry point for API handlers.
"""

from src.application.dto.requests import (
    AuditInvoiceRequest,
    ChatRequest,
    CreateSessionRequest,
    IndexDirectoryRequest,
    IndexDocumentRequest,
    SearchRequest,
    UploadInvoiceRequest,
)
from src.application.dto.responses import (
    AuditFindingResponse,
    AuditResultResponse,
    ChatMessageResponse,
    ChatResponse,
    DocumentListResponse,
    DocumentResponse,
    ErrorResponse,
    HealthResponse,
    IndexingStatsResponse,
    InvoiceResponse,
    LineItemResponse,
    PaginatedResponse,
    ProviderHealthResponse,
    SearchResponse,
    SearchResultResponse,
    SessionListResponse,
    SessionResponse,
)
from src.application.services import (
    get_chat_service,
    get_document_indexer_service,
    get_invoice_auditor_service,
    get_invoice_parser_service,
    get_search_service,
    reset_services,
)
from src.application.use_cases import (
    AuditInvoiceUseCase,
    ChatWithContextUseCase,
    SearchDocumentsUseCase,
    UploadInvoiceUseCase,
)

__all__ = [
    # Request DTOs
    "UploadInvoiceRequest",
    "AuditInvoiceRequest",
    "SearchRequest",
    "ChatRequest",
    "CreateSessionRequest",
    "IndexDocumentRequest",
    "IndexDirectoryRequest",
    # Response DTOs
    "InvoiceResponse",
    "LineItemResponse",
    "AuditResultResponse",
    "AuditFindingResponse",
    "SearchResponse",
    "SearchResultResponse",
    "ChatResponse",
    "ChatMessageResponse",
    "SessionResponse",
    "SessionListResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "IndexingStatsResponse",
    "HealthResponse",
    "ProviderHealthResponse",
    "ErrorResponse",
    "PaginatedResponse",
    # Use Cases
    "UploadInvoiceUseCase",
    "AuditInvoiceUseCase",
    "SearchDocumentsUseCase",
    "ChatWithContextUseCase",
    # Service factories
    "get_invoice_parser_service",
    "get_invoice_auditor_service",
    "get_document_indexer_service",
    "get_search_service",
    "get_chat_service",
    "reset_services",
]
