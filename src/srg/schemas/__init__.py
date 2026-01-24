"""Pydantic schemas for API request/response validation."""

from .chat import ChatRequest, ChatResponse
from .document import DocumentListResponse, DocumentResponse, IndexingStatsResponse
from .health import HealthResponse, ProviderHealth
from .invoice import AuditRequest, AuditResultResponse, InvoiceListResponse, InvoiceResponse
from .search import SearchRequest, SearchResponse, SearchResult
from .session import CreateSessionRequest, MessageResponse, SessionListResponse, SessionResponse

__all__ = [
    # Health
    "HealthResponse",
    "ProviderHealth",
    # Invoice
    "InvoiceResponse",
    "InvoiceListResponse",
    "AuditRequest",
    "AuditResultResponse",
    # Document
    "DocumentResponse",
    "DocumentListResponse",
    "IndexingStatsResponse",
    # Search
    "SearchRequest",
    "SearchResponse",
    "SearchResult",
    # Chat
    "ChatRequest",
    "ChatResponse",
    # Session
    "CreateSessionRequest",
    "SessionResponse",
    "SessionListResponse",
    "MessageResponse",
]
