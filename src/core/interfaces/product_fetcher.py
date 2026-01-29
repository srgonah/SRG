"""
Abstract interface for fetching product data from external URLs.

Used by the material ingestion service to extract product information
from e-commerce pages (Amazon, etc.).
"""

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from src.core.entities.material import OriginConfidence


class ProductPageData(BaseModel):
    """Extracted product data from an external product page."""

    title: str = Field(..., description="Product title")
    brand: str | None = Field(default=None, description="Brand name")
    description: str | None = Field(default=None, description="Product description")
    origin_country: str | None = Field(default=None, description="Country of origin")
    origin_confidence: OriginConfidence = Field(
        default=OriginConfidence.UNKNOWN,
        description="Confidence in origin determination",
    )
    evidence_text: str | None = Field(
        default=None,
        description="Raw text evidence used for origin inference",
    )
    source_url: str = Field(..., description="URL the data was fetched from")
    category: str | None = Field(default=None, description="Product category")
    suggested_synonyms: list[str] = Field(
        default_factory=list,
        description="Suggested alternative names or synonyms",
    )
    raw_attributes: dict[str, str] = Field(
        default_factory=dict,
        description="Additional key-value attributes extracted from the page",
    )
    # Extended product fields
    asin: str | None = Field(default=None, description="Amazon Standard Identification Number")
    weight: str | None = Field(default=None, description="Product weight from detail table")
    dimensions: str | None = Field(
        default=None, description="Product dimensions from detail table"
    )
    price: str | None = Field(default=None, description="Product price as displayed")
    rating: float | None = Field(default=None, description="Average customer rating (0-5)")
    num_ratings: int | None = Field(
        default=None, description="Number of customer ratings/reviews"
    )


class IProductPageFetcher(ABC):
    """
    Abstract interface for fetching and parsing product pages.

    Implementations handle specific e-commerce platforms
    (Amazon, AliExpress, etc.).
    """

    @abstractmethod
    async def fetch(self, url: str) -> ProductPageData:
        """
        Fetch and parse a product page URL.

        Args:
            url: Product page URL.

        Returns:
            Extracted product data.

        Raises:
            SRGError: If fetching or parsing fails.
        """

    @abstractmethod
    def supports_url(self, url: str) -> bool:
        """
        Check whether this fetcher can handle the given URL.

        Args:
            url: URL to check.

        Returns:
            True if this fetcher supports the URL.
        """
