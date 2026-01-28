"""
Evaluate Reminder Insights Use Case.

Runs insight rules on-demand and optionally creates derived reminders.
"""

from dataclasses import dataclass, field

from src.config import get_logger
from src.core.entities.insight import Insight, InsightCategory
from src.core.entities.reminder import Reminder
from src.core.interfaces.price_history import IPriceHistoryStore
from src.core.interfaces.storage import (
    ICompanyDocumentStore,
    IInvoiceStore,
    IReminderStore,
)
from src.core.services.reminder_intelligence import ReminderIntelligenceService

logger = get_logger(__name__)

# Map insight categories to linked_entity_type prefixes for derived reminders
_INSIGHT_ENTITY_TYPE_MAP: dict[InsightCategory, str] = {
    InsightCategory.EXPIRING_DOCUMENT: "insight:expiring_doc",
    InsightCategory.UNMATCHED_ITEM: "insight:unmatched_item",
    InsightCategory.PRICE_ANOMALY: "insight:price_anomaly",
}


@dataclass
class InsightEvaluationResult:
    """Result of insight evaluation."""

    insights: list[Insight] = field(default_factory=list)
    total_insights: int = 0
    reminders_created: int = 0
    created_reminder_ids: list[int] = field(default_factory=list)
    expiring_documents: int = 0
    unmatched_items: int = 0
    price_anomalies: int = 0


class EvaluateReminderInsightsUseCase:
    """
    Use case that evaluates system state for insights and optionally
    creates derived reminders.
    """

    def __init__(
        self,
        company_doc_store: ICompanyDocumentStore | None = None,
        invoice_store: IInvoiceStore | None = None,
        price_store: IPriceHistoryStore | None = None,
        reminder_store: IReminderStore | None = None,
    ) -> None:
        self._doc_store = company_doc_store
        self._invoice_store = invoice_store
        self._price_store = price_store
        self._rem_store = reminder_store

    async def _get_doc_store(self) -> ICompanyDocumentStore | None:
        if self._doc_store is None:
            try:
                from src.infrastructure.storage.sqlite import get_company_document_store
                self._doc_store = await get_company_document_store()
            except Exception:
                return None
        return self._doc_store

    async def _get_invoice_store(self) -> IInvoiceStore | None:
        if self._invoice_store is None:
            try:
                from src.infrastructure.storage.sqlite import get_invoice_store
                self._invoice_store = await get_invoice_store()
            except Exception:
                return None
        return self._invoice_store

    async def _get_price_store(self) -> IPriceHistoryStore | None:
        if self._price_store is None:
            try:
                from src.infrastructure.storage.sqlite import get_price_history_store
                self._price_store = await get_price_history_store()
            except Exception:
                return None
        return self._price_store

    async def _get_rem_store(self) -> IReminderStore:
        if self._rem_store is None:
            from src.infrastructure.storage.sqlite import get_reminder_store
            self._rem_store = await get_reminder_store()
        return self._rem_store

    async def execute(
        self,
        expiry_days: int = 30,
        auto_create: bool = False,
    ) -> InsightEvaluationResult:
        """
        Evaluate all insight rules.

        Args:
            expiry_days: Days ahead to check for expiring documents.
            auto_create: If True, create derived reminders for each insight.

        Returns:
            InsightEvaluationResult with insights and optional reminder info.
        """
        doc_store = await self._get_doc_store()
        invoice_store = await self._get_invoice_store()
        price_store = await self._get_price_store()

        service = ReminderIntelligenceService(
            company_doc_store=doc_store,
            invoice_store=invoice_store,
            price_store=price_store,
        )

        insights = await service.evaluate_all(expiry_days=expiry_days)

        result = InsightEvaluationResult(
            insights=insights,
            total_insights=len(insights),
        )

        # Count per category
        for insight in insights:
            if insight.category == InsightCategory.EXPIRING_DOCUMENT:
                result.expiring_documents += 1
            elif insight.category == InsightCategory.UNMATCHED_ITEM:
                result.unmatched_items += 1
            elif insight.category == InsightCategory.PRICE_ANOMALY:
                result.price_anomalies += 1

        # Optionally create derived reminders
        if auto_create and insights:
            rem_store = await self._get_rem_store()
            for insight in insights:
                entity_type = _INSIGHT_ENTITY_TYPE_MAP.get(
                    insight.category, f"insight:{insight.category.value}"
                )
                entity_id = insight.linked_entity_id or 0

                # Check for existing active reminder
                existing = await rem_store.find_by_linked_entity(
                    entity_type=entity_type,
                    entity_id=entity_id,
                )
                active = [r for r in existing if not r.is_done]
                if active:
                    continue

                from datetime import date, timedelta

                due = insight.suggested_due_date or (date.today() + timedelta(days=7))

                reminder = Reminder(
                    title=insight.title,
                    message=insight.message,
                    due_date=due,
                    linked_entity_type=entity_type,
                    linked_entity_id=entity_id,
                )
                created = await rem_store.create(reminder)
                result.reminders_created += 1
                if created.id is not None:
                    result.created_reminder_ids.append(created.id)

        logger.info(
            "insight_evaluation_done",
            total=result.total_insights,
            reminders_created=result.reminders_created,
        )

        return result
