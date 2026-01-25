"""Data Transfer Objects for API layer.

Request DTOs: Validate and parse incoming API requests.
Response DTOs: Structure and serialize API responses.

These are the ONLY contracts between API handlers and use cases.
"""

from src.application.dto.requests import (
    AuditInvoiceRequest,
    ChatRequest,
    CreateSessionRequest,
    IndexDirectoryRequest,
    IndexDocumentRequest,
    SearchDocumentsRequest,
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
    MemoryUpdateResponse,
    PaginatedResponse,
    ProviderHealthResponse,
    SearchDocumentsResponse,
    SearchResponse,
    SearchResultResponse,
    SessionListResponse,
    SessionResponse,
    SourceCitationResponse,
    UploadInvoiceResponse,
)

__all__ = [
    # Requests
    "UploadInvoiceRequest",
    "AuditInvoiceRequest",
    "SearchRequest",
    "SearchDocumentsRequest",
    "ChatRequest",
    "CreateSessionRequest",
    "IndexDocumentRequest",
    "IndexDirectoryRequest",
    # Responses
    "UploadInvoiceResponse",
    "InvoiceResponse",
    "LineItemResponse",
    "AuditResultResponse",
    "AuditFindingResponse",
    "SearchResultResponse",
    "SearchResponse",
    "SearchDocumentsResponse",
    "ChatMessageResponse",
    "ChatResponse",
    "SourceCitationResponse",
    "MemoryUpdateResponse",
    "SessionResponse",
    "SessionListResponse",
    "DocumentResponse",
    "DocumentListResponse",
    "IndexingStatsResponse",
    "HealthResponse",
    "ProviderHealthResponse",
    "ErrorResponse",
    "PaginatedResponse",
]
