"""Pytest configuration and fixtures."""

import asyncio
from collections.abc import AsyncGenerator, Generator

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient

from src.srg.config import settings
from src.srg.main import app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """Create event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def client() -> Generator[TestClient, None, None]:
    """Create sync test client."""
    with TestClient(app) as c:
        yield c


@pytest_asyncio.fixture
async def async_client() -> AsyncGenerator[AsyncClient, None]:
    """Create async test client."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def api_prefix() -> str:
    """Get API v1 prefix."""
    return settings.API_V1_PREFIX


@pytest.fixture
def sample_invoice_data() -> dict:
    """Sample invoice data for testing."""
    return {
        "invoice_number": "INV-2024-001",
        "vendor_name": "Test Vendor",
        "invoice_date": "2024-01-15",
        "total_amount": 1500.00,
        "currency": "DZD",
        "line_items": [
            {
                "description": "Test Product",
                "quantity": 10,
                "unit_price": 100.00,
                "total_price": 1000.00,
            },
            {
                "description": "Service Fee",
                "quantity": 1,
                "unit_price": 500.00,
                "total_price": 500.00,
            },
        ],
    }


@pytest.fixture
def sample_search_query() -> dict:
    """Sample search request for testing."""
    return {
        "query": "test product",
        "top_k": 5,
        "search_type": "hybrid",
        "use_reranker": True,
    }


@pytest.fixture
def sample_chat_message() -> dict:
    """Sample chat message for testing."""
    return {
        "message": "What invoices do we have from Test Vendor?",
        "use_rag": True,
        "top_k": 5,
    }
