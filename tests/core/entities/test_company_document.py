"""Tests for CompanyDocument entity."""

from datetime import date, timedelta

from src.core.entities.company_document import CompanyDocument, CompanyDocumentType


class TestCompanyDocument:
    """Tests for CompanyDocument entity."""

    def test_create_minimal(self):
        """Test creating a company document with minimal fields."""
        doc = CompanyDocument(
            company_key="ACME",
            title="Business License",
        )
        assert doc.company_key == "ACME"
        assert doc.title == "Business License"
        assert doc.document_type == CompanyDocumentType.OTHER
        assert doc.id is None
        assert doc.expiry_date is None

    def test_create_full(self):
        """Test creating a company document with all fields."""
        doc = CompanyDocument(
            id=1,
            company_key="ACME",
            title="Trade License",
            document_type=CompanyDocumentType.LICENSE,
            file_path="/docs/license.pdf",
            doc_id=42,
            expiry_date=date(2026, 12, 31),
            issued_date=date(2025, 1, 1),
            issuer="Ministry of Trade",
            notes="Annual renewal",
            metadata={"ref": "TL-001"},
        )
        assert doc.id == 1
        assert doc.document_type == CompanyDocumentType.LICENSE
        assert doc.expiry_date == date(2026, 12, 31)
        assert doc.issuer == "Ministry of Trade"
        assert doc.metadata == {"ref": "TL-001"}

    def test_document_types(self):
        """Test all document type enum values."""
        assert CompanyDocumentType.LICENSE == "license"
        assert CompanyDocumentType.CERTIFICATE == "certificate"
        assert CompanyDocumentType.PERMIT == "permit"
        assert CompanyDocumentType.INSURANCE == "insurance"
        assert CompanyDocumentType.CONTRACT == "contract"
        assert CompanyDocumentType.OTHER == "other"

    def test_is_expired_no_date(self):
        """Test is_expired returns False when no expiry date."""
        doc = CompanyDocument(company_key="X", title="No expiry")
        assert doc.is_expired is False

    def test_is_expired_future_date(self):
        """Test is_expired returns False for future expiry."""
        doc = CompanyDocument(
            company_key="X",
            title="Future",
            expiry_date=date.today() + timedelta(days=30),
        )
        assert doc.is_expired is False

    def test_is_expired_past_date(self):
        """Test is_expired returns True for past expiry."""
        doc = CompanyDocument(
            company_key="X",
            title="Expired",
            expiry_date=date.today() - timedelta(days=1),
        )
        assert doc.is_expired is True

    def test_days_until_expiry_no_date(self):
        """Test days_until_expiry returns None when no expiry date."""
        doc = CompanyDocument(company_key="X", title="No expiry")
        assert doc.days_until_expiry() is None

    def test_days_until_expiry_future(self):
        """Test days_until_expiry returns positive for future date."""
        doc = CompanyDocument(
            company_key="X",
            title="Future",
            expiry_date=date.today() + timedelta(days=10),
        )
        assert doc.days_until_expiry() == 10

    def test_days_until_expiry_past(self):
        """Test days_until_expiry returns negative for past date."""
        doc = CompanyDocument(
            company_key="X",
            title="Past",
            expiry_date=date.today() - timedelta(days=5),
        )
        assert doc.days_until_expiry() == -5

    def test_days_until_expiry_today(self):
        """Test days_until_expiry returns 0 for today."""
        doc = CompanyDocument(
            company_key="X",
            title="Today",
            expiry_date=date.today(),
        )
        assert doc.days_until_expiry() == 0
