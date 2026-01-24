"""
Async SQLite connection pool with aiosqlite.

Provides connection management with proper async context handling.
"""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import aiosqlite

from src.config import get_logger, get_settings

logger = get_logger(__name__)


class ConnectionPool:
    """
    Async SQLite connection pool.

    Manages a pool of connections with configurable size.
    """

    def __init__(
        self,
        db_path: Path,
        pool_size: int = 5,
        busy_timeout: int = 30000,
    ):
        self.db_path = db_path
        self.pool_size = pool_size
        self.busy_timeout = busy_timeout

        self._pool: asyncio.Queue[aiosqlite.Connection] = asyncio.Queue(maxsize=pool_size)
        self._connections: list[aiosqlite.Connection] = []
        self._initialized = False
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the connection pool."""
        async with self._lock:
            if self._initialized:
                return

            # Ensure database directory exists
            self.db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create connections
            for _ in range(self.pool_size):
                conn = await self._create_connection()
                self._connections.append(conn)
                await self._pool.put(conn)

            self._initialized = True
            logger.info(
                "connection_pool_initialized",
                db_path=str(self.db_path),
                pool_size=self.pool_size,
            )

    async def _create_connection(self) -> aiosqlite.Connection:
        """Create a new database connection with optimized settings."""
        conn = await aiosqlite.connect(self.db_path)

        # Enable WAL mode for better concurrency
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA synchronous=NORMAL")
        await conn.execute(f"PRAGMA busy_timeout={self.busy_timeout}")

        # Enable foreign keys
        await conn.execute("PRAGMA foreign_keys=ON")

        # Row factory for dict-like access
        conn.row_factory = aiosqlite.Row

        return conn

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Acquire a connection from the pool.

        Usage:
            async with pool.acquire() as conn:
                await conn.execute(...)
        """
        if not self._initialized:
            await self.initialize()

        conn = await self._pool.get()
        try:
            yield conn
        finally:
            await self._pool.put(conn)

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[aiosqlite.Connection]:
        """
        Acquire a connection with transaction context.

        Automatically commits on success, rolls back on exception.
        """
        async with self.acquire() as conn:
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise

    async def close(self) -> None:
        """Close all connections in the pool."""
        async with self._lock:
            for conn in self._connections:
                await conn.close()
            self._connections.clear()
            self._initialized = False
            logger.info("connection_pool_closed")


# Global connection pool
_pool: ConnectionPool | None = None


async def get_pool() -> ConnectionPool:
    """Get or create the global connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = ConnectionPool(
            db_path=settings.storage.db_path,
            pool_size=settings.storage.pool_size,
            busy_timeout=settings.storage.busy_timeout,
        )
        await _pool.initialize()
    return _pool


async def close_pool() -> None:
    """Close the global connection pool."""
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


@asynccontextmanager
async def get_connection() -> AsyncIterator[aiosqlite.Connection]:
    """
    Get a connection from the global pool.

    Convenience wrapper for common usage.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        yield conn


@asynccontextmanager
async def get_transaction() -> AsyncIterator[aiosqlite.Connection]:
    """
    Get a connection with transaction context.

    Convenience wrapper for transactional operations.
    """
    pool = await get_pool()
    async with pool.transaction() as conn:
        yield conn
