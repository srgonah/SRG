"""Unit tests for SQLite connection pool."""

import asyncio
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.infrastructure.storage.sqlite.connection import (
    ConnectionPool,
    close_pool,
    get_connection,
    get_pool,
    get_transaction,
)


class TestConnectionPoolInit:
    """Tests for ConnectionPool initialization."""

    def test_init_sets_db_path(self, temp_db_path: Path):
        """Pool stores database path."""
        pool = ConnectionPool(temp_db_path)
        assert pool.db_path == temp_db_path

    def test_init_default_pool_size(self, temp_db_path: Path):
        """Default pool size is 5."""
        pool = ConnectionPool(temp_db_path)
        assert pool.pool_size == 5

    def test_init_custom_pool_size(self, temp_db_path: Path):
        """Custom pool size is accepted."""
        pool = ConnectionPool(temp_db_path, pool_size=10)
        assert pool.pool_size == 10

    def test_init_default_busy_timeout(self, temp_db_path: Path):
        """Default busy timeout is 30000ms."""
        pool = ConnectionPool(temp_db_path)
        assert pool.busy_timeout == 30000

    def test_init_custom_busy_timeout(self, temp_db_path: Path):
        """Custom busy timeout is accepted."""
        pool = ConnectionPool(temp_db_path, busy_timeout=60000)
        assert pool.busy_timeout == 60000

    def test_init_not_initialized(self, temp_db_path: Path):
        """Pool starts uninitialized."""
        pool = ConnectionPool(temp_db_path)
        assert pool._initialized is False

    def test_init_empty_connections(self, temp_db_path: Path):
        """Pool starts with no connections."""
        pool = ConnectionPool(temp_db_path)
        assert len(pool._connections) == 0


class TestConnectionPoolInitialize:
    """Tests for ConnectionPool.initialize()."""

    @pytest.mark.asyncio
    async def test_initialize_creates_directory(self, tmp_path: Path):
        """Initialize creates database directory if not exists."""
        db_path = tmp_path / "subdir" / "nested" / "test.db"
        pool = ConnectionPool(db_path, pool_size=1)

        await pool.initialize()
        assert db_path.parent.exists()
        await pool.close()

    @pytest.mark.asyncio
    async def test_initialize_creates_connections(self, temp_db_path: Path):
        """Initialize creates pool_size connections."""
        pool = ConnectionPool(temp_db_path, pool_size=3)
        await pool.initialize()

        assert len(pool._connections) == 3
        assert pool._pool.qsize() == 3
        await pool.close()

    @pytest.mark.asyncio
    async def test_initialize_idempotent(self, temp_db_path: Path):
        """Multiple initialize calls are safe."""
        pool = ConnectionPool(temp_db_path, pool_size=2)

        await pool.initialize()
        await pool.initialize()
        await pool.initialize()

        assert len(pool._connections) == 2  # Only 2, not 6
        await pool.close()

    @pytest.mark.asyncio
    async def test_initialize_sets_initialized_flag(self, temp_db_path: Path):
        """Initialize sets _initialized to True."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.initialize()

        assert pool._initialized is True
        await pool.close()


class TestConnectionPoolCreateConnection:
    """Tests for ConnectionPool._create_connection()."""

    @pytest.mark.asyncio
    async def test_create_connection_returns_connection(self, temp_db_path: Path):
        """_create_connection returns aiosqlite.Connection."""
        pool = ConnectionPool(temp_db_path)
        conn = await pool._create_connection()

        assert isinstance(conn, aiosqlite.Connection)
        await conn.close()

    @pytest.mark.asyncio
    async def test_create_connection_wal_mode(self, temp_db_path: Path):
        """Connection has WAL journal mode enabled."""
        pool = ConnectionPool(temp_db_path)
        conn = await pool._create_connection()

        cursor = await conn.execute("PRAGMA journal_mode")
        result = await cursor.fetchone()
        assert result[0].lower() == "wal"
        await conn.close()

    @pytest.mark.asyncio
    async def test_create_connection_foreign_keys_enabled(self, temp_db_path: Path):
        """Connection has foreign keys enabled."""
        pool = ConnectionPool(temp_db_path)
        conn = await pool._create_connection()

        cursor = await conn.execute("PRAGMA foreign_keys")
        result = await cursor.fetchone()
        assert result[0] == 1
        await conn.close()

    @pytest.mark.asyncio
    async def test_create_connection_row_factory_set(self, temp_db_path: Path):
        """Connection has Row factory set."""
        pool = ConnectionPool(temp_db_path)
        conn = await pool._create_connection()

        assert conn.row_factory == aiosqlite.Row
        await conn.close()


class TestConnectionPoolAcquire:
    """Tests for ConnectionPool.acquire()."""

    @pytest.mark.asyncio
    async def test_acquire_returns_connection(self, temp_db_path: Path):
        """acquire() yields a connection."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.initialize()

        async with pool.acquire() as conn:
            assert conn is not None
            assert isinstance(conn, aiosqlite.Connection)

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_auto_initializes(self, temp_db_path: Path):
        """acquire() initializes pool if not initialized."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        assert pool._initialized is False

        async with pool.acquire() as conn:
            assert pool._initialized is True
            assert conn is not None

        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_returns_connection_to_pool(self, temp_db_path: Path):
        """Connection is returned to pool after context exits."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.initialize()

        assert pool._pool.qsize() == 1

        async with pool.acquire() as _conn:
            assert pool._pool.qsize() == 0

        assert pool._pool.qsize() == 1
        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_returns_on_exception(self, temp_db_path: Path):
        """Connection is returned even if exception occurs."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.initialize()

        with pytest.raises(ValueError):
            async with pool.acquire() as _conn:
                raise ValueError("Test error")

        assert pool._pool.qsize() == 1
        await pool.close()

    @pytest.mark.asyncio
    async def test_acquire_blocks_when_pool_exhausted(self, temp_db_path: Path):
        """acquire() blocks when all connections are in use."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.initialize()

        # Hold the only connection
        async with pool.acquire() as _conn1:
            # Try to acquire another (should timeout)
            with pytest.raises(asyncio.TimeoutError):
                async with asyncio.timeout(0.1):
                    async with pool.acquire() as _conn2:
                        pass

        await pool.close()


class TestConnectionPoolTransaction:
    """Tests for ConnectionPool.transaction()."""

    @pytest.mark.asyncio
    async def test_transaction_commits_on_success(self, initialized_db: Path):
        """Transaction commits when context exits normally."""
        pool = ConnectionPool(initialized_db, pool_size=1)
        await pool.initialize()

        async with pool.transaction() as conn:
            await conn.execute(
                "INSERT INTO documents (filename) VALUES (?)",
                ("test.pdf",),
            )

        # Verify data was committed
        async with pool.acquire() as conn:
            cursor = await conn.execute("SELECT filename FROM documents")
            row = await cursor.fetchone()
            assert row["filename"] == "test.pdf"

        await pool.close()

    @pytest.mark.asyncio
    async def test_transaction_rollbacks_on_exception(self, initialized_db: Path):
        """Transaction rolls back when exception occurs."""
        pool = ConnectionPool(initialized_db, pool_size=1)
        await pool.initialize()

        with pytest.raises(ValueError):
            async with pool.transaction() as conn:
                await conn.execute(
                    "INSERT INTO documents (filename) VALUES (?)",
                    ("rollback_test.pdf",),
                )
                raise ValueError("Force rollback")

        # Verify data was NOT committed
        async with pool.acquire() as conn:
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM documents WHERE filename = ?",
                ("rollback_test.pdf",),
            )
            row = await cursor.fetchone()
            assert row[0] == 0

        await pool.close()


class TestConnectionPoolClose:
    """Tests for ConnectionPool.close()."""

    @pytest.mark.asyncio
    async def test_close_clears_connections(self, temp_db_path: Path):
        """close() clears all connections."""
        pool = ConnectionPool(temp_db_path, pool_size=2)
        await pool.initialize()
        assert len(pool._connections) == 2

        await pool.close()
        assert len(pool._connections) == 0

    @pytest.mark.asyncio
    async def test_close_resets_initialized_flag(self, temp_db_path: Path):
        """close() sets _initialized to False."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.initialize()
        assert pool._initialized is True

        await pool.close()
        assert pool._initialized is False

    @pytest.mark.asyncio
    async def test_close_safe_when_not_initialized(self, temp_db_path: Path):
        """close() is safe on uninitialized pool."""
        pool = ConnectionPool(temp_db_path, pool_size=1)
        await pool.close()  # Should not raise


class TestGetPool:
    """Tests for get_pool() global function."""

    @pytest.mark.asyncio
    async def test_get_pool_creates_pool(self, mock_settings):
        """get_pool() creates a new pool if none exists."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        # Reset global pool
        conn_module._pool = None

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            pool = await get_pool()

            assert pool is not None
            assert isinstance(pool, ConnectionPool)
            assert pool.db_path == mock_settings.storage.db_path

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_pool_returns_same_instance(self, mock_settings):
        """get_pool() returns the same pool on subsequent calls."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            pool1 = await get_pool()
            pool2 = await get_pool()

            assert pool1 is pool2

            await close_pool()


class TestClosePool:
    """Tests for close_pool() global function."""

    @pytest.mark.asyncio
    async def test_close_pool_closes_global_pool(self, mock_settings):
        """close_pool() closes and clears the global pool."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            await get_pool()
            assert conn_module._pool is not None

            await close_pool()
            assert conn_module._pool is None

    @pytest.mark.asyncio
    async def test_close_pool_safe_when_none(self):
        """close_pool() is safe when no pool exists."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        await close_pool()  # Should not raise


class TestGetConnection:
    """Tests for get_connection() convenience wrapper."""

    @pytest.mark.asyncio
    async def test_get_connection_yields_connection(self, mock_settings):
        """get_connection() yields a connection."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            async with get_connection() as conn:
                assert conn is not None
                assert isinstance(conn, aiosqlite.Connection)

            await close_pool()


class TestGetTransaction:
    """Tests for get_transaction() convenience wrapper."""

    @pytest.mark.asyncio
    async def test_get_transaction_commits(self, mock_settings, initialized_db: Path):
        """get_transaction() commits on success."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            async with get_transaction() as conn:
                await conn.execute(
                    "INSERT INTO documents (filename) VALUES (?)",
                    ("txn_test.pdf",),
                )

            # Verify commit
            async with get_connection() as conn:
                cursor = await conn.execute(
                    "SELECT filename FROM documents WHERE filename = ?",
                    ("txn_test.pdf",),
                )
                row = await cursor.fetchone()
                assert row is not None

            await close_pool()
