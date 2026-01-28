"""
SQLite implementation of reminder storage.

Handles CRUD and upcoming/overdue queries for reminders.
"""

from datetime import datetime

import aiosqlite

from src.config import get_logger
from src.core.entities.reminder import Reminder
from src.core.interfaces.storage import IReminderStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteReminderStore(IReminderStore):
    """SQLite implementation of reminder storage."""

    async def create(self, reminder: Reminder) -> Reminder:
        """Create a new reminder."""
        reminder.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO reminders (
                    title, message, due_date, is_done,
                    linked_entity_type, linked_entity_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reminder.title,
                    reminder.message,
                    reminder.due_date.isoformat(),
                    1 if reminder.is_done else 0,
                    reminder.linked_entity_type,
                    reminder.linked_entity_id,
                    reminder.created_at.isoformat(),
                    reminder.updated_at.isoformat(),
                ),
            )
            reminder.id = cursor.lastrowid
            logger.info("reminder_created", reminder_id=reminder.id, title=reminder.title)
            return reminder

    async def get(self, reminder_id: int) -> Reminder | None:
        """Get reminder by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (reminder_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    async def update(self, reminder: Reminder) -> Reminder:
        """Update an existing reminder."""
        reminder.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE reminders SET
                    title = ?, message = ?, due_date = ?,
                    is_done = ?, linked_entity_type = ?,
                    linked_entity_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    reminder.title,
                    reminder.message,
                    reminder.due_date.isoformat(),
                    1 if reminder.is_done else 0,
                    reminder.linked_entity_type,
                    reminder.linked_entity_id,
                    reminder.updated_at.isoformat(),
                    reminder.id,
                ),
            )
            logger.info("reminder_updated", reminder_id=reminder.id)
            return reminder

    async def delete(self, reminder_id: int) -> bool:
        """Delete a reminder by ID."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM reminders WHERE id = ?", (reminder_id,)
            )
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("reminder_deleted", reminder_id=reminder_id)
            return deleted

    async def list_reminders(
        self, include_done: bool = False, limit: int = 100, offset: int = 0
    ) -> list[Reminder]:
        """List reminders with optional done filter."""
        async with get_connection() as conn:
            if include_done:
                cursor = await conn.execute(
                    """
                    SELECT * FROM reminders
                    ORDER BY due_date ASC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM reminders
                    WHERE is_done = 0
                    ORDER BY due_date ASC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )
            rows = await cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]

    async def list_upcoming(
        self, within_days: int = 7, limit: int = 100
    ) -> list[Reminder]:
        """List upcoming reminders within the given number of days."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM reminders
                WHERE is_done = 0
                  AND due_date <= date('now', ? || ' days')
                ORDER BY due_date ASC
                LIMIT ?
                """,
                (str(within_days), limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]

    async def find_by_linked_entity(
        self, entity_type: str, entity_id: int
    ) -> list[Reminder]:
        """Find reminders linked to a specific entity."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM reminders
                WHERE linked_entity_type = ? AND linked_entity_id = ?
                ORDER BY due_date ASC
                """,
                (entity_type, entity_id),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]

    @staticmethod
    def _row_to_entity(row: aiosqlite.Row) -> Reminder:
        """Convert a database row to a Reminder entity."""
        from datetime import date as date_type

        due_date = date_type.today()
        if row["due_date"]:
            try:
                due_date = date_type.fromisoformat(row["due_date"])
            except (ValueError, TypeError):
                pass

        created_at = datetime.utcnow()
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        updated_at = datetime.utcnow()
        if row["updated_at"]:
            try:
                updated_at = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                pass

        return Reminder(
            id=row["id"],
            title=row["title"],
            message=row["message"] or "",
            due_date=due_date,
            is_done=bool(row["is_done"]),
            linked_entity_type=row["linked_entity_type"],
            linked_entity_id=row["linked_entity_id"],
            created_at=created_at,
            updated_at=updated_at,
        )
