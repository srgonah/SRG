"""Database session management."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from src.infrastructure.storage.sqlite import get_connection_pool


@asynccontextmanager
async def get_db_session() -> AsyncGenerator:
    """
    Get database session context manager.

    Usage:
        async with get_db_session() as session:
            await session.execute("SELECT 1")
    """
    pool = await get_connection_pool()
    async with pool.connection() as conn:
        yield conn
