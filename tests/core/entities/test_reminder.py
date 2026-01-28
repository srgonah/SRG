"""Tests for Reminder entity."""

from datetime import date, datetime, timedelta

from src.core.entities.reminder import Reminder


class TestReminder:
    """Tests for Reminder entity."""

    def test_create_minimal(self):
        """Test creating a reminder with minimal fields."""
        reminder = Reminder(
            title="Follow up",
            due_date=date(2026, 3, 1),
        )
        assert reminder.title == "Follow up"
        assert reminder.due_date == date(2026, 3, 1)
        assert reminder.message == ""
        assert reminder.is_done is False
        assert reminder.id is None
        assert reminder.linked_entity_type is None
        assert reminder.linked_entity_id is None

    def test_create_full(self):
        """Test creating a reminder with all fields."""
        reminder = Reminder(
            id=1,
            title="Renew license",
            message="Company trade license expires soon",
            due_date=date(2026, 6, 15),
            is_done=False,
            linked_entity_type="company_document",
            linked_entity_id=42,
        )
        assert reminder.id == 1
        assert reminder.title == "Renew license"
        assert reminder.linked_entity_type == "company_document"
        assert reminder.linked_entity_id == 42

    def test_is_overdue_future(self):
        """Test is_overdue returns False for future due date."""
        reminder = Reminder(
            title="Future",
            due_date=date.today() + timedelta(days=7),
        )
        assert reminder.is_overdue is False

    def test_is_overdue_past(self):
        """Test is_overdue returns True for past due date."""
        reminder = Reminder(
            title="Past",
            due_date=date.today() - timedelta(days=1),
        )
        assert reminder.is_overdue is True

    def test_is_overdue_today(self):
        """Test is_overdue returns False for today's due date."""
        reminder = Reminder(
            title="Today",
            due_date=date.today(),
        )
        assert reminder.is_overdue is False

    def test_is_overdue_done(self):
        """Test is_overdue returns False when done, even if past due."""
        reminder = Reminder(
            title="Done",
            due_date=date.today() - timedelta(days=10),
            is_done=True,
        )
        assert reminder.is_overdue is False

    def test_default_timestamps(self):
        """Test that created_at and updated_at are set by default."""
        reminder = Reminder(title="Test", due_date=date.today())
        assert isinstance(reminder.created_at, datetime)
        assert isinstance(reminder.updated_at, datetime)
