"""Reminder entity for task/deadline tracking."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class Reminder(BaseModel):
    """
    Reminder entity for tracking tasks and deadlines.

    Can be linked to other entities (invoices, company documents, etc.)
    via linked_entity_type and linked_entity_id.
    """

    id: int | None = None
    title: str
    message: str = ""
    due_date: date
    is_done: bool = False
    linked_entity_type: str | None = None
    linked_entity_id: int | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_overdue(self) -> bool:
        """Check if the reminder is past due and not done."""
        if self.is_done:
            return False
        return self.due_date < date.today()
