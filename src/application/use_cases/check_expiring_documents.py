"""
Check Expiring Documents Use Case.

Scans company documents nearing expiry and auto-creates reminders
for any that don't already have active reminders.
"""

from dataclasses import dataclass, field

from src.config import get_logger
from src.core.entities.reminder import Reminder
from src.core.interfaces.storage import ICompanyDocumentStore, IReminderStore

logger = get_logger(__name__)


@dataclass
class ExpiryCheckResult:
    """Result of expiring document check."""

    total_expiring: int = 0
    reminders_created: int = 0
    already_reminded: int = 0
    created_reminder_ids: list[int] = field(default_factory=list)


class CheckExpiringDocumentsUseCase:
    """
    Use case for checking expiring company documents and creating reminders.

    Scans for documents expiring within a configurable window (default 30 days)
    and creates reminders for documents without existing active reminders.
    """

    def __init__(
        self,
        company_doc_store: ICompanyDocumentStore | None = None,
        reminder_store: IReminderStore | None = None,
    ):
        self._doc_store = company_doc_store
        self._rem_store = reminder_store

    async def _get_doc_store(self) -> ICompanyDocumentStore:
        if self._doc_store is None:
            from src.infrastructure.storage.sqlite import get_company_document_store
            self._doc_store = await get_company_document_store()
        return self._doc_store

    async def _get_rem_store(self) -> IReminderStore:
        if self._rem_store is None:
            from src.infrastructure.storage.sqlite import get_reminder_store
            self._rem_store = await get_reminder_store()
        return self._rem_store

    async def execute(self, within_days: int = 30) -> ExpiryCheckResult:
        """
        Check for expiring documents and create reminders.

        Args:
            within_days: Number of days to look ahead for expiring documents.

        Returns:
            ExpiryCheckResult with counts and created reminder IDs.
        """
        doc_store = await self._get_doc_store()
        rem_store = await self._get_rem_store()

        expiring_docs = await doc_store.list_expiring(
            within_days=within_days, limit=500,
        )

        result = ExpiryCheckResult(total_expiring=len(expiring_docs))

        for doc in expiring_docs:
            if doc.id is None:
                continue

            # Check if an active (not done) reminder already exists
            existing = await rem_store.find_by_linked_entity(
                entity_type="company_document",
                entity_id=doc.id,
            )
            active_reminders = [r for r in existing if not r.is_done]

            if active_reminders:
                result.already_reminded += 1
                continue

            # Create reminder with due_date = expiry_date
            reminder = Reminder(
                title=f"Expiring: {doc.title}",
                message=(
                    f"{doc.title} ({doc.document_type.value}) "
                    f"expires on {doc.expiry_date}"
                ),
                due_date=doc.expiry_date,  # type: ignore[arg-type]
                linked_entity_type="company_document",
                linked_entity_id=doc.id,
            )
            created = await rem_store.create(reminder)
            result.reminders_created += 1
            if created.id is not None:
                result.created_reminder_ids.append(created.id)

        logger.info(
            "expiry_check_complete",
            total_expiring=result.total_expiring,
            reminders_created=result.reminders_created,
            already_reminded=result.already_reminded,
        )

        return result
