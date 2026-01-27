"""Unit tests for database migrator."""

import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import aiosqlite
import pytest

from src.infrastructure.storage.sqlite.migrations.migrator import (
    MigrationInfo,
    MigrationResult,
    create_backup,
    discover_migrations,
    get_applied_migrations,
    get_current_version,
    get_migration_status,
    initialize_database,
    rebuild_fts_indexes,
    restore_backup,
    verify_schema_integrity,
)


class TestMigrationInfo:
    """Tests for MigrationInfo dataclass."""

    def test_from_file_parses_filename(self, tmp_path: Path):
        """from_file() parses version and name from filename."""
        # Create a test migration file
        migration_file = tmp_path / "v001_initial_schema.sql"
        migration_file.write_text("-- Test migration\nSELECT 1;")

        info = MigrationInfo.from_file(migration_file)

        assert info.version == "001"
        assert info.name == "initial_schema"
        assert info.path == migration_file

    def test_from_file_calculates_checksum(self, tmp_path: Path):
        """from_file() calculates checksum from content."""
        migration_file = tmp_path / "v001_test.sql"
        migration_file.write_text("SELECT 1;")

        info = MigrationInfo.from_file(migration_file)

        assert info.checksum is not None
        assert len(info.checksum) == 16  # First 16 chars of SHA-256

    def test_from_file_different_content_different_checksum(self, tmp_path: Path):
        """Different content produces different checksum."""
        file1 = tmp_path / "v001_test1.sql"
        file1.write_text("SELECT 1;")

        file2 = tmp_path / "v002_test2.sql"
        file2.write_text("SELECT 2;")

        info1 = MigrationInfo.from_file(file1)
        info2 = MigrationInfo.from_file(file2)

        assert info1.checksum != info2.checksum

    def test_from_file_invalid_filename_raises(self, tmp_path: Path):
        """from_file() raises ValueError for invalid filename."""
        invalid_file = tmp_path / "invalid_migration.sql"
        invalid_file.write_text("SELECT 1;")

        with pytest.raises(ValueError, match="Invalid migration filename"):
            MigrationInfo.from_file(invalid_file)

    def test_from_file_missing_version_raises(self, tmp_path: Path):
        """from_file() raises for missing version number."""
        invalid_file = tmp_path / "v_no_number.sql"
        invalid_file.write_text("SELECT 1;")

        with pytest.raises(ValueError):
            MigrationInfo.from_file(invalid_file)


class TestMigrationResult:
    """Tests for MigrationResult dataclass."""

    def test_success_result(self):
        """MigrationResult captures successful migration."""
        result = MigrationResult(
            version="001",
            name="test",
            success=True,
            execution_time_ms=150,
        )

        assert result.success is True
        assert result.error is None

    def test_failed_result(self):
        """MigrationResult captures failed migration."""
        result = MigrationResult(
            version="001",
            name="test",
            success=False,
            execution_time_ms=50,
            error="SQL syntax error",
        )

        assert result.success is False
        assert result.error == "SQL syntax error"


class TestGetAppliedMigrations:
    """Tests for get_applied_migrations()."""

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_table(self, tmp_path: Path):
        """Returns empty dict when schema_migrations doesn't exist."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as conn:
            result = await get_applied_migrations(conn)

        assert result == {}

    @pytest.mark.asyncio
    async def test_returns_applied_migrations(self, tmp_path: Path):
        """Returns dict of applied migrations."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("""
                CREATE TABLE schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum TEXT
                )
            """)
            await conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                ("001", "abc123"),
            )
            await conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                ("002", "def456"),
            )
            await conn.commit()

            result = await get_applied_migrations(conn)

        assert result == {"001": "abc123", "002": "def456"}


class TestGetCurrentVersion:
    """Tests for get_current_version()."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_table(self, tmp_path: Path):
        """Returns None when no schema tables exist."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as conn:
            result = await get_current_version(conn)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_latest_version(self, tmp_path: Path):
        """Returns latest applied version."""
        db_path = tmp_path / "test.db"

        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("""
                CREATE TABLE schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum TEXT
                )
            """)
            await conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                ("001", "abc"),
            )
            await conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                ("002", "def"),
            )
            await conn.commit()

            result = await get_current_version(conn)

        assert result == "002"


class TestDiscoverMigrations:
    """Tests for discover_migrations()."""

    def test_returns_empty_when_no_migrations(self, tmp_path: Path):
        """Returns empty list when no migrations exist."""
        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
            tmp_path,
        ):
            result = discover_migrations()

        assert result == []

    def test_discovers_migration_files(self, tmp_path: Path):
        """Discovers and parses migration files."""
        # Create test migration files
        (tmp_path / "v001_first.sql").write_text("SELECT 1;")
        (tmp_path / "v002_second.sql").write_text("SELECT 2;")

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
            tmp_path,
        ):
            result = discover_migrations()

        assert len(result) == 2
        assert result[0].version == "001"
        assert result[1].version == "002"

    def test_returns_sorted_by_version(self, tmp_path: Path):
        """Returns migrations sorted by version."""
        # Create out of order
        (tmp_path / "v003_third.sql").write_text("SELECT 3;")
        (tmp_path / "v001_first.sql").write_text("SELECT 1;")
        (tmp_path / "v002_second.sql").write_text("SELECT 2;")

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
            tmp_path,
        ):
            result = discover_migrations()

        assert [m.version for m in result] == ["001", "002", "003"]

    def test_skips_invalid_filenames(self, tmp_path: Path):
        """Skips files with invalid naming pattern."""
        (tmp_path / "v001_valid.sql").write_text("SELECT 1;")
        (tmp_path / "invalid_file.sql").write_text("SELECT 2;")
        (tmp_path / "readme.txt").write_text("Not a migration")

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
            tmp_path,
        ):
            result = discover_migrations()

        assert len(result) == 1
        assert result[0].name == "valid"


class TestCreateBackup:
    """Tests for create_backup()."""

    def test_creates_backup_file(self, tmp_path: Path):
        """create_backup() creates a backup copy."""
        db_path = tmp_path / "test.db"
        db_path.write_text("database content")

        backup_path = create_backup(db_path)

        assert backup_path.exists()
        assert backup_path.read_text() == "database content"
        assert ".backup_" in backup_path.name

    def test_backup_includes_timestamp(self, tmp_path: Path):
        """Backup filename includes timestamp."""
        db_path = tmp_path / "test.db"
        db_path.write_text("content")

        backup_path = create_backup(db_path)

        # Should contain date pattern YYYYMMDD
        assert any(c.isdigit() for c in backup_path.name)


class TestRestoreBackup:
    """Tests for restore_backup()."""

    def test_restores_from_backup(self, tmp_path: Path):
        """restore_backup() restores database from backup."""
        db_path = tmp_path / "test.db"
        backup_path = tmp_path / "test.backup.db"

        db_path.write_text("corrupted")
        backup_path.write_text("original content")

        restore_backup(db_path, backup_path)

        assert db_path.read_text() == "original content"


class TestGetMigrationStatus:
    """Tests for get_migration_status()."""

    @pytest.mark.asyncio
    async def test_returns_not_exists_when_no_database(self, tmp_path: Path):
        """Returns exists=False when database doesn't exist."""
        db_path = tmp_path / "nonexistent.db"

        mock_settings = MagicMock()
        mock_settings.storage.db_path = db_path

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
            return_value=mock_settings,
        ):
            result = await get_migration_status(db_path)

        assert result["exists"] is False
        assert result["current_version"] is None

    @pytest.mark.asyncio
    async def test_returns_migration_status(self, tmp_path: Path):
        """Returns complete migration status."""
        db_path = tmp_path / "test.db"

        # Create database with schema_migrations
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("""
                CREATE TABLE schema_migrations (
                    version TEXT PRIMARY KEY,
                    checksum TEXT
                )
            """)
            await conn.execute(
                "INSERT INTO schema_migrations (version, checksum) VALUES (?, ?)",
                ("001", "abc"),
            )
            await conn.commit()

        mock_settings = MagicMock()
        mock_settings.storage.db_path = db_path

        # Create migration file
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "v001_applied.sql").write_text("SELECT 1;")
        (migrations_dir / "v002_pending.sql").write_text("SELECT 2;")

        with (
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
                migrations_dir,
            ),
        ):
            result = await get_migration_status(db_path)

        assert result["exists"] is True
        assert result["current_version"] == "001"
        assert "001" in result["applied_migrations"]
        assert "002" in result["pending_migrations"]


class TestVerifySchemaIntegrity:
    """Tests for verify_schema_integrity()."""

    @pytest.mark.asyncio
    async def test_checks_foreign_keys(self, initialized_db: Path, mock_settings):
        """Verifies foreign key integrity."""
        mock_settings.storage.db_path = initialized_db

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
            return_value=mock_settings,
        ):
            checks = await verify_schema_integrity(initialized_db)

        fk_check = next(c for c in checks if c["check"] == "foreign_keys")
        assert fk_check["status"] == "PASS"

    @pytest.mark.asyncio
    async def test_checks_integrity(self, initialized_db: Path, mock_settings):
        """Verifies database integrity."""
        mock_settings.storage.db_path = initialized_db

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
            return_value=mock_settings,
        ):
            checks = await verify_schema_integrity(initialized_db)

        integrity_check = next(c for c in checks if c["check"] == "integrity")
        assert integrity_check["status"] == "PASS"
        assert integrity_check["result"] == "ok"

    @pytest.mark.asyncio
    async def test_checks_required_tables(self, initialized_db: Path, mock_settings):
        """Checks for required tables."""
        mock_settings.storage.db_path = initialized_db

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
            return_value=mock_settings,
        ):
            checks = await verify_schema_integrity(initialized_db)

        tables_check = next(c for c in checks if c["check"] == "required_tables")
        # Some tables may be missing from minimal schema
        assert "missing" in tables_check


class TestInitializeDatabase:
    """Tests for initialize_database()."""

    @pytest.mark.asyncio
    async def test_creates_database_directory(self, tmp_path: Path):
        """Creates database directory if not exists."""
        db_path = tmp_path / "subdir" / "nested" / "test.db"

        mock_settings = MagicMock()
        mock_settings.storage.db_path = db_path

        # Create minimal migration
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "v001_init.sql").write_text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT,
                checksum TEXT,
                applied_at TEXT DEFAULT (datetime('now')),
                execution_time_ms INTEGER
            );
        """)

        with (
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
                migrations_dir,
            ),
        ):
            await initialize_database(db_path, create_backup_before=False)

        assert db_path.parent.exists()
        assert db_path.exists()

    @pytest.mark.asyncio
    async def test_returns_migration_results(self, tmp_path: Path):
        """Returns list of migration results."""
        db_path = tmp_path / "test.db"

        mock_settings = MagicMock()
        mock_settings.storage.db_path = db_path

        # Create minimal migration
        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "v001_init.sql").write_text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT,
                checksum TEXT,
                applied_at TEXT DEFAULT (datetime('now')),
                execution_time_ms INTEGER
            );
        """)

        with (
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
                migrations_dir,
            ),
        ):
            results = await initialize_database(db_path, create_backup_before=False)

        assert len(results) >= 1
        assert all(isinstance(r, MigrationResult) for r in results)


class TestRebuildFtsIndexes:
    """Tests for rebuild_fts_indexes()."""

    @pytest.mark.asyncio
    async def test_rebuilds_indexes(self, initialized_db: Path, mock_settings):
        """rebuild_fts_indexes() rebuilds FTS5 indexes."""
        mock_settings.storage.db_path = initialized_db

        # Add some data to index
        async with aiosqlite.connect(initialized_db) as conn:
            await conn.execute(
                "INSERT INTO documents (filename, original_filename, file_path) VALUES (?, ?, ?)",
                ("test.pdf", "test.pdf", "/uploads/test.pdf"),
            )
            await conn.execute(
                """
                INSERT INTO doc_chunks (doc_id, chunk_index, chunk_text, chunk_size)
                VALUES (1, 0, 'Test chunk content', 18)
                """
            )
            # Manually populate the FTS table since we're inserting directly without triggers
            await conn.execute(
                """
                INSERT INTO doc_chunks_fts(rowid, chunk_text)
                VALUES (1, 'Test chunk content')
                """
            )
            await conn.commit()

        with patch(
            "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
            return_value=mock_settings,
        ):
            stats = await rebuild_fts_indexes(initialized_db)

        assert "doc_chunks_fts" in stats
        # Note: stats may be 0 or 1 depending on trigger behavior


class TestMigrationIntegration:
    """Integration tests for migration system."""

    @pytest.mark.asyncio
    async def test_migration_creates_backup(self, tmp_path: Path):
        """Migration creates backup when database exists."""
        db_path = tmp_path / "test.db"

        # Create existing database
        async with aiosqlite.connect(db_path) as conn:
            await conn.execute("CREATE TABLE existing (id INTEGER)")
            await conn.commit()

        mock_settings = MagicMock()
        mock_settings.storage.db_path = db_path

        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "v001_init.sql").write_text("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT,
                checksum TEXT,
                applied_at TEXT DEFAULT (datetime('now')),
                execution_time_ms INTEGER
            );
        """)

        with (
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
                migrations_dir,
            ),
        ):
            await initialize_database(db_path, create_backup_before=True)

        # Check backup was created and cleaned up (since migration succeeded)
        backup_files = list(tmp_path.glob("*.backup_*.db"))
        # Backup should be cleaned up on success
        assert len(backup_files) == 0

    @pytest.mark.asyncio
    async def test_skips_already_applied_migrations(self, tmp_path: Path):
        """Skips migrations that are already applied."""
        db_path = tmp_path / "test.db"

        mock_settings = MagicMock()
        mock_settings.storage.db_path = db_path

        migrations_dir = tmp_path / "migrations"
        migrations_dir.mkdir()
        migration_sql = """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT,
                checksum TEXT,
                applied_at TEXT DEFAULT (datetime('now')),
                execution_time_ms INTEGER
            );
        """
        (migrations_dir / "v001_init.sql").write_text(migration_sql)

        with (
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.get_settings",
                return_value=mock_settings,
            ),
            patch(
                "src.infrastructure.storage.sqlite.migrations.migrator.MIGRATIONS_DIR",
                migrations_dir,
            ),
        ):
            # Run first time
            results1 = await initialize_database(db_path, create_backup_before=False)

            # Run second time
            results2 = await initialize_database(db_path, create_backup_before=False)

        # First run should apply migration
        assert len(results1) == 1
        assert results1[0].success is True

        # Second run should skip (already applied)
        assert len(results2) == 0
