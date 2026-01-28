"""Tests for ReminderIntelligenceService."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from src.core.entities.company_document import CompanyDocument, CompanyDocumentType
from src.core.entities.insight import InsightCategory, InsightSeverity
from src.core.services.reminder_intelligence import ReminderIntelligenceService


def _make_doc(doc_id: int, title: str, expiry: date) -> CompanyDocument:
    """Helper to create a CompanyDocument with an expiry date."""
    return CompanyDocument(
        id=doc_id,
        company_key="acme",
        title=title,
        document_type=CompanyDocumentType.LICENSE,
        expiry_date=expiry,
    )


class TestReminderIntelligenceService:
    """Tests for the three insight rules."""

    @pytest.mark.asyncio
    async def test_empty_when_no_data(self):
        """All stores return empty → 0 insights."""
        doc_store = AsyncMock()
        doc_store.list_expiring.return_value = []
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = []
        inv_store.get_items_for_indexing.return_value = []
        price_store = AsyncMock()

        svc = ReminderIntelligenceService(
            company_doc_store=doc_store,
            invoice_store=inv_store,
            price_store=price_store,
        )
        insights = await svc.evaluate_all()
        assert insights == []

    @pytest.mark.asyncio
    async def test_expiring_docs_produces_insights(self):
        """2 expiring docs → 2 insights."""
        doc_store = AsyncMock()
        doc_store.list_expiring.return_value = [
            _make_doc(1, "License A", date.today() + timedelta(days=5)),
            _make_doc(2, "License B", date.today() + timedelta(days=20)),
        ]

        svc = ReminderIntelligenceService(company_doc_store=doc_store)
        insights = await svc.evaluate_all()
        assert len(insights) == 2
        assert all(i.category == InsightCategory.EXPIRING_DOCUMENT for i in insights)

    @pytest.mark.asyncio
    async def test_expiring_doc_critical_under_7_days(self):
        """Doc expiring in 3 days → CRITICAL severity."""
        doc_store = AsyncMock()
        doc_store.list_expiring.return_value = [
            _make_doc(1, "License", date.today() + timedelta(days=3)),
        ]

        svc = ReminderIntelligenceService(company_doc_store=doc_store)
        insights = await svc.evaluate_all()
        assert len(insights) == 1
        assert insights[0].severity == InsightSeverity.CRITICAL

    @pytest.mark.asyncio
    async def test_expiring_doc_warning_over_7_days(self):
        """Doc expiring in 15 days → WARNING severity."""
        doc_store = AsyncMock()
        doc_store.list_expiring.return_value = [
            _make_doc(1, "License", date.today() + timedelta(days=15)),
        ]

        svc = ReminderIntelligenceService(company_doc_store=doc_store)
        insights = await svc.evaluate_all()
        assert len(insights) == 1
        assert insights[0].severity == InsightSeverity.WARNING

    @pytest.mark.asyncio
    async def test_unmatched_items_produces_insights(self):
        """Items without material → insights."""
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = [
            {"id": 1, "item_name": "Widget A", "hs_code": "1234", "unit": "kg", "unit_price": 10.0},
            {"id": 2, "item_name": "Widget B", "hs_code": "5678", "unit": "pcs", "unit_price": 5.0},
        ]
        inv_store.get_items_for_indexing.return_value = []

        svc = ReminderIntelligenceService(invoice_store=inv_store)
        insights = await svc.evaluate_all()
        assert len(insights) == 2
        assert all(i.category == InsightCategory.UNMATCHED_ITEM for i in insights)

    @pytest.mark.asyncio
    async def test_unmatched_items_deduplicates_by_name(self):
        """Same name twice → 1 insight (deduplication by normalized name)."""
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = [
            {"id": 1, "item_name": "Widget A", "hs_code": None, "unit": None, "unit_price": 0},
            {"id": 2, "item_name": "widget a", "hs_code": None, "unit": None, "unit_price": 0},
        ]
        inv_store.get_items_for_indexing.return_value = []

        svc = ReminderIntelligenceService(invoice_store=inv_store)
        insights = await svc.evaluate_all()
        unmatched = [i for i in insights if i.category == InsightCategory.UNMATCHED_ITEM]
        assert len(unmatched) == 1

    @pytest.mark.asyncio
    async def test_unmatched_items_skips_empty_names(self):
        """Blank item_name → skipped."""
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = [
            {"id": 1, "item_name": "", "hs_code": None, "unit": None, "unit_price": 0},
            {"id": 2, "item_name": "  ", "hs_code": None, "unit": None, "unit_price": 0},
        ]
        inv_store.get_items_for_indexing.return_value = []

        svc = ReminderIntelligenceService(invoice_store=inv_store)
        insights = await svc.evaluate_all()
        assert len(insights) == 0

    @pytest.mark.asyncio
    async def test_price_anomaly_above_threshold(self):
        """25% deviation → insight produced."""
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = []
        inv_store.get_items_for_indexing.return_value = [
            {"id": 1, "item_name": "Steel Rod", "hs_code": "7214", "unit": "kg",
             "brand": None, "model": None, "quantity": 10, "unit_price": 125.0},
        ]
        price_store = AsyncMock()
        price_store.get_price_stats.return_value = [
            {"item_name": "Steel Rod", "occurrence_count": 5, "avg_price": 100.0},
        ]

        svc = ReminderIntelligenceService(
            invoice_store=inv_store, price_store=price_store
        )
        insights = await svc.evaluate_all()
        anomalies = [i for i in insights if i.category == InsightCategory.PRICE_ANOMALY]
        assert len(anomalies) == 1
        assert anomalies[0].details["deviation_pct"] == 25.0

    @pytest.mark.asyncio
    async def test_price_anomaly_below_threshold(self):
        """10% deviation → no insight."""
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = []
        inv_store.get_items_for_indexing.return_value = [
            {"id": 1, "item_name": "Steel Rod", "hs_code": "7214", "unit": "kg",
             "brand": None, "model": None, "quantity": 10, "unit_price": 110.0},
        ]
        price_store = AsyncMock()
        price_store.get_price_stats.return_value = [
            {"item_name": "Steel Rod", "occurrence_count": 5, "avg_price": 100.0},
        ]

        svc = ReminderIntelligenceService(
            invoice_store=inv_store, price_store=price_store
        )
        insights = await svc.evaluate_all()
        anomalies = [i for i in insights if i.category == InsightCategory.PRICE_ANOMALY]
        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_price_anomaly_needs_min_occurrences(self):
        """1 occurrence → no insight (needs ≥2)."""
        inv_store = AsyncMock()
        inv_store.list_unmatched_items.return_value = []
        inv_store.get_items_for_indexing.return_value = [
            {"id": 1, "item_name": "Rare Part", "hs_code": None, "unit": None,
             "brand": None, "model": None, "quantity": 1, "unit_price": 500.0},
        ]
        price_store = AsyncMock()
        price_store.get_price_stats.return_value = [
            {"item_name": "Rare Part", "occurrence_count": 1, "avg_price": 200.0},
        ]

        svc = ReminderIntelligenceService(
            invoice_store=inv_store, price_store=price_store
        )
        insights = await svc.evaluate_all()
        anomalies = [i for i in insights if i.category == InsightCategory.PRICE_ANOMALY]
        assert len(anomalies) == 0

    @pytest.mark.asyncio
    async def test_graceful_when_stores_none(self):
        """All stores None → empty list, no error."""
        svc = ReminderIntelligenceService()
        insights = await svc.evaluate_all()
        assert insights == []
