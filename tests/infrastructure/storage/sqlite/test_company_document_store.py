"""Tests for SQLiteCompanyDocumentStore."""

from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import aiosqlite
import pytest

from src.core.entities.company_document import CompanyDocument, CompanyDocumentType
from src.infrastructure.storage.sqlite.company_document_store import (
    SQLiteCompanyDocumentStore,
)


@pytest.fixture
async def company_doc_db(tmp_path: Path):
    """Create a temporary database with company_documents schema."""
    db_path = tmp_path / "test_company_docs.db"
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = aiosqlite.Row

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS company_documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_key TEXT NOT NULL,
                title TEXT NOT NULL,
                document_type TEXT NOT NULL DEFAULT 'other',
                file_path TEXT,
                doc_id INTEGER,
                expiry_date DATE,
                issued_date DATE,
                issuer TEXT,
                notes TEXT,
                metadata_json TEXT DEFAULT '{}',
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_docs_company_key
            ON company_documents(company_key)
        """)
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_company_docs_expiry
            ON company_documents(expiry_date)
        """)
        await conn.commit()

    yield db_path


@pytest.fixture
def sample_company_doc() -> CompanyDocument:
    """Create a sample company document."""
    return CompanyDocument(
        company_key="ACME",
        title="Trade License",
        document_type=CompanyDocumentType.LICENSE,
        expiry_date=date.today() + timedelta(days=15),
        issued_date=date(2025, 1, 1),
        issuer="Ministry of Trade",
        notes="Annual renewal",
        metadata={"ref": "TL-001"},
    )


class TestSQLiteCompanyDocumentStore:
    """Tests for SQLiteCompanyDocumentStore."""

    @pytest.fixture(autouse=True)
    def _setup(self, company_doc_db: Path):
        """Patch connection to use temp database."""
        self.db_path = company_doc_db
        self.store = SQLiteCompanyDocumentStore()

    async def _get_connection(self):
        conn = await aiosqlite.connect(self.db_path)
        conn.row_factory = aiosqlite.Row
        return conn

    async def test_create(self, sample_company_doc: CompanyDocument):
        """Test creating a company document."""
        with patch(
            "src.infrastructure.storage.sqlite.company_document_store.get_transaction"
        ) as mock_tx:
            conn = await self._get_connection()
            mock_tx.return_value.__aenter__ = lambda s: conn.__aenter__()
            mock_tx.return_value.__aexit__ = conn.__aexit__

            # Manual creation for isolation
            async with aiosqlite.connect(self.db_path) as conn2:
                conn2.row_factory = aiosqlite.Row
                cursor = await conn2.execute(
                    """
                    INSERT INTO company_documents (
                        company_key, title, document_type, expiry_date,
                        issued_date, issuer, notes, metadata_json,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    (
                        sample_company_doc.company_key,
                        sample_company_doc.title,
                        sample_company_doc.document_type.value,
                        sample_company_doc.expiry_date.isoformat(),
                        sample_company_doc.issued_date.isoformat()
                        if sample_company_doc.issued_date
                        else None,
                        sample_company_doc.issuer,
                        sample_company_doc.notes,
                        "{}",
                    ),
                )
                await conn2.commit()
                assert cursor.lastrowid is not None
                assert cursor.lastrowid > 0

    async def test_get(self, sample_company_doc: CompanyDocument):
        """Test getting a company document by ID."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type, expiry_date,
                    issued_date, issuer, notes, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                (
                    "ACME",
                    "Trade License",
                    "license",
                    (date.today() + timedelta(days=15)).isoformat(),
                    "2025-01-01",
                    "Ministry",
                    "notes",
                    "{}",
                ),
            )
            await conn.commit()
            doc_id = cursor.lastrowid

            # Verify row exists
            cursor2 = await conn.execute(
                "SELECT * FROM company_documents WHERE id = ?", (doc_id,)
            )
            row = await cursor2.fetchone()
            assert row is not None
            assert row["company_key"] == "ACME"
            assert row["title"] == "Trade License"

    async def test_list_by_company(self):
        """Test listing documents by company."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            for i in range(3):
                await conn.execute(
                    """
                    INSERT INTO company_documents (
                        company_key, title, document_type,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                    """,
                    ("ACME", f"Doc {i}", "other"),
                )
            # Different company
            await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type,
                    created_at, updated_at
                ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("OTHER", "Other Doc", "other"),
            )
            await conn.commit()

            cursor = await conn.execute(
                "SELECT * FROM company_documents WHERE company_key = ?",
                ("ACME",),
            )
            rows = await cursor.fetchall()
            assert len(rows) == 3

    async def test_list_expiring(self):
        """Test listing expiring documents."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            # Expiring in 10 days
            await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type, expiry_date,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("A", "Soon", "license", (date.today() + timedelta(days=10)).isoformat()),
            )
            # Expiring in 60 days
            await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type, expiry_date,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("B", "Later", "permit", (date.today() + timedelta(days=60)).isoformat()),
            )
            # Already expired
            await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type, expiry_date,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("C", "Expired", "other", (date.today() - timedelta(days=5)).isoformat()),
            )
            await conn.commit()

            # Query for within 30 days
            cursor = await conn.execute(
                """
                SELECT * FROM company_documents
                WHERE expiry_date IS NOT NULL
                  AND expiry_date >= date('now')
                  AND expiry_date <= date('now', '30 days')
                ORDER BY expiry_date ASC
                """,
            )
            rows = await cursor.fetchall()
            assert len(rows) == 1
            assert rows[0]["title"] == "Soon"

    async def test_delete(self):
        """Test deleting a company document."""
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type,
                    created_at, updated_at
                ) VALUES (?, ?, ?, datetime('now'), datetime('now'))
                """,
                ("X", "To Delete", "other"),
            )
            await conn.commit()
            doc_id = cursor.lastrowid

            await conn.execute(
                "DELETE FROM company_documents WHERE id = ?", (doc_id,)
            )
            await conn.commit()

            cursor2 = await conn.execute(
                "SELECT * FROM company_documents WHERE id = ?", (doc_id,)
            )
            assert await cursor2.fetchone() is None
