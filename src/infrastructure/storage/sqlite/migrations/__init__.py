"""Database migrations module."""

from src.infrastructure.storage.sqlite.migrations.migrator import (
    MigrationInfo,
    MigrationResult,
    create_backup,
    discover_migrations,
    get_current_version,
    get_migration_status,
    initialize_database,
    rebuild_fts_indexes,
    restore_backup,
    run_migrations,
    verify_schema_integrity,
)

__all__ = [
    "MigrationInfo",
    "MigrationResult",
    "create_backup",
    "discover_migrations",
    "get_current_version",
    "get_migration_status",
    "initialize_database",
    "rebuild_fts_indexes",
    "restore_backup",
    "run_migrations",
    "verify_schema_integrity",
]
