"""API smoke tests for reminders endpoints."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_rem_store
from src.api.main import app
from src.core.entities.reminder import Reminder


@pytest.fixture
def mock_reminder_store():
    """Create mock reminder store."""
    store = AsyncMock()
    sample = Reminder(
        id=1,
        title="Test Reminder",
        message="Test message",
        due_date=date.today() + timedelta(days=3),
    )
    store.create.return_value = sample
    store.get.return_value = sample
    store.update.return_value = sample
    store.delete.return_value = True
    store.list_reminders.return_value = [sample]
    store.list_upcoming.return_value = [sample]
    return store


@pytest.fixture
async def rem_client(mock_reminder_store):
    """Async client with reminder store override."""
    app.dependency_overrides[get_rem_store] = lambda: mock_reminder_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_rem_store, None)


class TestRemindersAPI:
    """Smoke tests for reminders API."""

    async def test_create_endpoint_exists(self, rem_client: AsyncClient):
        """Test that POST /api/reminders endpoint exists."""
        response = await rem_client.post(
            "/api/reminders",
            json={
                "title": "Test",
                "due_date": date.today().isoformat(),
            },
        )
        assert response.status_code != 404

    async def test_list_endpoint_exists(self, rem_client: AsyncClient):
        """Test that GET /api/reminders endpoint exists."""
        response = await rem_client.get("/api/reminders")
        assert response.status_code != 404

    async def test_upcoming_endpoint_exists(self, rem_client: AsyncClient):
        """Test that GET /api/reminders/upcoming endpoint exists."""
        response = await rem_client.get("/api/reminders/upcoming")
        assert response.status_code != 404

    async def test_get_by_id_endpoint_exists(self, rem_client: AsyncClient):
        """Test that GET /api/reminders/{id} returns 200 with mock store."""
        response = await rem_client.get("/api/reminders/1")
        assert response.status_code == 200

    async def test_delete_endpoint_exists(self, rem_client: AsyncClient):
        """Test that DELETE /api/reminders/{id} returns 204 with mock store."""
        response = await rem_client.delete("/api/reminders/1")
        assert response.status_code == 204
