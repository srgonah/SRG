"""Tests for EvaluateReminderInsightsUseCase."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.evaluate_reminder_insights import (
    EvaluateReminderInsightsUseCase,
    InsightEvaluationResult,
)
from src.core.entities.company_document import CompanyDocument, CompanyDocumentType
from src.core.entities.reminder import Reminder


def _make_doc(doc_id: int, title: str, expiry: date) -> CompanyDocument:
    return CompanyDocument(
        id=doc_id,
        company_key="acme",
        title=title,
        document_type=CompanyDocumentType.LICENSE,
        expiry_date=expiry,
    )


def _setup_stores(
    expiring_docs=None,
    unmatched_items=None,
    indexing_items=None,
    price_stats=None,
):
    """Create mock stores with configured return values."""
    doc_store = AsyncMock()
    doc_store.list_expiring.return_value = expiring_docs or []

    inv_store = AsyncMock()
    inv_store.list_unmatched_items.return_value = unmatched_items or []
    inv_store.get_items_for_indexing.return_value = indexing_items or []

    price_store = AsyncMock()
    price_store.get_price_stats.return_value = price_stats or []

    rem_store = AsyncMock()
    rem_store.find_by_linked_entity.return_value = []
    rem_store.create.side_effect = lambda r: _assign_id(r)

    return doc_store, inv_store, price_store, rem_store


def _assign_id(reminder: Reminder) -> Reminder:
    """Simulate DB creating an ID."""
    reminder.id = 100
    return reminder


class TestEvaluateReminderInsightsUseCase:
    """Tests for the evaluate insights use case."""

    @pytest.mark.asyncio
    async def test_execute_returns_result(self):
        """Verify InsightEvaluationResult fields are populated."""
        doc_store, inv_store, price_store, rem_store = _setup_stores(
            expiring_docs=[_make_doc(1, "License", date.today() + timedelta(days=5))],
        )

        uc = EvaluateReminderInsightsUseCase(
            company_doc_store=doc_store,
            invoice_store=inv_store,
            price_store=price_store,
            reminder_store=rem_store,
        )
        result = await uc.execute()

        assert isinstance(result, InsightEvaluationResult)
        assert result.total_insights == 1
        assert len(result.insights) == 1
        assert result.reminders_created == 0  # auto_create=False by default

    @pytest.mark.asyncio
    async def test_auto_create_false_no_reminders(self):
        """auto_create=False → store.create never called."""
        doc_store, inv_store, price_store, rem_store = _setup_stores(
            expiring_docs=[_make_doc(1, "License", date.today() + timedelta(days=5))],
        )

        uc = EvaluateReminderInsightsUseCase(
            company_doc_store=doc_store,
            invoice_store=inv_store,
            price_store=price_store,
            reminder_store=rem_store,
        )
        await uc.execute(auto_create=False)
        rem_store.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_auto_create_creates_reminders(self):
        """auto_create=True → reminders created with insight: prefix."""
        doc_store, inv_store, price_store, rem_store = _setup_stores(
            expiring_docs=[_make_doc(1, "License", date.today() + timedelta(days=5))],
        )

        uc = EvaluateReminderInsightsUseCase(
            company_doc_store=doc_store,
            invoice_store=inv_store,
            price_store=price_store,
            reminder_store=rem_store,
        )
        result = await uc.execute(auto_create=True)

        assert result.reminders_created == 1
        assert len(result.created_reminder_ids) == 1

        # Verify the reminder was created with insight: prefix
        call_args = rem_store.create.call_args[0][0]
        assert call_args.linked_entity_type == "insight:expiring_doc"

    @pytest.mark.asyncio
    async def test_auto_create_skips_duplicates(self):
        """Existing active reminder → no duplicate created."""
        doc_store, inv_store, price_store, rem_store = _setup_stores(
            expiring_docs=[_make_doc(1, "License", date.today() + timedelta(days=5))],
        )
        # Simulate existing active reminder
        rem_store.find_by_linked_entity.return_value = [
            Reminder(
                id=50,
                title="Existing",
                due_date=date.today(),
                is_done=False,
                linked_entity_type="insight:expiring_doc",
                linked_entity_id=1,
            )
        ]

        uc = EvaluateReminderInsightsUseCase(
            company_doc_store=doc_store,
            invoice_store=inv_store,
            price_store=price_store,
            reminder_store=rem_store,
        )
        result = await uc.execute(auto_create=True)

        assert result.reminders_created == 0
        rem_store.create.assert_not_called()

    @pytest.mark.asyncio
    async def test_per_category_counts(self):
        """Verify expiring_documents, unmatched_items, price_anomalies counts."""
        doc_store, inv_store, price_store, rem_store = _setup_stores(
            expiring_docs=[
                _make_doc(1, "License A", date.today() + timedelta(days=5)),
                _make_doc(2, "License B", date.today() + timedelta(days=10)),
            ],
            unmatched_items=[
                {"id": 10, "item_name": "Widget", "hs_code": None, "unit": None, "unit_price": 0},
            ],
            indexing_items=[
                {"id": 20, "item_name": "Steel", "hs_code": "7214", "unit": "kg",
                 "brand": None, "model": None, "quantity": 10, "unit_price": 150.0},
            ],
            price_stats=[
                {"item_name": "Steel", "occurrence_count": 5, "avg_price": 100.0},
            ],
        )

        uc = EvaluateReminderInsightsUseCase(
            company_doc_store=doc_store,
            invoice_store=inv_store,
            price_store=price_store,
            reminder_store=rem_store,
        )
        result = await uc.execute()

        assert result.expiring_documents == 2
        assert result.unmatched_items == 1
        assert result.price_anomalies == 1
        assert result.total_insights == 4
