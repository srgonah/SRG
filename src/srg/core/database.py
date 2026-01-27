"""Database session management."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from src.infrastructure.storage.sqlite import get_connection_pool


@asynccontextmanager
async def get_db_session() -> AsyncIterator[Any]:
    """
    Get database session context manager.

    Usage:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
    """
    pool = await get_connection_pool()
    async with pool.acquire() as conn:
        yield conn
