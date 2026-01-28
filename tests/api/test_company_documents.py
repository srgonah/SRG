"""API smoke tests for company documents endpoints."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import get_check_expiring_documents_use_case, get_company_doc_store
from src.api.main import app
from src.application.use_cases.check_expiring_documents import ExpiryCheckResult
from src.core.entities.company_document import CompanyDocument, CompanyDocumentType


@pytest.fixture
def mock_company_doc_store():
    """Create mock company document store."""
    store = AsyncMock()
    sample = CompanyDocument(
        id=1,
        company_key="ACME",
        title="Trade License",
        document_type=CompanyDocumentType.LICENSE,
        expiry_date=date.today() + timedelta(days=30),
        metadata={},
    )
    store.create.return_value = sample
    store.get.return_value = sample
    store.update.return_value = sample
    store.delete.return_value = True
    store.list_by_company.return_value = [sample]
    store.list_expiring.return_value = [sample]
    return store


@pytest.fixture
async def cd_client(mock_company_doc_store):
    """Async client with company document store override."""
    app.dependency_overrides[get_company_doc_store] = lambda: mock_company_doc_store
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_company_doc_store, None)


class TestCompanyDocumentsAPI:
    """Smoke tests for company documents API."""

    async def test_create_endpoint_exists(self, cd_client: AsyncClient):
        """Test that POST /api/company-documents endpoint exists."""
        response = await cd_client.post(
            "/api/company-documents",
            json={
                "company_key": "ACME",
                "title": "Test License",
                "document_type": "license",
            },
        )
        # Should not be 404 (endpoint exists)
        assert response.status_code != 404

    async def test_list_endpoint_exists(self, cd_client: AsyncClient):
        """Test that GET /api/company-documents endpoint exists."""
        response = await cd_client.get("/api/company-documents")
        assert response.status_code != 404

    async def test_expiring_endpoint_exists(self, cd_client: AsyncClient):
        """Test that GET /api/company-documents/expiring endpoint exists."""
        response = await cd_client.get("/api/company-documents/expiring")
        assert response.status_code != 404

    async def test_get_by_id_endpoint_exists(self, cd_client: AsyncClient):
        """Test that GET /api/company-documents/{id} returns 200 with mock store."""
        response = await cd_client.get("/api/company-documents/1")
        assert response.status_code == 200

    async def test_delete_endpoint_exists(self, cd_client: AsyncClient):
        """Test that DELETE /api/company-documents/{id} returns 204 with mock store."""
        response = await cd_client.delete("/api/company-documents/1")
        assert response.status_code == 204


class TestCheckExpiryEndpoint:
    """Tests for POST /api/company-documents/check-expiry."""

    @pytest.fixture
    def mock_use_case(self):
        """Create mock expiry check use case."""
        uc = AsyncMock()
        uc.execute.return_value = ExpiryCheckResult(
            total_expiring=3,
            reminders_created=2,
            already_reminded=1,
            created_reminder_ids=[101, 102],
        )
        return uc

    @pytest.fixture
    async def expiry_client(self, mock_use_case):
        """Async client with expiry check use case override."""
        app.dependency_overrides[get_check_expiring_documents_use_case] = lambda: mock_use_case
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            yield ac
        app.dependency_overrides.pop(get_check_expiring_documents_use_case, None)

    async def test_check_expiry_endpoint_exists(self, expiry_client: AsyncClient):
        """Test that POST /api/company-documents/check-expiry exists."""
        response = await expiry_client.post("/api/company-documents/check-expiry")
        assert response.status_code == 200

    async def test_check_expiry_returns_result(self, expiry_client: AsyncClient):
        """Test response body contains expiry check result."""
        response = await expiry_client.post("/api/company-documents/check-expiry")
        data = response.json()
        assert data["total_expiring"] == 3
        assert data["reminders_created"] == 2
        assert data["already_reminded"] == 1
        assert data["created_reminder_ids"] == [101, 102]

    async def test_check_expiry_custom_window(
        self, expiry_client: AsyncClient, mock_use_case,
    ):
        """Test that within_days query param is passed through."""
        await expiry_client.post("/api/company-documents/check-expiry?within_days=60")
        mock_use_case.execute.assert_awaited_once_with(within_days=60)
