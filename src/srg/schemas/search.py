"""Search schemas."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Search request schema."""

    query: str = Field(..., min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=50)
    search_type: str = Field(default="hybrid", pattern="^(hybrid|semantic|keyword)$")
    use_reranker: bool = True
    filters: dict | None = None


class SearchResult(BaseModel):
    """Single search result."""

    chunk_id: str
    document_id: str
    content: str
    score: float
    metadata: dict = {}
    page_number: int | None = None
    file_name: str | None = None


class SearchResponse(BaseModel):
    """Search response schema."""

    query: str
    results: list[SearchResult]
    total: int
    search_type: str
    took_ms: float
