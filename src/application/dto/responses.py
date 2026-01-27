"""Response DTOs for API endpoints.

Pydantic v2 models for API response serialization.
These are the ONLY contracts between use cases and API layer.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class LineItemResponse(BaseModel):
    """Line item in invoice response."""

    description: str = Field(..., description="Item description")
    quantity: float = Field(..., description="Quantity ordered")
    unit: str | None = Field(default=None, description="Unit of measure")
    unit_price: float = Field(..., description="Price per unit")
    total_price: float = Field(..., description="Line total (qty * unit_price)")
    hs_code: str | None = Field(default=None, description="HS code if available")
    reference: str | None = Field(default=None, description="Item reference/SKU")


class InvoiceResponse(BaseModel):
    """Invoice response DTO."""

    id: str = Field(..., description="Invoice ID")
    document_id: str | None = Field(default=None, description="Linked document ID")
    invoice_number: str | None = Field(default=None, description="Invoice number")
    vendor_name: str | None = Field(default=None, description="Vendor/seller name")
    vendor_address: str | None = Field(default=None, description="Vendor address")
    buyer_name: str | None = Field(default=None, description="Buyer name")
    invoice_date: date | None = Field(default=None, description="Invoice date")
    due_date: date | None = Field(default=None, description="Payment due date")
    subtotal: float | None = Field(default=None, description="Subtotal before tax")
    tax_amount: float | None = Field(default=None, description="Tax amount")
    total_amount: float | None = Field(default=None, description="Total amount")
    currency: str = Field(default="USD", description="Currency code")
    line_items: list[LineItemResponse] = Field(default=[], description="Line items")
    calculated_total: float = Field(..., description="Sum of line item totals")
    source_file: str | None = Field(default=None, description="Source filename")
    parsed_at: datetime = Field(..., description="Parsing timestamp")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Parse confidence")
    parser_used: str | None = Field(default=None, description="Parser that was used")


class UploadInvoiceResponse(BaseModel):
    """Response for invoice upload use case.

    Contains the parsed invoice, document reference, and optional audit result.
    """

    document_id: str = Field(..., description="Created document ID")
    invoice_id: str = Field(..., description="Created invoice ID")
    invoice: InvoiceResponse = Field(..., description="Parsed invoice data")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Overall confidence score")
    warnings: list[str] = Field(default=[], description="Parsing warnings")
    audit: "AuditResultResponse | None" = Field(
        default=None, description="Audit result if auto_audit was enabled"
    )
    indexed: bool = Field(default=False, description="Whether document was indexed")


class AuditFindingResponse(BaseModel):
    """Individual audit finding."""

    code: str = Field(..., description="Finding code (e.g., MATH_ERROR)")
    category: str = Field(..., description="Finding category")
    severity: str = Field(..., description="Severity: error, warning, info")
    message: str = Field(..., description="Human-readable message")
    field: str | None = Field(default=None, description="Affected field path")
    expected: str | None = Field(default=None, description="Expected value")
    actual: str | None = Field(default=None, description="Actual value found")


class AuditResultResponse(BaseModel):
    """Audit result response DTO.

    Contains comprehensive audit findings with summary statistics.
    """

    id: str = Field(..., description="Audit result ID")
    invoice_id: str = Field(..., description="Audited invoice ID")
    passed: bool = Field(..., description="Whether audit passed (no errors)")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Audit confidence score")
    findings: list[AuditFindingResponse] = Field(default=[], description="All findings")
    summary: str | None = Field(default=None, description="LLM-generated summary")
    audited_at: datetime = Field(..., description="Audit timestamp")
    error_count: int = Field(..., ge=0, description="Number of errors")
    warning_count: int = Field(..., ge=0, description="Number of warnings")
    llm_used: bool = Field(default=False, description="Whether LLM was used")
    duration_ms: float | None = Field(default=None, description="Audit duration in ms")


class SearchResultResponse(BaseModel):
    """Single search result with relevance score and metadata."""

    chunk_id: str = Field(..., description="Chunk ID")
    document_id: str = Field(..., description="Source document ID")
    content: str = Field(..., description="Matched text content")
    score: float = Field(..., ge=0.0, description="Relevance score")
    metadata: dict[str, Any] = Field(default={}, description="Additional metadata")
    page_number: int | None = Field(default=None, description="Source page number")
    file_name: str | None = Field(default=None, description="Source filename")
    highlight: str | None = Field(default=None, description="Highlighted snippet")


class SearchDocumentsResponse(BaseModel):
    """Search response DTO with results and timing.

    Contains search results along with query metadata.
    """

    query: str = Field(..., description="Original search query")
    results: list[SearchResultResponse] = Field(default=[], description="Search results")
    total: int = Field(..., ge=0, description="Total results returned")
    search_type: str = Field(..., description="Search type used")
    took_ms: float = Field(..., ge=0, description="Search duration in milliseconds")
    cache_hit: bool = Field(default=False, description="Whether result was from cache")
    reranked: bool = Field(default=False, description="Whether reranking was applied")


# Alias for backward compatibility
SearchResponse = SearchDocumentsResponse


class SourceCitationResponse(BaseModel):
    """Source citation for RAG responses."""

    document_id: str = Field(..., description="Source document ID")
    chunk_id: str = Field(..., description="Source chunk ID")
    file_name: str | None = Field(default=None, description="Source filename")
    page_number: int | None = Field(default=None, description="Page number")
    relevance_score: float = Field(..., ge=0.0, le=1.0, description="Relevance score")
    snippet: str | None = Field(default=None, description="Relevant text snippet")


class MemoryUpdateResponse(BaseModel):
    """Memory fact extracted from conversation."""

    fact_type: str = Field(..., description="Type of fact (entity, preference, etc.)")
    content: str = Field(..., description="Fact content")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Extraction confidence")


class ChatMessageResponse(BaseModel):
    """Chat message response."""

    id: str = Field(..., description="Message ID")
    role: str = Field(..., description="Role: user, assistant, system")
    content: str = Field(..., description="Message content")
    created_at: datetime = Field(..., description="Creation timestamp")
    context_used: str | None = Field(default=None, description="RAG context if used")
    token_count: int | None = Field(default=None, description="Token count")


class ChatResponse(BaseModel):
    """Chat response DTO with RAG context and citations.

    Contains the assistant response along with session info and sources.
    """

    session_id: str = Field(..., description="Chat session ID")
    message: ChatMessageResponse = Field(..., description="Assistant response")
    context_chunks: int = Field(default=0, ge=0, description="Number of RAG chunks used")
    citations: list[SourceCitationResponse] = Field(
        default=[], description="Source citations"
    )
    memory_updates: list[MemoryUpdateResponse] = Field(
        default=[], description="Memory facts extracted"
    )
    is_new_session: bool = Field(default=False, description="Whether new session was created")


class SessionResponse(BaseModel):
    """Session response DTO."""

    id: str
    title: str
    message_count: int
    created_at: datetime
    updated_at: datetime
    metadata: dict[str, Any] = {}


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
    metadata: dict[str, Any] = {}


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
