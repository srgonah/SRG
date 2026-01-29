"""Request DTOs for API endpoints.

Pydantic v2 models for API request validation.
These are the ONLY contracts between API and use cases.
"""

from typing import Any

from pydantic import BaseModel, Field


class UploadInvoiceRequest(BaseModel):
    """Request for invoice upload.

    File content is handled separately via UploadFile in the API layer.
    """

    vendor_hint: str | None = Field(
        default=None,
        description="Hint for vendor detection (company name or key)",
        examples=["VOLTA HUB", "volta_hub"],
    )
    template_id: str | None = Field(
        default=None,
        description="Force specific template ID for parsing",
        examples=["volta_hub", "ain_alreem"],
    )
    source: str | None = Field(
        default=None,
        description="Source of the invoice (email, scan, upload, etc.)",
        examples=["email", "scan", "manual_upload"],
    )
    auto_audit: bool = Field(
        default=True,
        description="Automatically audit after parsing",
    )
    auto_catalog: bool = Field(
        default=True,
        description="Automatically match items to materials catalog",
    )
    auto_index: bool = Field(
        default=True,
        description="Automatically index for search after parsing",
    )
    strict_mode: bool = Field(
        default=False,
        description="Fail on parsing warnings instead of continuing",
    )


class AuditInvoiceRequest(BaseModel):
    """Request for invoice audit.

    Supports both rule-based and LLM-powered auditing.
    """

    invoice_id: str = Field(
        ...,
        description="Invoice ID to audit",
        examples=["inv_123", "12345"],
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM for semantic analysis (slower but more thorough)",
    )
    strict_mode: bool = Field(
        default=False,
        description="Treat warnings as errors",
    )
    rules: list[str] | None = Field(
        default=None,
        description="Specific rule codes to check (all rules if None)",
        examples=[["MATH_CHECK", "REQUIRED_FIELDS", "DATE_VALIDATION"]],
    )
    save_result: bool = Field(
        default=True,
        description="Save audit result to database",
    )


class SearchDocumentsRequest(BaseModel):
    """Request for document search.

    Supports hybrid (semantic + keyword), pure semantic, or pure keyword search.
    """

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query text",
        examples=["PVC cable prices", "invoice from VOLTA HUB"],
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of results to return",
    )
    search_type: str = Field(
        default="hybrid",
        pattern="^(hybrid|semantic|keyword)$",
        description="Search strategy: hybrid, semantic, or keyword",
    )
    use_reranker: bool = Field(
        default=True,
        description="Apply neural reranking for better relevance",
    )
    use_cache: bool = Field(
        default=True,
        description="Use cached results if available",
    )
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Metadata filters (e.g., {'vendor': 'VOLTA HUB', 'year': 2024})",
    )
    min_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Minimum relevance score threshold",
    )


# Alias for backward compatibility
SearchRequest = SearchDocumentsRequest


class ChatRequest(BaseModel):
    """Request for chat message.

    Supports RAG-enhanced conversations with session management.
    """

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User message content",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID to continue conversation (creates new if None)",
    )
    use_rag: bool = Field(
        default=True,
        description="Use RAG to retrieve relevant context",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Number of context chunks for RAG",
    )
    max_context_length: int = Field(
        default=4000,
        ge=500,
        le=16000,
        description="Maximum context length in characters",
    )
    stream: bool = Field(
        default=False,
        description="Stream response tokens as they're generated",
    )
    include_sources: bool = Field(
        default=True,
        description="Include source citations in response",
    )
    extract_memory: bool = Field(
        default=True,
        description="Extract and store memory facts from conversation",
    )


class CreateSessionRequest(BaseModel):
    """Request to create chat session."""

    title: str | None = Field(
        default=None,
        max_length=200,
        description="Session title",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Session metadata",
    )


class IndexDocumentRequest(BaseModel):
    """Request to index a document."""

    file_path: str = Field(
        ...,
        description="Path to document file",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Document metadata",
    )


class IndexDirectoryRequest(BaseModel):
    """Request to index a directory."""

    directory: str = Field(
        ...,
        description="Directory path",
    )
    recursive: bool = Field(
        default=True,
        description="Recurse into subdirectories",
    )
    extensions: list[str] | None = Field(
        default=None,
        description="File extensions to include",
    )


class AddToCatalogRequest(BaseModel):
    """Request to add invoice items to the materials catalog."""

    invoice_id: int = Field(
        ...,
        description="Invoice ID whose items to add to catalog",
    )
    item_ids: list[int] | None = Field(
        default=None,
        description="Specific item IDs to add (all LINE_ITEM rows if None)",
    )


class ManualMatchRequest(BaseModel):
    """Request to manually match an invoice item to a material."""

    material_id: str = Field(
        ...,
        description="Material catalog ID to match the item to",
    )


# --- Proforma PDF ---


class GenerateProformaPdfRequest(BaseModel):
    """Request to generate a proforma PDF for an invoice."""

    invoice_id: str = Field(
        ...,
        description="Invoice ID to generate proforma PDF for",
    )


# --- Company Documents ---


class CreateCompanyDocumentRequest(BaseModel):
    """Request to create a company document."""

    company_key: str = Field(..., description="Company identifier")
    title: str = Field(..., description="Document title")
    document_type: str = Field(
        default="other",
        description="Document type: license, certificate, permit, insurance, contract, other",
    )
    expiry_date: str | None = Field(
        default=None,
        description="Expiry date in ISO format (YYYY-MM-DD)",
    )
    issued_date: str | None = Field(
        default=None,
        description="Issued date in ISO format (YYYY-MM-DD)",
    )
    issuer: str | None = Field(default=None, description="Issuing authority")
    notes: str | None = Field(default=None, description="Additional notes")
    metadata: dict[str, Any] | None = Field(default=None, description="Extra metadata")


class UpdateCompanyDocumentRequest(BaseModel):
    """Request to update a company document."""

    company_key: str | None = Field(default=None, description="Company identifier")
    title: str | None = Field(default=None, description="Document title")
    document_type: str | None = Field(default=None, description="Document type")
    expiry_date: str | None = Field(default=None, description="Expiry date (YYYY-MM-DD)")
    issued_date: str | None = Field(default=None, description="Issued date (YYYY-MM-DD)")
    issuer: str | None = Field(default=None, description="Issuing authority")
    notes: str | None = Field(default=None, description="Additional notes")
    metadata: dict[str, Any] | None = Field(default=None, description="Extra metadata")


class ListExpiringDocumentsRequest(BaseModel):
    """Request to list expiring documents."""

    within_days: int = Field(
        default=30,
        ge=1,
        description="Number of days to look ahead for expiring documents",
    )


# --- Reminders ---


class CreateReminderRequest(BaseModel):
    """Request to create a reminder."""

    title: str = Field(..., description="Reminder title")
    message: str = Field(default="", description="Reminder message/details")
    due_date: str = Field(..., description="Due date in ISO format (YYYY-MM-DD)")
    linked_entity_type: str | None = Field(
        default=None,
        description="Linked entity type (e.g., 'invoice', 'company_document')",
    )
    linked_entity_id: int | None = Field(
        default=None,
        description="ID of the linked entity",
    )


class UpdateReminderRequest(BaseModel):
    """Request to update a reminder."""

    title: str | None = Field(default=None, description="Reminder title")
    message: str | None = Field(default=None, description="Reminder message")
    due_date: str | None = Field(default=None, description="Due date (YYYY-MM-DD)")
    is_done: bool | None = Field(default=None, description="Mark as done/undone")
    linked_entity_type: str | None = Field(default=None, description="Linked entity type")
    linked_entity_id: int | None = Field(default=None, description="Linked entity ID")


# --- Material Ingestion ---


class IngestMaterialRequest(BaseModel):
    """Request to ingest a material from an external product URL."""

    url: str = Field(
        ...,
        description="Product page URL (e.g., https://amazon.ae/dp/...)",
        examples=["https://www.amazon.ae/dp/B09V3KXJPB"],
    )
    category: str | None = Field(
        default=None,
        description="Optional material category override",
    )
    unit: str | None = Field(
        default=None,
        description="Optional unit of measure override (e.g., PCS, M, KG)",
    )


class BatchIngestMaterialRequest(BaseModel):
    """Request to ingest materials from multiple external product URLs."""

    urls: list[str] = Field(
        ...,
        min_length=1,
        max_length=20,
        description="List of product page URLs (max 20)",
        examples=[
            [
                "https://www.amazon.ae/dp/B09V3KXJPB",
                "https://www.amazon.ae/dp/B08N5WRWNW",
            ]
        ],
    )
    category: str | None = Field(
        default=None,
        description="Optional material category override (applied to all)",
    )
    unit: str | None = Field(
        default=None,
        description="Optional unit of measure override (applied to all)",
    )


class PreviewIngestRequest(BaseModel):
    """Request to preview product data from a URL without saving."""

    url: str = Field(
        ...,
        description="Product page URL to preview",
        examples=["https://www.amazon.ae/dp/B09V3KXJPB"],
    )


# --- Inventory ---


class ReceiveStockRequest(BaseModel):
    """Request to receive stock (IN movement)."""

    material_id: str = Field(..., description="Material catalog ID")
    quantity: float = Field(..., gt=0, description="Quantity to receive")
    unit_cost: float = Field(..., ge=0, description="Cost per unit")
    reference: str | None = Field(default=None, description="PO or invoice reference")
    notes: str | None = Field(default=None, description="Additional notes")
    movement_date: str | None = Field(
        default=None,
        description="Movement date in ISO format (defaults to today)",
    )


class IssueStockRequest(BaseModel):
    """Request to issue stock (OUT movement)."""

    material_id: str = Field(..., description="Material catalog ID")
    quantity: float = Field(..., gt=0, description="Quantity to issue")
    reference: str | None = Field(default=None, description="Reference number")
    notes: str | None = Field(default=None, description="Additional notes")
    movement_date: str | None = Field(
        default=None,
        description="Movement date in ISO format (defaults to today)",
    )


# --- Local Sales ---


class CreateSalesItemRequest(BaseModel):
    """A single item in a local sales invoice."""

    material_id: str = Field(..., description="Material catalog ID")
    description: str = Field(..., description="Item description")
    quantity: float = Field(..., gt=0, description="Quantity sold")
    unit_price: float = Field(..., ge=0, description="Selling price per unit")


class CreateSalesInvoiceRequest(BaseModel):
    """Request to create a local sales invoice."""

    invoice_number: str = Field(..., description="Invoice number")
    customer_name: str = Field(..., description="Customer name")
    sale_date: str | None = Field(
        default=None,
        description="Sale date in ISO format (defaults to today)",
    )
    tax_amount: float = Field(default=0.0, ge=0, description="Tax amount")
    notes: str | None = Field(default=None, description="Additional notes")
    items: list[CreateSalesItemRequest] = Field(
        ..., description="Line items to sell"
    )


# --- Amazon Import ---


class AmazonImportRequest(BaseModel):
    """Request to import materials from Amazon search."""

    category: str = Field(
        ...,
        description="Product category (e.g., Electronics, Home & Kitchen)",
        examples=["Electronics", "Home & Kitchen", "Industrial"],
    )
    subcategory: str = Field(
        default="all",
        description="Subcategory within the category",
        examples=["all", "Computers", "Mobile Phones", "Tools"],
    )
    query: str = Field(
        default="",
        description="Optional search query to refine results",
        examples=["cable", "PVC pipe", "safety gloves"],
    )
    limit: int = Field(
        default=20,
        ge=1,
        le=50,
        description="Maximum number of items to import (1-50)",
    )
    unit: str | None = Field(
        default=None,
        description="Unit of measure to assign to imported materials",
        examples=["PCS", "M", "KG", "L"],
    )


# --- PDF Templates ---


class TemplatePositionRequest(BaseModel):
    """Position configuration for a template element."""

    x: float = Field(..., description="X coordinate in mm from left")
    y: float = Field(..., description="Y coordinate in mm from top")
    width: float | None = Field(default=None, description="Width in mm")
    height: float | None = Field(default=None, description="Height in mm")
    font_size: int | None = Field(default=None, description="Font size for text")
    alignment: str = Field(default="left", description="Text alignment: left, center, right")


class TemplatePositionsRequest(BaseModel):
    """Positions for all dynamic elements in the template."""

    company_name: TemplatePositionRequest | None = None
    company_address: TemplatePositionRequest | None = None
    logo: TemplatePositionRequest | None = None
    document_title: TemplatePositionRequest | None = None
    document_number: TemplatePositionRequest | None = None
    document_date: TemplatePositionRequest | None = None
    seller_info: TemplatePositionRequest | None = None
    buyer_info: TemplatePositionRequest | None = None
    bank_details: TemplatePositionRequest | None = None
    items_table: TemplatePositionRequest | None = None
    totals: TemplatePositionRequest | None = None
    signature: TemplatePositionRequest | None = None
    stamp: TemplatePositionRequest | None = None
    footer: TemplatePositionRequest | None = None


class CreateTemplateRequest(BaseModel):
    """Request to create a PDF template."""

    name: str = Field(..., description="Template name")
    description: str = Field(default="", description="Template description")
    template_type: str = Field(
        default="proforma",
        description="Template type: proforma, sales, quote, receipt",
    )
    positions: TemplatePositionsRequest | None = Field(
        default=None, description="Element positions"
    )
    page_size: str = Field(default="A4", description="Page size: A4, Letter")
    orientation: str = Field(default="portrait", description="portrait or landscape")
    margin_top: float = Field(default=10.0, description="Top margin in mm")
    margin_bottom: float = Field(default=10.0, description="Bottom margin in mm")
    margin_left: float = Field(default=10.0, description="Left margin in mm")
    margin_right: float = Field(default=10.0, description="Right margin in mm")
    primary_color: str = Field(default="#000000", description="Primary color hex")
    secondary_color: str = Field(default="#666666", description="Secondary color hex")
    is_default: bool = Field(default=False, description="Set as default template")


class UpdateTemplateRequest(BaseModel):
    """Request to update a PDF template."""

    name: str | None = None
    description: str | None = None
    positions: TemplatePositionsRequest | None = None
    page_size: str | None = None
    orientation: str | None = None
    margin_top: float | None = None
    margin_bottom: float | None = None
    margin_left: float | None = None
    margin_right: float | None = None
    primary_color: str | None = None
    secondary_color: str | None = None
    is_default: bool | None = None
    is_active: bool | None = None


# --- PDF Creators ---


class BankDetailsRequest(BaseModel):
    """Bank details for document generation."""

    bank_name: str = Field(..., description="Bank name")
    account_name: str = Field(default="", description="Account holder name")
    account_number: str = Field(default="", description="Account number")
    iban: str = Field(default="", description="IBAN")
    swift_code: str = Field(default="", description="SWIFT/BIC code")
    branch: str = Field(default="", description="Branch name")


class PartyInfoRequest(BaseModel):
    """Party (seller/buyer) information."""

    name: str = Field(..., description="Company/person name")
    address: str = Field(default="", description="Full address")
    phone: str = Field(default="", description="Phone number")
    email: str = Field(default="", description="Email address")
    tax_id: str = Field(default="", description="Tax ID / VAT number")


class CreatorItemRequest(BaseModel):
    """Single line item for document creation."""

    description: str = Field(..., description="Item description")
    quantity: float = Field(..., gt=0, description="Quantity")
    unit: str = Field(default="PCS", description="Unit of measure")
    unit_price: float = Field(..., ge=0, description="Price per unit")
    hs_code: str | None = Field(default=None, description="HS code")


class CreateProformaRequest(BaseModel):
    """Request to create a proforma invoice from scratch."""

    # Template
    template_id: int | None = Field(default=None, description="Template ID to use")

    # Document info
    document_number: str = Field(..., description="Proforma number")
    document_date: str = Field(..., description="Date in YYYY-MM-DD format")
    valid_until: str | None = Field(default=None, description="Validity date")

    # Parties
    seller: PartyInfoRequest = Field(..., description="Seller information")
    buyer: PartyInfoRequest = Field(..., description="Buyer information")

    # Bank details
    bank_details: BankDetailsRequest | None = Field(
        default=None, description="Bank details for payment"
    )

    # Items
    items: list[CreatorItemRequest] = Field(..., description="Line items")

    # Financial
    currency: str = Field(default="AED", description="Currency code")
    tax_rate: float = Field(default=0.0, ge=0, le=100, description="Tax rate percentage")
    discount_amount: float = Field(default=0.0, ge=0, description="Discount amount")

    # Notes
    notes: str = Field(default="", description="Additional notes")
    terms: str = Field(default="", description="Terms and conditions")

    # Output options
    save_as_document: bool = Field(
        default=True, description="Save generated PDF to documents"
    )


class CreateSalesDocumentRequest(BaseModel):
    """Request to create a sales invoice document from scratch."""

    # Template
    template_id: int | None = Field(default=None, description="Template ID to use")

    # Document info
    invoice_number: str = Field(..., description="Invoice number")
    invoice_date: str = Field(..., description="Date in YYYY-MM-DD format")

    # Parties
    seller: PartyInfoRequest = Field(..., description="Seller information")
    buyer: PartyInfoRequest = Field(..., description="Buyer/customer information")

    # Bank details
    bank_details: BankDetailsRequest | None = Field(
        default=None, description="Bank details for payment"
    )

    # Items
    items: list[CreatorItemRequest] = Field(..., description="Line items")

    # Financial
    currency: str = Field(default="AED", description="Currency code")
    tax_rate: float = Field(default=0.0, ge=0, le=100, description="Tax rate percentage")
    discount_amount: float = Field(default=0.0, ge=0, description="Discount amount")

    # Notes
    notes: str = Field(default="", description="Additional notes")
    payment_terms: str = Field(default="", description="Payment terms")

    # Output options
    save_as_document: bool = Field(
        default=True, description="Save generated PDF to documents"
    )
