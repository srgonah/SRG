"""Data Transfer Objects for API layer."""

from src.application.dto.requests import (
    AuditInvoiceRequest,
    ChatRequest,
    CreateSessionRequest,
    IndexDocumentRequest,
    SearchRequest,
    UploadInvoiceRequest,
)
from src.application.dto.responses import (
    AuditFindingResponse,
    AuditResultResponse,
    ChatMessageResponse,
    ChatResponse,
    DocumentResponse,
    ErrorResponse,
    HealthResponse,
    IndexingStatsResponse,
    InvoiceResponse,
    LineItemResponse,
    SearchResponse,
    SearchResultResponse,
    SessionResponse,
)

__all__ = [
    # Requests
    "UploadInvoiceRequest",
    "AuditInvoiceRequest",
    "SearchRequest",
    "ChatRequest",
    "CreateSessionRequest",
    "IndexDocumentRequest",
    # Responses
    "InvoiceResponse",
    "LineItemResponse",
    "AuditResultResponse",
    "AuditFindingResponse",
    "SearchResultResponse",
    "SearchResponse",
    "ChatMessageResponse",
    "ChatResponse",
    "SessionResponse",
    "DocumentResponse",
    "IndexingStatsResponse",
    "HealthResponse",
    "ErrorResponse",
]
