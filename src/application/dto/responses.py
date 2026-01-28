"""Response DTOs for API endpoints.

Pydantic v2 models for API response serialization.
These are the ONLY contracts between use cases and API layer.
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class CatalogSuggestionResponse(BaseModel):
    """Candidate material suggestion for unmatched items."""

    material_id: str = Field(..., description="Material ID")
    name: str = Field(..., description="Material name")
    normalized_name: str = Field(..., description="Normalized material name")
    hs_code: str | None = Field(default=None, description="HS code")
    unit: str | None = Field(default=None, description="Unit of measure")


class LineItemResponse(BaseModel):
    """Line item in invoice response."""

    description: str = Field(..., description="Item description")
    quantity: float = Field(..., description="Quantity ordered")
    unit: str | None = Field(default=None, description="Unit of measure")
    unit_price: float = Field(..., description="Price per unit")
    total_price: float = Field(..., description="Line total (qty * unit_price)")
    hs_code: str | None = Field(default=None, description="HS code if available")
    reference: str | None = Field(default=None, description="Item reference/SKU")
    matched_material_id: str | None = Field(
        default=None, description="Linked material ID if cataloged"
    )
    needs_catalog: bool = Field(
        default=False, description="True when item is a line item with no matched material"
    )
    catalog_suggestions: list[CatalogSuggestionResponse] = Field(
        default_factory=list,
        description="Top candidate materials for unmatched items",
    )


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
    """Standardized error response DTO.

    Every error response includes:
    - error_code: machine-readable code (e.g. INVOICE_NOT_FOUND)
    - message: human-readable description
    - hint: suggested recovery action
    - path: request path that triggered the error
    """

    error_code: str = Field(..., description="Machine-readable error code")
    message: str = Field(..., description="Human-readable error description")
    hint: str | None = Field(default=None, description="Suggested recovery action")
    detail: str | None = Field(default=None, description="Additional details")
    path: str | None = Field(default=None, description="Request path")
    timestamp: datetime = Field(default_factory=datetime.now)

    # Backward-compatible aliases
    @property
    def error(self) -> str:
        """Alias for message (backward compat)."""
        return self.message

    @property
    def code(self) -> str:
        """Alias for error_code (backward compat)."""
        return self.error_code


class PaginatedResponse(BaseModel):
    """Base for paginated responses."""

    total: int
    limit: int
    offset: int
    has_more: bool


# --- Catalog / Materials ---


class MaterialSynonymResponse(BaseModel):
    """Material synonym in response."""

    id: str
    synonym: str
    language: str = "en"


class MaterialResponse(BaseModel):
    """Material catalog entry response."""

    id: str
    name: str
    normalized_name: str
    hs_code: str | None = None
    category: str | None = None
    unit: str | None = None
    description: str | None = None
    brand: str | None = None
    source_url: str | None = None
    origin_country: str | None = None
    origin_confidence: str = "unknown"
    synonyms: list[MaterialSynonymResponse] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class MaterialListResponse(BaseModel):
    """Paginated list of materials."""

    materials: list[MaterialResponse]
    total: int


# --- Price History ---


class PriceHistoryEntryResponse(BaseModel):
    """Single price history entry."""

    item_name: str
    hs_code: str | None = None
    seller_name: str | None = None
    invoice_date: str | None = None
    quantity: float
    unit_price: float
    currency: str = "USD"


class PriceHistoryResponse(BaseModel):
    """Price history query response."""

    entries: list[PriceHistoryEntryResponse]
    total: int


class PriceStatsResponse(BaseModel):
    """Price statistics for an item."""

    item_name: str
    hs_code: str | None = None
    seller_name: str | None = None
    currency: str = "USD"
    occurrence_count: int = 0
    min_price: float = 0.0
    max_price: float = 0.0
    avg_price: float = 0.0
    price_trend: str | None = None
    first_seen: str | None = None
    last_seen: str | None = None


class PriceStatsListResponse(BaseModel):
    """List of price statistics."""

    stats: list[PriceStatsResponse]
    total: int


# --- Add to Catalog ---


class AddToCatalogResponse(BaseModel):
    """Response for add-to-catalog operation."""

    materials_created: int = 0
    materials_updated: int = 0
    materials: list[MaterialResponse] = Field(default_factory=list)


# --- Proforma PDF ---


class ProformaPdfResponse(BaseModel):
    """Response for proforma PDF generation."""

    invoice_id: str
    file_path: str
    file_size: int


# --- Company Documents ---


class CompanyDocumentResponse(BaseModel):
    """Company document response DTO."""

    id: int
    company_key: str
    title: str
    document_type: str
    file_path: str | None = None
    doc_id: int | None = None
    expiry_date: date | None = None
    issued_date: date | None = None
    issuer: str | None = None
    notes: str | None = None
    is_expired: bool = False
    days_until_expiry: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class CompanyDocumentListResponse(BaseModel):
    """Paginated list of company documents."""

    documents: list[CompanyDocumentResponse]
    total: int


# --- Reminders ---


class ReminderResponse(BaseModel):
    """Reminder response DTO."""

    id: int
    title: str
    message: str = ""
    due_date: date
    is_done: bool = False
    is_overdue: bool = False
    linked_entity_type: str | None = None
    linked_entity_id: int | None = None
    created_at: datetime
    updated_at: datetime


class ReminderListResponse(BaseModel):
    """Paginated list of reminders."""

    reminders: list[ReminderResponse]
    total: int


# --- Material Ingestion ---


class ExpiryCheckResponse(BaseModel):
    """Response for expiring document check."""

    total_expiring: int = Field(..., description="Total documents expiring within window")
    reminders_created: int = Field(..., description="New reminders created")
    already_reminded: int = Field(..., description="Documents that already had active reminders")
    created_reminder_ids: list[int] = Field(
        default_factory=list, description="IDs of newly created reminders"
    )


class IngestMaterialResponse(BaseModel):
    """Response for material ingestion from external URL."""

    material: MaterialResponse
    created: bool = Field(
        ..., description="True if a new material was created, False if existing was updated"
    )
    synonyms_added: list[str] = Field(
        default_factory=list, description="Synonyms that were added"
    )
    source_url: str = Field(..., description="URL the data was ingested from")
    brand: str | None = Field(default=None, description="Extracted brand")
    origin_country: str | None = Field(default=None, description="Extracted country of origin")
    origin_confidence: str = Field(default="unknown", description="Confidence in origin data")
    evidence_text: str | None = Field(default=None, description="Evidence for origin inference")


# --- Inventory ---


class StockMovementResponse(BaseModel):
    """Stock movement response DTO."""

    id: int
    movement_type: str
    quantity: float
    unit_cost: float
    reference: str | None = None
    notes: str | None = None
    movement_date: date
    created_at: datetime


class InventoryItemResponse(BaseModel):
    """Inventory item response DTO."""

    id: int
    material_id: str
    quantity_on_hand: float
    avg_cost: float
    total_value: float
    last_movement_date: date | None = None
    created_at: datetime
    updated_at: datetime


class ReceiveStockResponse(BaseModel):
    """Response for stock receive operation."""

    inventory_item: InventoryItemResponse
    movement: StockMovementResponse
    created: bool = False  # True if new inventory item was created


class IssueStockResponse(BaseModel):
    """Response for stock issue operation."""

    inventory_item: InventoryItemResponse
    movement: StockMovementResponse


class InventoryStatusResponse(BaseModel):
    """Paginated inventory status response."""

    items: list[InventoryItemResponse]
    total: int


# --- Local Sales ---


class LocalSalesItemResponse(BaseModel):
    """Local sales item response DTO."""

    id: int
    inventory_item_id: int
    material_id: str
    description: str
    quantity: float
    unit_price: float
    cost_basis: float
    line_total: float
    profit: float


class LocalSalesInvoiceResponse(BaseModel):
    """Local sales invoice response DTO."""

    id: int
    invoice_number: str
    customer_name: str
    sale_date: date
    subtotal: float
    tax_amount: float
    total_amount: float
    total_cost: float
    total_profit: float
    notes: str | None = None
    items: list[LocalSalesItemResponse]
    created_at: datetime


class SalesInvoiceListResponse(BaseModel):
    """Paginated list of sales invoices."""

    invoices: list[LocalSalesInvoiceResponse]
    total: int


# --- Reminder Intelligence / Insights ---


class InsightResponse(BaseModel):
    """Single insight detected by reminder intelligence."""

    category: str
    severity: str
    title: str
    message: str = ""
    suggested_due_date: date | None = None
    linked_entity_type: str | None = None
    linked_entity_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class InsightsEvaluationResponse(BaseModel):
    """Response for insight evaluation endpoint."""

    total_insights: int
    expiring_documents: int = 0
    unmatched_items: int = 0
    price_anomalies: int = 0
    insights: list[InsightResponse] = Field(default_factory=list)
    reminders_created: int = 0
    created_reminder_ids: list[int] = Field(default_factory=list)
