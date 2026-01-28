"""API smoke tests for inventory endpoints."""

from datetime import date, datetime
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient

from src.api.dependencies import (
    get_inv_item_store,
    get_issue_stock_use_case,
    get_receive_stock_use_case,
)
from src.api.main import app
from src.application.use_cases.issue_stock import IssueStockResult, IssueStockUseCase
from src.application.use_cases.receive_stock import ReceiveStockResult, ReceiveStockUseCase
from src.core.entities.inventory import InventoryItem, MovementType, StockMovement


@pytest.fixture
def mock_inventory_store():
    store = AsyncMock()
    store.list_items.return_value = []
    store.get_movements.return_value = []
    return store


@pytest.fixture
def mock_receive_use_case():
    uc = AsyncMock(spec=ReceiveStockUseCase)
    now = datetime.utcnow()
    item = InventoryItem(id=1, material_id="MAT-001", quantity_on_hand=100, avg_cost=10.0, created_at=now, updated_at=now)
    mvmt = StockMovement(id=1, inventory_item_id=1, movement_type=MovementType.IN, quantity=100, unit_cost=10.0, movement_date=date.today(), created_at=now)
    result = ReceiveStockResult(inventory_item=item, movement=mvmt, created=True)
    uc.execute.return_value = result
    uc.to_response.return_value = ReceiveStockUseCase().to_response(result)
    return uc


@pytest.fixture
def mock_issue_use_case():
    uc = AsyncMock(spec=IssueStockUseCase)
    now = datetime.utcnow()
    item = InventoryItem(id=1, material_id="MAT-001", quantity_on_hand=70, avg_cost=10.0, created_at=now, updated_at=now)
    mvmt = StockMovement(id=1, inventory_item_id=1, movement_type=MovementType.OUT, quantity=30, unit_cost=10.0, movement_date=date.today(), created_at=now)
    result = IssueStockResult(inventory_item=item, movement=mvmt)
    uc.execute.return_value = result
    uc.to_response.return_value = IssueStockUseCase().to_response(result)
    return uc


@pytest.fixture
async def inv_client(mock_inventory_store, mock_receive_use_case, mock_issue_use_case):
    app.dependency_overrides[get_inv_item_store] = lambda: mock_inventory_store
    app.dependency_overrides[get_receive_stock_use_case] = lambda: mock_receive_use_case
    app.dependency_overrides[get_issue_stock_use_case] = lambda: mock_issue_use_case
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.pop(get_inv_item_store, None)
    app.dependency_overrides.pop(get_receive_stock_use_case, None)
    app.dependency_overrides.pop(get_issue_stock_use_case, None)


class TestInventoryAPI:
    async def test_receive_endpoint_exists(self, inv_client: AsyncClient):
        response = await inv_client.post(
            "/api/inventory/receive",
            json={"material_id": "MAT-001", "quantity": 100, "unit_cost": 10.0},
        )
        assert response.status_code != 404

    async def test_receive_returns_201(self, inv_client: AsyncClient):
        response = await inv_client.post(
            "/api/inventory/receive",
            json={"material_id": "MAT-001", "quantity": 100, "unit_cost": 10.0},
        )
        assert response.status_code == 201

    async def test_issue_endpoint_exists(self, inv_client: AsyncClient):
        response = await inv_client.post(
            "/api/inventory/issue",
            json={"material_id": "MAT-001", "quantity": 30},
        )
        assert response.status_code != 404

    async def test_status_endpoint_exists(self, inv_client: AsyncClient):
        response = await inv_client.get("/api/inventory/status")
        assert response.status_code != 404

    async def test_movements_endpoint_exists(self, inv_client: AsyncClient):
        response = await inv_client.get("/api/inventory/1/movements")
        assert response.status_code != 404
