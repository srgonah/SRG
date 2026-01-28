"""Tests for the Insight entity."""

from datetime import date

from src.core.entities.insight import Insight, InsightCategory, InsightSeverity


class TestInsightEntity:
    """Tests for Insight model."""

    def test_insight_construction_all_fields(self):
        """Test Insight with all fields populated."""
        insight = Insight(
            category=InsightCategory.EXPIRING_DOCUMENT,
            severity=InsightSeverity.CRITICAL,
            title="Expiring: Trade License",
            message="Trade License expires on 2026-02-15",
            suggested_due_date=date(2026, 2, 15),
            linked_entity_type="company_document",
            linked_entity_id=42,
            details={"days_left": 18, "document_type": "license"},
        )
        assert insight.category == InsightCategory.EXPIRING_DOCUMENT
        assert insight.severity == InsightSeverity.CRITICAL
        assert insight.title == "Expiring: Trade License"
        assert insight.message == "Trade License expires on 2026-02-15"
        assert insight.suggested_due_date == date(2026, 2, 15)
        assert insight.linked_entity_type == "company_document"
        assert insight.linked_entity_id == 42
        assert insight.details["days_left"] == 18

    def test_insight_default_values(self):
        """Test Insight defaults: severity=WARNING, details={}."""
        insight = Insight(
            category=InsightCategory.UNMATCHED_ITEM,
            title="Unmatched item: Widget",
        )
        assert insight.severity == InsightSeverity.WARNING
        assert insight.message == ""
        assert insight.suggested_due_date is None
        assert insight.linked_entity_type is None
        assert insight.linked_entity_id is None
        assert insight.details == {}

    def test_insight_enum_values(self):
        """Test enum string values for InsightCategory and InsightSeverity."""
        assert InsightCategory.EXPIRING_DOCUMENT.value == "expiring_document"
        assert InsightCategory.UNMATCHED_ITEM.value == "unmatched_item"
        assert InsightCategory.PRICE_ANOMALY.value == "price_anomaly"

        assert InsightSeverity.INFO.value == "info"
        assert InsightSeverity.WARNING.value == "warning"
        assert InsightSeverity.CRITICAL.value == "critical"
