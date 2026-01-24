"""Request DTOs for API endpoints."""

from pydantic import BaseModel, Field


class UploadInvoiceRequest(BaseModel):
    """Request for invoice upload."""

    # File is handled separately via UploadFile
    vendor_hint: str | None = Field(
        default=None,
        description="Hint for vendor detection",
    )
    template_id: str | None = Field(
        default=None,
        description="Force specific template",
    )
    auto_audit: bool = Field(
        default=True,
        description="Automatically audit after parsing",
    )


class AuditInvoiceRequest(BaseModel):
    """Request for invoice audit."""

    invoice_id: str = Field(
        ...,
        description="Invoice ID to audit",
    )
    use_llm: bool = Field(
        default=True,
        description="Use LLM for semantic analysis",
    )
    rules: list[str] | None = Field(
        default=None,
        description="Specific rules to check",
    )


class SearchRequest(BaseModel):
    """Request for document search."""

    query: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="Search query",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Number of results",
    )
    search_type: str = Field(
        default="hybrid",
        pattern="^(hybrid|semantic|keyword)$",
        description="Search type",
    )
    use_reranker: bool = Field(
        default=True,
        description="Apply reranking",
    )
    filters: dict | None = Field(
        default=None,
        description="Metadata filters",
    )


class ChatRequest(BaseModel):
    """Request for chat message."""

    message: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="User message",
    )
    session_id: str | None = Field(
        default=None,
        description="Session ID (creates new if None)",
    )
    use_rag: bool = Field(
        default=True,
        description="Use RAG for context",
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Context chunks for RAG",
    )
    stream: bool = Field(
        default=False,
        description="Stream response",
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
