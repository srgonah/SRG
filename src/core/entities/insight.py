"""Insight entity for on-demand reminder intelligence."""

from datetime import date
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class InsightCategory(str, Enum):
    """Category of detected insight."""

    EXPIRING_DOCUMENT = "expiring_document"
    UNMATCHED_ITEM = "unmatched_item"
    PRICE_ANOMALY = "price_anomaly"


class InsightSeverity(str, Enum):
    """Severity level of an insight."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class Insight(BaseModel):
    """
    An insight detected by evaluating system state.

    Pure Pydantic model, not persisted. Generated on-demand
    by rule evaluation in ReminderIntelligenceService.
    """

    category: InsightCategory
    severity: InsightSeverity = InsightSeverity.WARNING
    title: str
    message: str = ""
    suggested_due_date: date | None = None
    linked_entity_type: str | None = None
    linked_entity_id: int | None = None
    details: dict[str, Any] = Field(default_factory=dict)
