"""Company document entity with expiry tracking."""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CompanyDocumentType(str, Enum):
    """Type of company document."""

    LICENSE = "license"
    CERTIFICATE = "certificate"
    PERMIT = "permit"
    INSURANCE = "insurance"
    CONTRACT = "contract"
    OTHER = "other"


class CompanyDocument(BaseModel):
    """
    Company document with expiry date tracking.

    Represents licenses, certificates, permits, insurance policies,
    and other company documents that may expire.
    """

    id: int | None = None
    company_key: str
    title: str
    document_type: CompanyDocumentType = CompanyDocumentType.OTHER
    file_path: str | None = None
    doc_id: int | None = None
    expiry_date: date | None = None
    issued_date: date | None = None
    issuer: str | None = None
    notes: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_expired(self) -> bool:
        """Check if the document has expired."""
        if self.expiry_date is None:
            return False
        return self.expiry_date < date.today()

    def days_until_expiry(self) -> int | None:
        """Return the number of days until expiry, or None if no expiry date."""
        if self.expiry_date is None:
            return None
        delta = self.expiry_date - date.today()
        return delta.days
