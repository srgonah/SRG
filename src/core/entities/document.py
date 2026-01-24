"""
Document domain entities for the RAG system.

Represents documents, pages, and chunks for indexing and search.
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class PageType(str, Enum):
    """Type of document page."""

    INVOICE = "invoice"
    PACKING_LIST = "packing_list"
    CONTRACT = "contract"
    BANK_FORM = "bank_form"
    CERTIFICATE = "certificate"
    COVER_LETTER = "cover_letter"
    OTHER = "other"


class DocumentStatus(str, Enum):
    """Document processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"


class Document(BaseModel):
    """
    Document entity representing a PDF or image file.

    Supports versioning with is_latest flag.
    """

    id: int | None = None

    # File info
    filename: str
    original_filename: str
    file_path: str
    file_hash: str | None = None
    file_size: int = 0
    mime_type: str = "application/pdf"

    # Processing state
    status: DocumentStatus = DocumentStatus.PENDING
    error_message: str | None = None

    # Versioning
    version: int = 1
    is_latest: bool = True
    previous_version_id: int | None = None

    # Derived data
    page_count: int = 0
    company_key: str | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    indexed_at: datetime | None = None


class Page(BaseModel):
    """
    Single page from a document.

    Contains extracted text and classification.
    """

    id: int | None = None
    doc_id: int
    page_no: int

    # Classification
    page_type: PageType = PageType.OTHER
    type_confidence: float = 0.0

    # Extracted content
    text: str = ""
    text_length: int = 0

    # Image data (for vision processing)
    image_path: str | None = None
    image_hash: str | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Chunk(BaseModel):
    """
    Text chunk for embedding and search.

    Chunks are created from pages with overlap for context.
    """

    id: int | None = None
    doc_id: int
    page_id: int

    # Chunk data
    chunk_index: int = 0
    chunk_text: str = ""
    chunk_size: int = 0

    # Position in page
    start_char: int = 0
    end_char: int = 0

    # Metadata for search context
    metadata: dict[str, Any] = Field(default_factory=dict)

    # FAISS mapping
    faiss_id: int | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def embedding_text(self) -> str:
        """Text used for embedding generation."""
        # Prepend page type for context
        page_type = self.metadata.get("page_type", "")
        if page_type:
            return f"[{page_type}] {self.chunk_text}"
        return self.chunk_text


class IndexingState(BaseModel):
    """
    State tracking for incremental indexing.

    Stores the last processed document/chunk for resumption.
    """

    id: int | None = None
    index_name: str  # "chunks" or "items"

    # Last indexed IDs
    last_doc_id: int = 0
    last_chunk_id: int = 0
    last_item_id: int = 0

    # Counts
    total_indexed: int = 0
    pending_count: int = 0

    # State
    is_building: bool = False
    last_error: str | None = None

    # Timestamps
    last_run_at: datetime | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class SearchResult(BaseModel):
    """
    Search result from vector/hybrid search.

    Combines chunk data with relevance scores.
    """

    # Identifiers
    chunk_id: int | None = None
    item_id: int | None = None
    doc_id: int | None = None

    # Content
    text: str = ""
    item_name: str | None = None

    # Scores
    faiss_score: float = 0.0
    fts_score: float = 0.0
    hybrid_score: float = 0.0
    reranker_score: float | None = None
    final_score: float = 0.0

    # Ranking
    faiss_rank: int = 0
    final_rank: int = 0

    # Context
    page_no: int | None = None
    page_type: str | None = None
    invoice_no: str | None = None
    invoice_date: str | None = None
    seller_name: str | None = None

    # Additional item fields
    hs_code: str | None = None
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None

    # Metadata
    metadata: dict[str, Any] = Field(default_factory=dict)
