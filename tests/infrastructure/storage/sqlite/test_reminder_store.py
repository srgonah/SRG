"""Tests for SQLiteReminderStore."""

from datetime import date, timedelta
from pathlib import Path

import aiosqlite
import pytest

from src.infrastructure.storage.sqlite.reminder_store import SQLiteReminderStore


@pytest.fixture
async def reminder_db(tmp_path: Path):
    """Create a temporary database with reminders schema."""
    db_path = tmp_path / "test_reminders.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                message TEXT DEFAULT '',
                due_date DATE NOT NULL,
                is_done INTEGER NOT NULL DEFAULT 0,
                linked_entity_type TEXT,
                linked_entity_id INTEGER,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_due_date
            ON reminders(due_date)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_reminders_is_done
            ON reminders(is_done)
        """)
        await conn.commit()

    yield db_path


class TestSQLiteReminderStore:
    """Tests for SQLiteReminderStore."""

    @pytest.fixture(autouse=True)
    def _setup(self, reminder_db: Path):
        """Setup temp database."""
        self.db_path = reminder_db
        self.store = SQLiteReminderStore()

    async def test_create_reminder(self):
        """Test creating a reminder in the database."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                INSERT INTO reminders (
                    title, message, due_date, is_done,
                    linked_entity_type, linked_entity_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Test Reminder", "Test message", date.today().isoformat(), 0, None, None),
            )
            await conn.commit()
            assert cursor.lastrowid is not None
            assert cursor.lastrowid > 0

    async def test_get_reminder(self):
        """Test getting a reminder by ID."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                INSERT INTO reminders (
                    title, message, due_date, is_done,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Get Test", "msg", date.today().isoformat(), 0),
            )
            await conn.commit()
            rid = cursor.lastrowid

            cursor2 = await conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (rid,)
            )
            row = await cursor2.fetchone()
            assert row is not None
            assert row["title"] == "Get Test"
            assert row["is_done"] == 0

    async def test_update_reminder(self):
        """Test updating a reminder."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                INSERT INTO reminders (
                    title, message, due_date, is_done,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Update Test", "", date.today().isoformat(), 0),
            )
            await conn.commit()
            rid = cursor.lastrowid

            # Mark as done
            await conn.execute(
                "UPDATE reminders SET is_done = 1 WHERE id = ?", (rid,)
            )
            await conn.commit()

            cursor2 = await conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (rid,)
            )
            row = await cursor2.fetchone()
            assert row["is_done"] == 1

    async def test_delete_reminder(self):
        """Test deleting a reminder."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    created_at, updated_at
                ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Delete Test", date.today().isoformat(), 0),
            )
            await conn.commit()
            rid = cursor.lastrowid

            await conn.execute("DELETE FROM reminders WHERE id = ?", (rid,))
            await conn.commit()

            cursor2 = await conn.execute(
                "SELECT * FROM reminders WHERE id = ?", (rid,)
            )
            assert await cursor2.fetchone() is None

    async def test_list_upcoming(self):
        """Test listing upcoming reminders."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Due in 3 days
            await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    created_at, updated_at
                ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Soon", (date.today() + timedelta(days=3)).isoformat(), 0),
            )
            # Due in 30 days
            await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    created_at, updated_at
                ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Later", (date.today() + timedelta(days=30)).isoformat(), 0),
            )
            # Already done
            await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    created_at, updated_at
                ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Done", (date.today() + timedelta(days=2)).isoformat(), 1),
            )
            await conn.commit()

            # Within 7 days, not done
            cursor = await conn.execute(
                """
                SELECT * FROM reminders
                WHERE is_done = 0
                  AND due_date <= date('now', '7 days')
                ORDER BY due_date ASC
                """,
            )
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["title"] == "Soon"

    async def test_list_reminders_exclude_done(self):
        """Test listing reminders excluding done ones."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            await conn.execute(
                """
                INSERT INTO reminders (title, due_date, is_done, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Pending", date.today().isoformat(), 0),
            )
            await conn.execute(
                """
                INSERT INTO reminders (title, due_date, is_done, created_at, updated_at)
                VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Completed", date.today().isoformat(), 1),
            )
            await conn.commit()

            # Exclude done
            cursor = await conn.execute(
                "SELECT * FROM reminders WHERE is_done = 0"
            )
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["title"] == "Pending"

            # Include done
            cursor2 = await conn.execute("SELECT * FROM reminders")
            rows2 = await cursor2.fetchall()
            assert len(rows2) == 2

    async def test_find_by_linked_entity(self):
        """Test finding reminders linked to a specific entity."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Reminder linked to company_document 10
            await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    linked_entity_type, linked_entity_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Doc 10 reminder", date.today().isoformat(), 0, "company_document", 10),
            )
            # Reminder linked to company_document 20
            await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    linked_entity_type, linked_entity_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Doc 20 reminder", date.today().isoformat(), 0, "company_document", 20),
            )
            # Reminder linked to invoice 10 (different type)
            await conn.execute(
                """
                INSERT INTO reminders (
                    title, due_date, is_done,
                    linked_entity_type, linked_entity_id,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("Invoice reminder", date.today().isoformat(), 0, "invoice", 10),
            )
            await conn.commit()

            # Query for company_document 10 only
            cursor = await conn.execute(
                """
                SELECT * FROM reminders
                WHERE linked_entity_type = ? AND linked_entity_id = ?
                ORDER BY due_date ASC
                """,
                ("company_document", 10),
            )
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["title"] == "Doc 10 reminder"

            # Query for entity with no reminders
            cursor2 = await conn.execute(
                """
                SELECT * FROM reminders
                WHERE linked_entity_type = ? AND linked_entity_id = ?
                """,
                ("company_document", 999),
            )
            rows2 = await cursor2.fetchall()
            assert len(rows2) == 0
