"""Request DTOs for API endpoints.

Pydantic v2 models for API request validation.
These are the ONLY contracts between API and use cases.
"""

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
    filters: dict | None = Field(
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
    metadata: dict | None = Field(
        default=None,
        description="Session metadata",
    )


class IndexDocumentRequest(BaseModel):
    """Request to index a document."""

    file_path: str = Field(
        ...,
        description="Path to document file",
    )
    metadata: dict | None = Field(
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
