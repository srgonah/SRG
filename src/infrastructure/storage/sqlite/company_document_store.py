"""
SQLite implementation of company document storage.

Handles CRUD and expiry queries for company documents.
"""

import json
from datetime import datetime

import aiosqlite

from src.config import get_logger
from src.core.entities.company_document import CompanyDocument, CompanyDocumentType
from src.core.interfaces.storage import ICompanyDocumentStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteCompanyDocumentStore(ICompanyDocumentStore):
    """SQLite implementation of company document storage."""

    async def create(self, doc: CompanyDocument) -> CompanyDocument:
        """Create a new company document record."""
        doc.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO company_documents (
                    company_key, title, document_type, file_path, doc_id,
                    expiry_date, issued_date, issuer, notes, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    doc.company_key,
                    doc.title,
                    doc.document_type.value,
                    doc.file_path,
                    doc.doc_id,
                    doc.expiry_date.isoformat() if doc.expiry_date else None,
                    doc.issued_date.isoformat() if doc.issued_date else None,
                    doc.issuer,
                    doc.notes,
                    json.dumps(doc.metadata),
                    doc.created_at.isoformat(),
                    doc.updated_at.isoformat(),
                ),
            )
            doc.id = cursor.lastrowid
            logger.info(
                "company_document_created",
                doc_id=doc.id,
                company_key=doc.company_key,
            )
            return doc

    async def get(self, doc_id: int) -> CompanyDocument | None:
        """Get company document by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM company_documents WHERE id = ?", (doc_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_entity(row)

    async def update(self, doc: CompanyDocument) -> CompanyDocument:
        """Update an existing company document."""
        doc.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE company_documents SET
                    company_key = ?, title = ?, document_type = ?,
                    file_path = ?, doc_id = ?, expiry_date = ?,
                    issued_date = ?, issuer = ?, notes = ?,
                    metadata_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    doc.company_key,
                    doc.title,
                    doc.document_type.value,
                    doc.file_path,
                    doc.doc_id,
                    doc.expiry_date.isoformat() if doc.expiry_date else None,
                    doc.issued_date.isoformat() if doc.issued_date else None,
                    doc.issuer,
                    doc.notes,
                    json.dumps(doc.metadata),
                    doc.updated_at.isoformat(),
                    doc.id,
                ),
            )
            logger.info("company_document_updated", doc_id=doc.id)
            return doc

    async def delete(self, doc_id: int) -> bool:
        """Delete a company document by ID."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM company_documents WHERE id = ?", (doc_id,)
            )
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info("company_document_deleted", doc_id=doc_id)
            return deleted

    async def list_by_company(
        self, company_key: str, limit: int = 100, offset: int = 0
    ) -> list[CompanyDocument]:
        """List company documents for a given company."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM company_documents
                WHERE company_key = ?
                ORDER BY expiry_date ASC NULLS LAST
                LIMIT ? OFFSET ?
                """,
                (company_key, limit, offset),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]

    async def list_expiring(
        self, within_days: int = 30, limit: int = 100
    ) -> list[CompanyDocument]:
        """List documents expiring within the given number of days."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM company_documents
                WHERE expiry_date IS NOT NULL
                  AND expiry_date >= date('now')
                  AND expiry_date <= date('now', ? || ' days')
                ORDER BY expiry_date ASC
                LIMIT ?
                """,
                (str(within_days), limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_entity(row) for row in rows]

    @staticmethod
    def _row_to_entity(row: aiosqlite.Row) -> CompanyDocument:
        """Convert a database row to a CompanyDocument entity."""
        from datetime import date as date_type

        metadata = {}
        metadata_raw = row["metadata_json"]
        if metadata_raw:
            try:
                metadata = json.loads(metadata_raw)
            except (json.JSONDecodeError, TypeError):
                pass

        expiry_date = None
        if row["expiry_date"]:
            try:
                expiry_date = date_type.fromisoformat(row["expiry_date"])
            except (ValueError, TypeError):
                pass

        issued_date = None
        if row["issued_date"]:
            try:
                issued_date = date_type.fromisoformat(row["issued_date"])
            except (ValueError, TypeError):
                pass

        created_at = datetime.utcnow()
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        updated_at = datetime.utcnow()
        if row["updated_at"]:
            try:
                updated_at = datetime.fromisoformat(row["updated_at"])
            except (ValueError, TypeError):
                pass

        return CompanyDocument(
            id=row["id"],
            company_key=row["company_key"],
            title=row["title"],
            document_type=CompanyDocumentType(row["document_type"]),
            file_path=row["file_path"],
            doc_id=row["doc_id"],
            expiry_date=expiry_date,
            issued_date=issued_date,
            issuer=row["issuer"],
            notes=row["notes"],
            metadata=metadata,
            created_at=created_at,
            updated_at=updated_at,
        )
