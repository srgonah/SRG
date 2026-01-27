"""
Database schema migrator with versioned migrations.

Supports:
- Versioned SQL migrations (v001_, v002_, etc.)
- Migration tracking in schema_migrations table
- Validation before/after migrations
- FTS5 index rebuilding
- Rollback support via backup
"""

import asyncio
import hashlib
import re
import shutil
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import aiosqlite

from src.config import get_logger, get_settings

logger = get_logger(__name__)

MIGRATIONS_DIR = Path(__file__).parent
SCHEMA_FILE = MIGRATIONS_DIR / "schema.sql"  # Legacy compatibility


@dataclass
class MigrationInfo:
    """Information about a migration file."""

    version: str
    name: str
    path: Path
    checksum: str

    @classmethod
    def from_file(cls, path: Path) -> "MigrationInfo":
        """Parse migration info from filename."""
        # Expected format: v001_name.sql
        match = re.match(r"v(\d+)_(.+)\.sql", path.name)
        if not match:
            raise ValueError(f"Invalid migration filename: {path.name}")

        version = match.group(1)
        name = match.group(2)
        content = path.read_text(encoding="utf-8")
        checksum = hashlib.sha256(content.encode()).hexdigest()[:16]

        return cls(version=version, name=name, path=path, checksum=checksum)


@dataclass
class MigrationResult:
    """Result of a migration operation."""

    version: str
    name: str
    success: bool
    execution_time_ms: int
    error: str | None = None


async def get_applied_migrations(conn: aiosqlite.Connection) -> dict[str, str]:
    """Get dictionary of applied migration versions to checksums."""
    try:
        cursor = await conn.execute(
            "SELECT version, checksum FROM schema_migrations ORDER BY version"
        )
        rows = await cursor.fetchall()
        return {row[0]: row[1] for row in rows}
    except aiosqlite.OperationalError:
        # Table doesn't exist yet
        return {}


async def get_current_version(conn: aiosqlite.Connection) -> str | None:
    """Get current schema version from database."""
    try:
        # Try new schema_migrations table first
        cursor = await conn.execute(
            "SELECT version FROM schema_migrations ORDER BY version DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        if row:
            return row[0]

        # Fall back to legacy schema_version table
        cursor = await conn.execute(
            "SELECT version FROM schema_version ORDER BY applied_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return row[0] if row else None
    except aiosqlite.OperationalError:
        return None


def discover_migrations() -> list[MigrationInfo]:
    """Discover all migration files in order."""
    migrations = []
    for path in sorted(MIGRATIONS_DIR.glob("v*.sql")):
        try:
            migrations.append(MigrationInfo.from_file(path))
        except ValueError as e:
            logger.warning("skipping_invalid_migration", path=str(path), error=str(e))
    return migrations


async def validate_pre_migration(
    conn: aiosqlite.Connection,
    migration: MigrationInfo,
) -> list[dict]:
    """Run pre-migration validation checks."""
    checks = []

    # Check if migration already applied
    applied = await get_applied_migrations(conn)
    if migration.version in applied:
        if applied[migration.version] != migration.checksum:
            checks.append({
                "check": "checksum_mismatch",
                "status": "FAILED",
                "severity": "CRITICAL",
                "message": f"Migration {migration.version} has different checksum than applied version",
            })
        else:
            checks.append({
                "check": "already_applied",
                "status": "SKIPPED",
                "severity": "INFO",
                "message": f"Migration {migration.version} already applied",
            })

    return checks


async def validate_post_migration(
    conn: aiosqlite.Connection,
    migration: MigrationInfo,
) -> list[dict]:
    """Run post-migration validation checks."""
    checks = []

    # Verify migration was recorded
    cursor = await conn.execute(
        "SELECT 1 FROM schema_migrations WHERE version = ?",
        (migration.version,),
    )
    if not await cursor.fetchone():
        checks.append({
            "check": "migration_not_recorded",
            "status": "FAILED",
            "severity": "CRITICAL",
            "message": f"Migration {migration.version} not found in schema_migrations",
        })

    # Verify foreign key integrity
    cursor = await conn.execute("PRAGMA foreign_key_check")
    violations = await cursor.fetchall()
    if violations:
        checks.append({
            "check": "foreign_key_violation",
            "status": "FAILED",
            "severity": "CRITICAL",
            "message": f"Foreign key violations found: {len(violations)}",
        })

    return checks


async def apply_migration(
    conn: aiosqlite.Connection,
    migration: MigrationInfo,
) -> MigrationResult:
    """Apply a single migration."""
    logger.info(
        "applying_migration",
        version=migration.version,
        name=migration.name,
    )

    start_time = time.time()

    try:
        # Read migration SQL
        sql = migration.path.read_text(encoding="utf-8")

        # Execute migration
        await conn.executescript(sql)

        # Record migration (if not already recorded by the migration itself)
        await conn.execute(
            """
            INSERT OR REPLACE INTO schema_migrations (version, name, checksum, execution_time_ms)
            VALUES (?, ?, ?, ?)
            """,
            (
                migration.version,
                migration.name,
                migration.checksum,
                int((time.time() - start_time) * 1000),
            ),
        )

        await conn.commit()

        execution_time = int((time.time() - start_time) * 1000)
        logger.info(
            "migration_applied",
            version=migration.version,
            name=migration.name,
            execution_time_ms=execution_time,
        )

        return MigrationResult(
            version=migration.version,
            name=migration.name,
            success=True,
            execution_time_ms=execution_time,
        )

    except Exception as e:
        await conn.rollback()
        execution_time = int((time.time() - start_time) * 1000)
        logger.error(
            "migration_failed",
            version=migration.version,
            name=migration.name,
            error=str(e),
        )
        return MigrationResult(
            version=migration.version,
            name=migration.name,
            success=False,
            execution_time_ms=execution_time,
            error=str(e),
        )


def create_backup(db_path: Path) -> Path:
    """Create a backup of the database before migration."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = db_path.with_suffix(f".backup_{timestamp}.db")
    shutil.copy2(db_path, backup_path)
    logger.info("database_backup_created", backup_path=str(backup_path))
    return backup_path


def restore_backup(db_path: Path, backup_path: Path) -> None:
    """Restore database from backup."""
    shutil.copy2(backup_path, db_path)
    logger.info("database_restored_from_backup", backup_path=str(backup_path))


async def initialize_database(
    db_path: Path | None = None,
    create_backup_before: bool = True,
) -> list[MigrationResult]:
    """
    Initialize the database with all pending migrations.

    Args:
        db_path: Path to database file (default from settings)
        create_backup_before: Whether to backup before migrations

    Returns:
        List of migration results
    """
    settings = get_settings()
    db_path = db_path or settings.storage.db_path

    # Ensure directory exists
    db_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info("initializing_database", db_path=str(db_path))

    # Create backup if database exists
    backup_path = None
    if create_backup_before and db_path.exists():
        backup_path = create_backup(db_path)

    results = []

    try:
        async with aiosqlite.connect(db_path) as conn:
            # Enable WAL mode and foreign keys
            await conn.execute("PRAGMA journal_mode=WAL")
            await conn.execute("PRAGMA foreign_keys=ON")

            # Discover migrations
            migrations = discover_migrations()
            if not migrations:
                logger.warning("no_migrations_found")
                return results

            # Get applied migrations
            applied = await get_applied_migrations(conn)

            # Apply pending migrations in order
            for migration in migrations:
                # Skip if already applied with same checksum
                if migration.version in applied:
                    if applied[migration.version] == migration.checksum:
                        logger.info(
                            "migration_already_applied",
                            version=migration.version,
                        )
                        continue
                    else:
                        logger.warning(
                            "migration_checksum_changed",
                            version=migration.version,
                        )

                # Validate before
                pre_checks = await validate_pre_migration(conn, migration)
                if any(c["status"] == "FAILED" for c in pre_checks):
                    logger.error("pre_migration_validation_failed", checks=pre_checks)
                    break

                if any(c["status"] == "SKIPPED" for c in pre_checks):
                    continue

                # Apply migration
                result = await apply_migration(conn, migration)
                results.append(result)

                if not result.success:
                    logger.error("migration_failed_stopping", version=migration.version)
                    break

                # Validate after
                post_checks = await validate_post_migration(conn, migration)
                if any(c["status"] == "FAILED" for c in post_checks):
                    logger.error("post_migration_validation_failed", checks=post_checks)
                    break

            # Verify tables
            cursor = await conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
            tables = [row[0] for row in await cursor.fetchall()]
            logger.info("database_tables", count=len(tables))

        # Clean up backup if all succeeded
        if backup_path and all(r.success for r in results):
            backup_path.unlink()
            logger.info("backup_cleaned_up")

    except Exception as e:
        logger.error("database_initialization_failed", error=str(e))
        if backup_path and backup_path.exists():
            restore_backup(db_path, backup_path)
        raise

    return results


# Alias for backward compatibility
run_migrations = initialize_database


async def rebuild_fts_indexes(db_path: Path | None = None) -> dict:
    """
    Rebuild FTS5 indexes from source tables.

    Returns:
        Dictionary with rebuild statistics
    """
    settings = get_settings()
    db_path = db_path or settings.storage.db_path

    stats = {
        "doc_chunks_fts": 0,
        "invoice_items_fts": 0,
    }

    async with aiosqlite.connect(db_path) as conn:
        logger.info("rebuilding_fts_indexes")

        # Rebuild doc_chunks_fts
        await conn.execute("DELETE FROM doc_chunks_fts")
        cursor = await conn.execute(
            "INSERT INTO doc_chunks_fts(rowid, chunk_text) "
            "SELECT id, chunk_text FROM doc_chunks"
        )
        stats["doc_chunks_fts"] = cursor.rowcount

        # Rebuild invoice_items_fts
        await conn.execute("DELETE FROM invoice_items_fts")
        cursor = await conn.execute(
            "INSERT INTO invoice_items_fts(rowid, item_name, description, hs_code) "
            "SELECT id, item_name, COALESCE(description, ''), COALESCE(hs_code, '') "
            "FROM invoice_items"
        )
        stats["invoice_items_fts"] = cursor.rowcount

        await conn.commit()
        logger.info("fts_indexes_rebuilt", stats=stats)

    return stats


async def get_migration_status(db_path: Path | None = None) -> dict:
    """
    Get current migration status.

    Returns:
        Dictionary with migration status information
    """
    settings = get_settings()
    db_path = db_path or settings.storage.db_path

    if not db_path.exists():
        return {
            "exists": False,
            "current_version": None,
            "applied_migrations": [],
            "pending_migrations": [],
        }

    async with aiosqlite.connect(db_path) as conn:
        current = await get_current_version(conn)
        applied = await get_applied_migrations(conn)
        discovered = discover_migrations()

        pending = [
            m for m in discovered
            if m.version not in applied
        ]

        return {
            "exists": True,
            "current_version": current,
            "applied_migrations": list(applied.keys()),
            "pending_migrations": [m.version for m in pending],
            "total_migrations": len(discovered),
        }


async def verify_schema_integrity(db_path: Path | None = None) -> list[dict]:
    """
    Verify database schema integrity.

    Returns:
        List of integrity check results
    """
    settings = get_settings()
    db_path = db_path or settings.storage.db_path

    checks = []

    async with aiosqlite.connect(db_path) as conn:
        # Check foreign key integrity
        cursor = await conn.execute("PRAGMA foreign_key_check")
        fk_violations = await cursor.fetchall()
        checks.append({
            "check": "foreign_keys",
            "status": "PASS" if not fk_violations else "FAIL",
            "violations": len(fk_violations),
        })

        # Check integrity
        cursor = await conn.execute("PRAGMA integrity_check")
        integrity = await cursor.fetchone()
        checks.append({
            "check": "integrity",
            "status": "PASS" if integrity[0] == "ok" else "FAIL",
            "result": integrity[0],
        })

        # Check required tables exist
        required_tables = [
            "documents",
            "doc_pages",
            "doc_chunks",
            "invoices",
            "invoice_items",
            "audit_results",
            "chat_sessions",
            "chat_messages",
            "memory_facts",
            "company_templates",
            "indexing_state",
            "schema_migrations",
        ]

        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        existing_tables = {row[0] for row in await cursor.fetchall()}

        missing = [t for t in required_tables if t not in existing_tables]
        checks.append({
            "check": "required_tables",
            "status": "PASS" if not missing else "FAIL",
            "missing": missing,
        })

        # Check FTS tables
        fts_tables = ["doc_chunks_fts", "invoice_items_fts"]
        missing_fts = [t for t in fts_tables if t not in existing_tables]
        checks.append({
            "check": "fts_tables",
            "status": "PASS" if not missing_fts else "FAIL",
            "missing": missing_fts,
        })

    return checks


def main() -> None:
    """CLI entry point for database migration."""
    import argparse

    parser = argparse.ArgumentParser(description="SRG Database Migrator")
    parser.add_argument(
        "--db-path",
        type=Path,
        help="Database path (default from settings)",
    )
    parser.add_argument(
        "--rebuild-fts",
        action="store_true",
        help="Rebuild FTS indexes",
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show migration status",
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        help="Verify schema integrity",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backup before migrations",
    )
    args = parser.parse_args()

    async def run():
        if args.status:
            status = await get_migration_status(args.db_path)
            print(f"Database exists: {status['exists']}")
            print(f"Current version: {status.get('current_version', 'N/A')}")
            print(f"Applied migrations: {status.get('applied_migrations', [])}")
            print(f"Pending migrations: {status.get('pending_migrations', [])}")

        elif args.verify:
            checks = await verify_schema_integrity(args.db_path)
            for check in checks:
                status = "PASS" if check["status"] == "PASS" else "FAIL"
                print(f"[{status}] {check['check']}")
                if check["status"] != "PASS":
                    for key, value in check.items():
                        if key not in ("check", "status"):
                            print(f"       {key}: {value}")

        elif args.rebuild_fts:
            stats = await rebuild_fts_indexes(args.db_path)
            print(f"FTS indexes rebuilt: {stats}")

        else:
            results = await initialize_database(
                args.db_path,
                create_backup_before=not args.no_backup,
            )
            for result in results:
                status = "SUCCESS" if result.success else "FAILED"
                print(f"[{status}] v{result.version}: {result.name} ({result.execution_time_ms}ms)")
                if result.error:
                    print(f"         Error: {result.error}")

    asyncio.run(run())


if __name__ == "__main__":
    main()
