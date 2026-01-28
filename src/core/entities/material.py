"""
Material domain entity for the materials catalog.

Represents a material/product tracked across invoices.
"""

from datetime import UTC, datetime
from enum import Enum

from pydantic import BaseModel, Field, model_validator


class OriginConfidence(str, Enum):
    """Confidence level for country-of-origin determination."""

    CONFIRMED = "confirmed"
    LIKELY = "likely"
    UNKNOWN = "unknown"


class MaterialSynonym(BaseModel):
    """A synonym or alternative name for a material."""

    id: str | None = None
    material_id: str | None = None
    synonym: str
    language: str = "en"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class Material(BaseModel):
    """
    A material/product in the catalog.

    Tracks names, synonyms, and links to price history.
    """

    id: str | None = None
    name: str
    normalized_name: str = ""
    hs_code: str | None = None
    category: str | None = None
    unit: str | None = None
    description: str | None = None
    brand: str | None = None
    source_url: str | None = None
    origin_country: str | None = None
    origin_confidence: OriginConfidence = OriginConfidence.UNKNOWN
    evidence_text: str | None = None
    synonyms: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def compute_normalized_name(self) -> "Material":
        """Auto-compute normalized_name from name if not set."""
        if not self.normalized_name:
            self.normalized_name = self.name.strip().lower()
        return self
