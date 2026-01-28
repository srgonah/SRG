"""Unit tests for CheckExpiringDocumentsUseCase."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from src.application.use_cases.check_expiring_documents import (
    CheckExpiringDocumentsUseCase,
    ExpiryCheckResult,
)
from src.core.entities.company_document import CompanyDocument, CompanyDocumentType
from src.core.entities.reminder import Reminder


def _make_doc(
    doc_id: int = 1,
    title: str = "Trade License",
    days_until_expiry: int = 15,
) -> CompanyDocument:
    """Create a sample company document expiring in N days."""
    return CompanyDocument(
        id=doc_id,
        company_key="acme",
        title=title,
        document_type=CompanyDocumentType.LICENSE,
        expiry_date=date.today() + timedelta(days=days_until_expiry),
    )


def _make_reminder(
    reminder_id: int = 100,
    entity_id: int = 1,
    is_done: bool = False,
) -> Reminder:
    """Create a sample reminder linked to a company document."""
    return Reminder(
        id=reminder_id,
        title="Expiring: Trade License",
        due_date=date.today() + timedelta(days=15),
        linked_entity_type="company_document",
        linked_entity_id=entity_id,
        is_done=is_done,
    )


class TestCheckExpiringDocuments:
    """Tests for CheckExpiringDocumentsUseCase."""

    def _make_stores(
        self,
        expiring_docs: list[CompanyDocument] | None = None,
        existing_reminders: list[Reminder] | None = None,
    ):
        """Create mock stores."""
        doc_store = AsyncMock()
        doc_store.list_expiring = AsyncMock(return_value=expiring_docs or [])

        rem_store = AsyncMock()
        rem_store.find_by_linked_entity = AsyncMock(
            return_value=existing_reminders or [],
        )
        # Make create return a reminder with an ID
        async def mock_create(reminder):
            reminder.id = 999
            return reminder

        rem_store.create = AsyncMock(side_effect=mock_create)

        return doc_store, rem_store

    @pytest.mark.asyncio
    async def test_no_expiring_docs(self):
        """Should return empty result when no documents are expiring."""
        doc_store, rem_store = self._make_stores(expiring_docs=[])

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        result = await uc.execute(within_days=30)

        assert isinstance(result, ExpiryCheckResult)
        assert result.total_expiring == 0
        assert result.reminders_created == 0
        assert result.already_reminded == 0
        rem_store.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_reminder_for_expiring_doc(self):
        """Should create a reminder for a document with no existing reminder."""
        doc = _make_doc(doc_id=1, title="Trade License", days_until_expiry=15)
        doc_store, rem_store = self._make_stores(expiring_docs=[doc])

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        result = await uc.execute()

        assert result.total_expiring == 1
        assert result.reminders_created == 1
        assert result.already_reminded == 0
        assert 999 in result.created_reminder_ids
        rem_store.create.assert_awaited_once()
        created_reminder = rem_store.create.call_args[0][0]
        assert "Trade License" in created_reminder.title
        assert created_reminder.linked_entity_type == "company_document"
        assert created_reminder.linked_entity_id == 1
        assert created_reminder.due_date == doc.expiry_date

    @pytest.mark.asyncio
    async def test_skips_already_reminded_doc(self):
        """Should not create duplicate reminder for already reminded document."""
        doc = _make_doc(doc_id=1)
        existing = _make_reminder(entity_id=1, is_done=False)
        doc_store, rem_store = self._make_stores(
            expiring_docs=[doc], existing_reminders=[existing],
        )

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        result = await uc.execute()

        assert result.total_expiring == 1
        assert result.reminders_created == 0
        assert result.already_reminded == 1
        rem_store.create.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_creates_reminder_when_existing_is_done(self):
        """Should create new reminder if existing reminder is marked done."""
        doc = _make_doc(doc_id=1)
        done_reminder = _make_reminder(entity_id=1, is_done=True)
        doc_store, rem_store = self._make_stores(
            expiring_docs=[doc], existing_reminders=[done_reminder],
        )

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        result = await uc.execute()

        assert result.reminders_created == 1
        assert result.already_reminded == 0

    @pytest.mark.asyncio
    async def test_multiple_docs_mixed(self):
        """Should handle mix of reminded and un-reminded documents."""
        doc1 = _make_doc(doc_id=1, title="License A")
        doc2 = _make_doc(doc_id=2, title="License B")
        doc3 = _make_doc(doc_id=3, title="License C")

        async def mock_find(entity_type, entity_id):
            if entity_id == 2:
                return [_make_reminder(entity_id=2, is_done=False)]
            return []

        doc_store = AsyncMock()
        doc_store.list_expiring = AsyncMock(return_value=[doc1, doc2, doc3])

        rem_store = AsyncMock()
        rem_store.find_by_linked_entity = AsyncMock(side_effect=mock_find)

        create_counter = 0

        async def mock_create(reminder):
            nonlocal create_counter
            create_counter += 1
            reminder.id = 900 + create_counter
            return reminder

        rem_store.create = AsyncMock(side_effect=mock_create)

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        result = await uc.execute()

        assert result.total_expiring == 3
        assert result.reminders_created == 2
        assert result.already_reminded == 1
        assert len(result.created_reminder_ids) == 2

    @pytest.mark.asyncio
    async def test_skips_doc_without_id(self):
        """Should skip documents with no ID."""
        doc = CompanyDocument(
            id=None,
            company_key="acme",
            title="No ID Doc",
            expiry_date=date.today() + timedelta(days=10),
        )
        doc_store, rem_store = self._make_stores(expiring_docs=[doc])

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        result = await uc.execute()

        assert result.total_expiring == 1
        assert result.reminders_created == 0
        rem_store.find_by_linked_entity.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_custom_within_days(self):
        """Should pass within_days parameter to store."""
        doc_store, rem_store = self._make_stores(expiring_docs=[])

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        await uc.execute(within_days=60)

        doc_store.list_expiring.assert_awaited_once_with(
            within_days=60, limit=500,
        )

    @pytest.mark.asyncio
    async def test_reminder_message_contains_doc_info(self):
        """Created reminder should have meaningful title and message."""
        doc = _make_doc(doc_id=5, title="Insurance Policy", days_until_expiry=20)
        doc.document_type = CompanyDocumentType.INSURANCE
        doc_store, rem_store = self._make_stores(expiring_docs=[doc])

        uc = CheckExpiringDocumentsUseCase(
            company_doc_store=doc_store, reminder_store=rem_store,
        )
        await uc.execute()

        created_reminder = rem_store.create.call_args[0][0]
        assert "Insurance Policy" in created_reminder.title
        assert "insurance" in created_reminder.message
        assert str(doc.expiry_date) in created_reminder.message
