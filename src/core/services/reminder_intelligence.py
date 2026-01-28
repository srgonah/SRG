"""
Reminder Intelligence Service.

Evaluates system state on-demand and returns insights that
can optionally become derived reminders. No background scheduler.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from src.config import get_logger
from src.core.entities.insight import Insight, InsightCategory, InsightSeverity
from src.core.interfaces.price_history import IPriceHistoryStore
from src.core.interfaces.storage import ICompanyDocumentStore, IInvoiceStore

logger = get_logger(__name__)


class ReminderIntelligenceService:
    """
    Layer-pure service that evaluates system state and produces insights.

    Depends only on core interfaces. Any None store causes
    the corresponding rule to be skipped gracefully.
    """

    def __init__(
        self,
        company_doc_store: ICompanyDocumentStore | None = None,
        invoice_store: IInvoiceStore | None = None,
        price_store: IPriceHistoryStore | None = None,
    ) -> None:
        self._doc_store = company_doc_store
        self._invoice_store = invoice_store
        self._price_store = price_store

    async def evaluate_all(self, expiry_days: int = 30) -> list[Insight]:
        """
        Run all insight rules and return combined results.

        Args:
            expiry_days: Number of days ahead for expiring document check.

        Returns:
            List of detected insights across all rules.
        """
        insights: list[Insight] = []

        insights.extend(await self._check_expiring_documents(expiry_days))
        insights.extend(await self._check_unmatched_items())
        insights.extend(await self._check_price_anomalies())

        logger.info(
            "insight_evaluation_complete",
            total=len(insights),
        )
        return insights

    async def _check_expiring_documents(self, within_days: int) -> list[Insight]:
        """Check for documents nearing expiry."""
        if self._doc_store is None:
            return []

        try:
            expiring = await self._doc_store.list_expiring(
                within_days=within_days, limit=500
            )
        except Exception:
            logger.warning("insight_expiring_docs_error", exc_info=True)
            return []

        insights: list[Insight] = []
        today = date.today()

        for doc in expiring:
            if doc.expiry_date is None or doc.id is None:
                continue

            days_left = (doc.expiry_date - today).days
            severity = (
                InsightSeverity.CRITICAL
                if days_left <= 7
                else InsightSeverity.WARNING
            )

            insights.append(
                Insight(
                    category=InsightCategory.EXPIRING_DOCUMENT,
                    severity=severity,
                    title=f"Expiring: {doc.title}",
                    message=(
                        f"{doc.title} expires on {doc.expiry_date} "
                        f"({days_left} days remaining)"
                    ),
                    suggested_due_date=doc.expiry_date,
                    linked_entity_type="company_document",
                    linked_entity_id=doc.id,
                    details={"days_left": days_left, "document_type": doc.document_type.value},
                )
            )

        return insights

    async def _check_unmatched_items(self) -> list[Insight]:
        """Check for invoice line items with no matched material."""
        if self._invoice_store is None:
            return []

        try:
            items = await self._invoice_store.list_unmatched_items(limit=500)
        except Exception:
            logger.warning("insight_unmatched_items_error", exc_info=True)
            return []

        # Deduplicate by normalized item name
        seen_names: set[str] = set()
        insights: list[Insight] = []

        for item in items:
            name = (item.get("item_name") or "").strip()
            if not name:
                continue

            normalized = name.lower()
            if normalized in seen_names:
                continue
            seen_names.add(normalized)

            insights.append(
                Insight(
                    category=InsightCategory.UNMATCHED_ITEM,
                    severity=InsightSeverity.INFO,
                    title=f"Unmatched item: {name}",
                    message=f"Item '{name}' has no matched material in the catalog",
                    linked_entity_type="invoice_item",
                    linked_entity_id=item.get("id"),
                    details={
                        "item_name": name,
                        "hs_code": item.get("hs_code"),
                        "unit": item.get("unit"),
                    },
                )
            )

        return insights

    async def _check_price_anomalies(self) -> list[Insight]:
        """Check for items with price deviating >20% from historical average."""
        if self._invoice_store is None or self._price_store is None:
            return []

        try:
            items = await self._invoice_store.get_items_for_indexing(
                last_item_id=0, limit=1000
            )
        except Exception:
            logger.warning("insight_price_anomaly_items_error", exc_info=True)
            return []

        # Group by unique item name to avoid redundant stats queries
        items_by_name: dict[str, list[dict[str, Any]]] = {}
        for item in items:
            name = (item.get("item_name") or "").strip()
            if not name:
                continue
            normalized = name.lower()
            if normalized not in items_by_name:
                items_by_name[normalized] = []
            items_by_name[normalized].append(item)

        insights: list[Insight] = []

        for normalized_name, group in items_by_name.items():
            try:
                stats_list = await self._price_store.get_price_stats(
                    item_name=group[0]["item_name"]
                )
            except Exception:
                logger.warning(
                    "insight_price_stats_error",
                    item=normalized_name,
                    exc_info=True,
                )
                continue

            if not stats_list:
                continue

            stats = stats_list[0]
            occurrence_count = stats.get("occurrence_count", 0)
            avg_price = stats.get("avg_price", 0.0)

            if occurrence_count < 2 or avg_price <= 0:
                continue

            # Check each item in the group
            for item in group:
                unit_price = item.get("unit_price", 0.0)
                if unit_price <= 0:
                    continue

                deviation = abs(unit_price - avg_price) / avg_price
                if deviation > 0.20:
                    pct = round(deviation * 100, 1)
                    name = item.get("item_name", normalized_name)
                    insights.append(
                        Insight(
                            category=InsightCategory.PRICE_ANOMALY,
                            severity=InsightSeverity.WARNING,
                            title=f"Price anomaly: {name}",
                            message=(
                                f"'{name}' priced at {unit_price} deviates "
                                f"{pct}% from average {avg_price}"
                            ),
                            linked_entity_type="invoice_item",
                            linked_entity_id=item.get("id"),
                            details={
                                "item_name": name,
                                "unit_price": unit_price,
                                "avg_price": avg_price,
                                "deviation_pct": pct,
                                "occurrence_count": occurrence_count,
                            },
                        )
                    )

        return insights
