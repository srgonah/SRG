"""Unit tests for Material entity ingestion-related fields."""

from src.core.entities.material import Material, OriginConfidence


class TestOriginConfidence:
    """Tests for OriginConfidence enum."""

    def test_enum_values(self):
        """OriginConfidence has three expected values."""
        assert OriginConfidence.CONFIRMED.value == "confirmed"
        assert OriginConfidence.LIKELY.value == "likely"
        assert OriginConfidence.UNKNOWN.value == "unknown"

    def test_enum_from_string(self):
        """OriginConfidence can be created from string value."""
        assert OriginConfidence("confirmed") == OriginConfidence.CONFIRMED
        assert OriginConfidence("likely") == OriginConfidence.LIKELY
        assert OriginConfidence("unknown") == OriginConfidence.UNKNOWN

    def test_is_str_subclass(self):
        """OriginConfidence values are strings."""
        assert isinstance(OriginConfidence.CONFIRMED, str)
        assert OriginConfidence.CONFIRMED == "confirmed"


class TestMaterialIngestionFields:
    """Tests for Material ingestion-related fields."""

    def test_default_ingestion_fields(self):
        """Ingestion fields default to None/UNKNOWN."""
        m = Material(name="Test Product")
        assert m.brand is None
        assert m.source_url is None
        assert m.origin_country is None
        assert m.origin_confidence == OriginConfidence.UNKNOWN
        assert m.evidence_text is None

    def test_set_ingestion_fields(self):
        """Ingestion fields can be set at creation."""
        m = Material(
            name="BOSCH Drill 500W",
            brand="BOSCH",
            source_url="https://amazon.ae/dp/B001",
            origin_country="Germany",
            origin_confidence=OriginConfidence.CONFIRMED,
            evidence_text="Country of Origin: Germany",
        )
        assert m.brand == "BOSCH"
        assert m.source_url == "https://amazon.ae/dp/B001"
        assert m.origin_country == "Germany"
        assert m.origin_confidence == OriginConfidence.CONFIRMED
        assert m.evidence_text == "Country of Origin: Germany"

    def test_ingestion_fields_with_normalized_name(self):
        """Ingestion fields work alongside auto-normalized name."""
        m = Material(
            name="  DeWalt Impact Driver  ",
            brand="DeWalt",
            origin_country="China",
            origin_confidence=OriginConfidence.LIKELY,
        )
        assert m.normalized_name == "dewalt impact driver"
        assert m.brand == "DeWalt"
        assert m.origin_confidence == OriginConfidence.LIKELY

    def test_origin_confidence_serialization(self):
        """OriginConfidence serializes to string value."""
        m = Material(
            name="Test",
            origin_confidence=OriginConfidence.CONFIRMED,
        )
        data = m.model_dump()
        assert data["origin_confidence"] == "confirmed"
