"""Response DTOs for API endpoints."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class LineItemResponse(BaseModel):
    """Line item in invoice response."""

    description: str
    quantity: float
    unit: str | None = None
    unit_price: float
    total_price: float
    reference: str | None = None


class InvoiceResponse(BaseModel):
    """Invoice response DTO."""

    id: str
    document_id: str | None = None
    invoice_number: str | None = None
    vendor_name: str | None = None
    vendor_address: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    currency: str = "DZD"
    line_items: list[LineItemResponse] = []
    calculated_total: float
    source_file: str | None = None
    parsed_at: datetime
    confidence: float = 0.0


class AuditFindingResponse(BaseModel):
    """Audit finding response."""

    category: str
    severity: str
    message: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None


class AuditResultResponse(BaseModel):
    """Audit result response DTO."""

    id: str
    invoice_id: str
    passed: bool
    confidence: float
    findings: list[AuditFindingResponse]
    audited_at: datetime
    error_count: int
    warning_count: int


class SearchResultResponse(BaseModel):
    """Single search result."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict = {}
    page_number: int | None = None
    file_name: str | None = None


class SearchResponse(BaseModel):
    """Search response DTO."""

    query: str
    results: list[SearchResultResponse]
    total: int
    search_type: str
    took_ms: float


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: str
    role: str
    content: str
    created_at: datetime
    context_used: str | None = None


class ChatResponse(BaseModel):
    """Chat response DTO."""

    session_id: str
    message: ChatMessageResponse
    context_chunks: int = 0


class SessionResponse(BaseModel):
    """Session response DTO."""

    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    metadata: dict = {}


class SessionListResponse(BaseModel):
    """Session list response."""

    sessions: list[SessionResponse]
    total: int


class DocumentResponse(BaseModel):
    """Document response DTO."""

    id: str
    file_name: str
    file_path: str
    file_type: str
    file_size: int
    page_count: int = 0
    chunk_count: int = 0
    indexed_at: datetime | None = None
    metadata: dict = {}


class DocumentListResponse(BaseModel):
    """Document list response."""

    documents: list[DocumentResponse]
    total: int


class IndexingStatsResponse(BaseModel):
    """Indexing statistics response."""

    documents: int
    chunks: int
    vectors: int
    index_synced: bool


class ProviderHealthResponse(BaseModel):
    """Provider health status."""

    name: str
    available: bool
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str = "1.0.0"
    uptime_seconds: float
    llm: ProviderHealthResponse | None = None
    embedding: ProviderHealthResponse | None = None
    database: ProviderHealthResponse | None = None
    vector_store: ProviderHealthResponse | None = None


class ErrorResponse(BaseModel):
    """Error response DTO."""

    error: str
    detail: str | None = None
    code: str | None = None
    path: str | None = None
    timestamp: datetime = Field(default_factory=datetime.now)


class PaginatedResponse(BaseModel):
    """Base for paginated responses."""

    total: int
    limit: int
    offset: int
    has_more: bool
