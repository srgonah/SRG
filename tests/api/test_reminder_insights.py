"""API tests for reminder insights endpoint."""

from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_evaluate_insights_use_case
from src.api.main import app
from src.application.use_cases.evaluate_reminder_insights import (
    EvaluateReminderInsightsUseCase,
    InsightEvaluationResult,
)
from src.core.entities.insight import Insight, InsightCategory, InsightSeverity


def _make_result(insights=None) -> InsightEvaluationResult:
    insights = insights or []
    return InsightEvaluationResult(
        insights=insights,
        total_insights=len(insights),
        expiring_documents=sum(
            1 for i in insights if i.category == InsightCategory.EXPIRING_DOCUMENT
        ),
        unmatched_items=sum(
            1 for i in insights if i.category == InsightCategory.UNMATCHED_ITEM
        ),
        price_anomalies=sum(
            1 for i in insights if i.category == InsightCategory.PRICE_ANOMALY
        ),
    )


@pytest.fixture
def mock_insights_use_case():
    """Create a mock use case returning a sample result."""
    uc = AsyncMock(spec=EvaluateReminderInsightsUseCase)
    sample_insight = Insight(
        category=InsightCategory.EXPIRING_DOCUMENT,
        severity=InsightSeverity.WARNING,
        title="Expiring: Trade License",
        message="Expires soon",
    )
    uc.execute.return_value = _make_result([sample_insight])
    return uc


@pytest.fixture
async def insights_client(mock_insights_use_case):
    """Async client with insights use case override."""
    app.dependency_overrides[get_evaluate_insights_use_case] = lambda: mock_insights_use_case
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_evaluate_insights_use_case, None)


class TestReminderInsightsAPI:
    """Tests for GET /api/reminders/insights."""

    async def test_insights_endpoint_exists(self, insights_client: AsyncClient):
        """GET /api/reminders/insights returns 200."""
        response = await insights_client.get("/api/reminders/insights")
        assert response.status_code == 200

    async def test_insights_response_shape(self, insights_client: AsyncClient):
        """Response has total_insights and insights list."""
        response = await insights_client.get("/api/reminders/insights")
        data = response.json()
        assert "total_insights" in data
        assert "insights" in data
        assert isinstance(data["insights"], list)
        assert data["total_insights"] == 1
        assert data["expiring_documents"] == 1

    async def test_insights_auto_create_param(
        self, insights_client: AsyncClient, mock_insights_use_case
    ):
        """?auto_create=true is accepted and forwarded."""
        response = await insights_client.get(
            "/api/reminders/insights?auto_create=true"
        )
        assert response.status_code == 200
        mock_insights_use_case.execute.assert_called_with(
            expiry_days=30, auto_create=True
        )

    async def test_insights_custom_expiry_days(
        self, insights_client: AsyncClient, mock_insights_use_case
    ):
        """?expiry_days=60 is accepted and forwarded."""
        response = await insights_client.get(
            "/api/reminders/insights?expiry_days=60"
        )
        assert response.status_code == 200
        mock_insights_use_case.execute.assert_called_with(
            expiry_days=60, auto_create=False
        )
