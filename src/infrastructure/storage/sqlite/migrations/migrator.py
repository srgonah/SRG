"""
Database schema migrator.

Handles initial schema creation and version migrations.
"""

import asyncio
from pathlib import Path

import aiosqlite

from src.config import get_logger, get_settings

logger = get_logger(__name__)

SCHEMA_FILE = Path(__file__).parent / "schema.sql"


async def get_current_version(conn: aiosqlite.Connection) -> str | None:
    """Get current schema version from database."""
    try:
        cursor = await conn.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    except aiosqlite.OperationalError:
        return None


async def apply_schema(conn: aiosqlite.Connection, schema_sql: str) -> None:
    """Apply schema SQL to database."""
    # Use executescript to run the entire schema at once
    await conn.executescript(schema_sql)


async def initialize_database(db_path: Path | None = None) -> None:
    """
    Initialize the database with the current schema.

    Creates the database file and all tables if they don't exist.
    """
    settings = get_settings()
    db_path = db_path or settings.storage.db_path

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("initializing_database", db_path=str(db_path))

    # Read schema
    schema_sql = SCHEMA_FILE.read_text(encoding="utf-8")

    async with aiosqlite.connect(db_path) as conn:
        # Enable WAL mode
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")

        # Check current version
        current = await get_current_version(conn)

        if current is None:
            logger.info("applying_initial_schema")
            await apply_schema(conn, schema_sql)
            await conn.commit()
            logger.info("schema_applied", version="1.0.0")
        else:
            logger.info("schema_already_initialized", version=current)

        # Verify tables
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = [row[0] for row in await cursor.fetchall()]
        logger.info("database_tables", tables=tables)


# Alias for backward compatibility
run_migrations = initialize_database


async def rebuild_fts_indexes(db_path: Path | None = None) -> None:
    """Rebuild FTS5 indexes from source tables."""
    settings = get_settings()
    db_path = db_path or settings.storage.db_path

    async with aiosqlite.connect(db_path) as conn:
        logger.info("rebuilding_fts_indexes")

        # Rebuild doc_chunks_fts
        await conn.execute("DELETE FROM doc_chunks_fts")
        await conn.execute(
            "INSERT INTO doc_chunks_fts(rowid, chunk_text) SELECT id, chunk_text FROM doc_chunks"
        )

        # Rebuild invoice_items_fts
        await conn.execute("DELETE FROM invoice_items_fts")
        await conn.execute(
            "INSERT INTO invoice_items_fts(rowid, item_name, description, hs_code) "
            "SELECT id, item_name, COALESCE(description, ''), COALESCE(hs_code, '') "
            "FROM invoice_items"
        )

        await conn.commit()
        logger.info("fts_indexes_rebuilt")


def main() -> None:
    """CLI entry point for database migration."""
    import argparse

    parser = argparse.ArgumentParser(description="SRG Database Migrator")
    parser.add_argument("--db-path", type=Path, help="Database path (default from settings)")
    parser.add_argument("--rebuild-fts", action="store_true", help="Rebuild FTS indexes")
    args = parser.parse_args()

    async def run():
        if args.rebuild_fts:
            await rebuild_fts_indexes(args.db_path)
        else:
            await initialize_database(args.db_path)

    asyncio.run(run())


if __name__ == "__main__":
    main()
