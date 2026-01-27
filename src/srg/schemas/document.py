"""Document schemas."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class DocumentResponse(BaseModel):
    """Document response schema."""

    model_config = ConfigDict(from_attributes=True)

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
    """Paginated document list response."""

    documents: list[DocumentResponse]
    total: int
    limit: int
    offset: int


class IndexingStatsResponse(BaseModel):
    """Indexing statistics response."""

    documents: int
    chunks: int
    vectors: int
    index_synced: bool
