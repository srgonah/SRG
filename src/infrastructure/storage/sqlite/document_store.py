"""
SQLite implementation of document storage.

Handles documents, pages, and chunks with full CRUD operations.
"""

import json
from datetime import datetime

import aiosqlite

from src.config import get_logger
from src.core.entities import Chunk, Document, DocumentStatus, Page, PageType
from src.core.interfaces import IDocumentStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteDocumentStore(IDocumentStore):
    """SQLite implementation of document storage."""

    # Document operations

    async def create_document(self, document: Document) -> Document:
        """Create a new document record."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO documents (
                    filename, original_filename, file_path, file_hash, file_size,
                    mime_type, status, error_message, version, is_latest,
                    previous_version_id, page_count, company_key, metadata_json,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    document.filename,
                    document.original_filename,
                    document.file_path,
                    document.file_hash,
                    document.file_size,
                    document.mime_type,
                    document.status.value,
                    document.error_message,
                    document.version,
                    1 if document.is_latest else 0,
                    document.previous_version_id,
                    document.page_count,
                    document.company_key,
                    json.dumps(document.metadata),
                    document.created_at.isoformat(),
                    document.updated_at.isoformat(),
                ),
            )
            document.id = cursor.lastrowid
            logger.info("document_created", doc_id=document.id, filename=document.filename)
            return document

    async def get_document(self, doc_id: int) -> Document | None:
        """Get document by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM documents WHERE id = ?", (doc_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_document(row)

    async def get_document_by_hash(self, file_hash: str) -> Document | None:
        """Get document by file hash."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM documents WHERE file_hash = ? AND is_latest = 1",
                (file_hash,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_document(row)

    async def update_document(self, document: Document) -> Document:
        """Update existing document."""
        document.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE documents SET
                    filename = ?, file_path = ?, status = ?, error_message = ?,
                    is_latest = ?, page_count = ?, company_key = ?,
                    metadata_json = ?, updated_at = ?, indexed_at = ?
                WHERE id = ?
                """,
                (
                    document.filename,
                    document.file_path,
                    document.status.value,
                    document.error_message,
                    1 if document.is_latest else 0,
                    document.page_count,
                    document.company_key,
                    json.dumps(document.metadata),
                    document.updated_at.isoformat(),
                    document.indexed_at.isoformat() if document.indexed_at else None,
                    document.id,
                ),
            )
            return document

    async def delete_document(self, doc_id: int) -> bool:
        """Delete document and related data."""
        async with get_transaction() as conn:
            # Check exists
            cursor = await conn.execute("SELECT id FROM documents WHERE id = ?", (doc_id,))
            if await cursor.fetchone() is None:
                return False

            # Delete (cascades to pages, chunks, etc.)
            await conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            logger.info("document_deleted", doc_id=doc_id)
            return True

    async def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Document]:
        """List documents with pagination."""
        async with get_connection() as conn:
            if status:
                cursor = await conn.execute(
                    """
                    SELECT * FROM documents
                    WHERE is_latest = 1 AND status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM documents
                    WHERE is_latest = 1
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = await cursor.fetchall()
            return [self._row_to_document(row) for row in rows]

    # Page operations

    async def create_page(self, page: Page) -> Page:
        """Create a new page record."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO doc_pages (
                    doc_id, page_no, page_type, type_confidence,
                    text, text_length, image_path, image_hash, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    page.doc_id,
                    page.page_no,
                    page.page_type.value,
                    page.type_confidence,
                    page.text,
                    len(page.text),
                    page.image_path,
                    page.image_hash,
                    json.dumps(page.metadata),
                ),
            )
            page.id = cursor.lastrowid
            return page

    async def get_pages(self, doc_id: int) -> list[Page]:
        """Get all pages for a document."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM doc_pages WHERE doc_id = ? ORDER BY page_no",
                (doc_id,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_page(row) for row in rows]

    async def update_page(self, page: Page) -> Page:
        """Update page record."""
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE doc_pages SET
                    page_type = ?, type_confidence = ?, text = ?,
                    text_length = ?, image_path = ?, metadata_json = ?
                WHERE id = ?
                """,
                (
                    page.page_type.value,
                    page.type_confidence,
                    page.text,
                    len(page.text),
                    page.image_path,
                    json.dumps(page.metadata),
                    page.id,
                ),
            )
            return page

    # Chunk operations

    async def create_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Create multiple chunk records."""
        if not chunks:
            return []

        async with get_transaction() as conn:
            for chunk in chunks:
                cursor = await conn.execute(
                    """
                    INSERT INTO doc_chunks (
                        doc_id, page_id, chunk_index, chunk_text, chunk_size,
                        start_char, end_char, metadata_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        chunk.doc_id,
                        chunk.page_id,
                        chunk.chunk_index,
                        chunk.chunk_text,
                        len(chunk.chunk_text),
                        chunk.start_char,
                        chunk.end_char,
                        json.dumps(chunk.metadata),
                    ),
                )
                chunk.id = cursor.lastrowid

            # Update FTS index
            await conn.execute(
                """
                INSERT INTO doc_chunks_fts(rowid, chunk_text)
                SELECT id, chunk_text FROM doc_chunks
                WHERE id IN (SELECT MAX(id) FROM doc_chunks GROUP BY id HAVING MAX(id) > ?)
                """,
                ((chunks[0].id or 0) - 1 if chunks else 0,),
            )

            return chunks

    async def get_chunks(self, doc_id: int) -> list[Chunk]:
        """Get all chunks for a document."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM doc_chunks WHERE doc_id = ? ORDER BY chunk_index",
                (doc_id,),
            )
            rows = await cursor.fetchall()
            return [self._row_to_chunk(row) for row in rows]

    async def get_chunk_by_id(self, chunk_id: int) -> Chunk | None:
        """Get chunk by ID."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM doc_chunks WHERE id = ?", (chunk_id,))
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_chunk(row)

    async def get_chunks_for_indexing(
        self,
        last_chunk_id: int = 0,
        limit: int = 1000,
    ) -> list[Chunk]:
        """Get chunks that need indexing."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT c.* FROM doc_chunks c
                INNER JOIN documents d ON c.doc_id = d.id
                WHERE c.id > ? AND d.is_latest = 1
                ORDER BY c.id
                LIMIT ?
                """,
                (last_chunk_id, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_chunk(row) for row in rows]

    # Conversion helpers

    def _row_to_document(self, row: aiosqlite.Row) -> Document:
        """Convert database row to Document entity."""
        return Document(
            id=row["id"],
            filename=row["filename"],
            original_filename=row["original_filename"],
            file_path=row["file_path"],
            file_hash=row["file_hash"],
            file_size=row["file_size"],
            mime_type=row["mime_type"],
            status=DocumentStatus(row["status"]),
            error_message=row["error_message"],
            version=row["version"],
            is_latest=bool(row["is_latest"]),
            previous_version_id=row["previous_version_id"],
            page_count=row["page_count"],
            company_key=row["company_key"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            indexed_at=datetime.fromisoformat(row["indexed_at"]) if row["indexed_at"] else None,
        )

    def _row_to_page(self, row: aiosqlite.Row) -> Page:
        """Convert database row to Page entity."""
        return Page(
            id=row["id"],
            doc_id=row["doc_id"],
            page_no=row["page_no"],
            page_type=PageType(row["page_type"]),
            type_confidence=row["type_confidence"],
            text=row["text"] or "",
            text_length=row["text_length"],
            image_path=row["image_path"],
            image_hash=row["image_hash"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_chunk(self, row: aiosqlite.Row) -> Chunk:
        """Convert database row to Chunk entity."""
        return Chunk(
            id=row["id"],
            doc_id=row["doc_id"],
            page_id=row["page_id"],
            chunk_index=row["chunk_index"],
            chunk_text=row["chunk_text"],
            chunk_size=row["chunk_size"],
            start_char=row["start_char"],
            end_char=row["end_char"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )
