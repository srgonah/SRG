"""
SQLite implementation of invoice storage.

Handles invoices, line items, and audit results.
"""

import json
from datetime import datetime
from typing import Any

import aiosqlite

from src.config import get_logger
from src.core.entities import (
    ArithmeticCheckContainer,
    AuditIssue,
    AuditResult,
    AuditStatus,
    BankDetails,
    Invoice,
    LineItem,
    ParsingStatus,
    RowType,
)
from src.core.interfaces import IInvoiceStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteInvoiceStore(IInvoiceStore):
    """SQLite implementation of invoice storage."""

    async def create_invoice(self, invoice: Invoice) -> Invoice:
        """Create a new invoice record."""
        async with get_transaction() as conn:
            # Insert invoice
            cursor = await conn.execute(
                """
                INSERT INTO invoices (
                    doc_id, invoice_no, invoice_date, seller_name, buyer_name,
                    company_key, currency, total_amount, subtotal, tax_amount,
                    discount_amount, total_quantity, quality_score, confidence,
                    template_confidence, parser_version, template_id, parsing_status,
                    error_message, bank_details_json, is_latest, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.doc_id,
                    invoice.invoice_no,
                    invoice.invoice_date,
                    invoice.seller_name,
                    invoice.buyer_name,
                    invoice.company_key,
                    invoice.currency,
                    invoice.total_amount,
                    invoice.subtotal,
                    invoice.tax_amount,
                    invoice.discount_amount,
                    invoice.total_quantity,
                    invoice.quality_score,
                    invoice.confidence,
                    invoice.template_confidence,
                    invoice.parser_version,
                    invoice.template_id,
                    invoice.parsing_status.value,
                    invoice.error_message,
                    json.dumps(invoice.bank_details.model_dump()) if invoice.bank_details else None,
                    1,
                    invoice.created_at.isoformat(),
                    invoice.updated_at.isoformat(),
                ),
            )
            invoice.id = cursor.lastrowid

            # Insert items
            for item in invoice.items:
                item.invoice_id = invoice.id
                await self._insert_item(conn, item)

            logger.info("invoice_created", invoice_id=invoice.id, items=len(invoice.items))
            return invoice

    async def _insert_item(self, conn: aiosqlite.Connection, item: LineItem) -> None:
        """Insert a single line item."""
        cursor = await conn.execute(
            """
            INSERT INTO invoice_items (
                invoice_id, line_number, item_name, description, hs_code,
                unit, brand, model, quantity, unit_price, total_price, row_type
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item.invoice_id,
                item.line_number,
                item.item_name,
                item.description,
                item.hs_code,
                item.unit,
                item.brand,
                item.model,
                item.quantity,
                item.unit_price,
                item.total_price,
                item.row_type.value,
            ),
        )
        item.id = cursor.lastrowid

        # Update FTS
        await conn.execute(
            """
            INSERT INTO invoice_items_fts(rowid, item_name, description, hs_code)
            VALUES (?, ?, ?, ?)
            """,
            (item.id, item.item_name, item.description or "", item.hs_code or ""),
        )

    async def get_invoice(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID with items."""
        async with get_connection() as conn:
            cursor = await conn.execute("SELECT * FROM invoices WHERE id = ?", (invoice_id,))
            row = await cursor.fetchone()
            if row is None:
                return None

            invoice = self._row_to_invoice(row)

            # Load items
            items_cursor = await conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY line_number",
                (invoice_id,),
            )
            items_rows = await items_cursor.fetchall()
            invoice.items = [self._row_to_item(r) for r in items_rows]

            return invoice

    async def get_invoice_by_doc_id(self, doc_id: int) -> Invoice | None:
        """Get invoice by document ID."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM invoices WHERE doc_id = ? AND is_latest = 1",
                (doc_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            invoice = self._row_to_invoice(row)

            # Load items
            items_cursor = await conn.execute(
                "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY line_number",
                (invoice.id,),
            )
            items_rows = await items_cursor.fetchall()
            invoice.items = [self._row_to_item(r) for r in items_rows]

            return invoice

    async def update_invoice(self, invoice: Invoice) -> Invoice:
        """Update invoice record."""
        invoice.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE invoices SET
                    invoice_no = ?, invoice_date = ?, seller_name = ?, buyer_name = ?,
                    company_key = ?, currency = ?, total_amount = ?, subtotal = ?,
                    tax_amount = ?, discount_amount = ?, quality_score = ?, confidence = ?,
                    parsing_status = ?, error_message = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    invoice.invoice_no,
                    invoice.invoice_date,
                    invoice.seller_name,
                    invoice.buyer_name,
                    invoice.company_key,
                    invoice.currency,
                    invoice.total_amount,
                    invoice.subtotal,
                    invoice.tax_amount,
                    invoice.discount_amount,
                    invoice.quality_score,
                    invoice.confidence,
                    invoice.parsing_status.value,
                    invoice.error_message,
                    invoice.updated_at.isoformat(),
                    invoice.id,
                ),
            )
            return invoice

    async def delete_invoice(self, invoice_id: int) -> bool:
        """Delete invoice and items."""
        async with get_transaction() as conn:
            cursor = await conn.execute("SELECT id FROM invoices WHERE id = ?", (invoice_id,))
            if await cursor.fetchone() is None:
                return False

            # Delete FTS entries for items
            await conn.execute(
                """
                DELETE FROM invoice_items_fts
                WHERE rowid IN (SELECT id FROM invoice_items WHERE invoice_id = ?)
                """,
                (invoice_id,),
            )

            # Delete invoice (cascades to items)
            await conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))
            logger.info("invoice_deleted", invoice_id=invoice_id)
            return True

    async def list_invoices(
        self,
        limit: int = 100,
        offset: int = 0,
        company_key: str | None = None,
    ) -> list[Invoice]:
        """List invoices with pagination."""
        async with get_connection() as conn:
            if company_key:
                cursor = await conn.execute(
                    """
                    SELECT * FROM invoices
                    WHERE is_latest = 1 AND company_key = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (company_key, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM invoices
                    WHERE is_latest = 1
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = await cursor.fetchall()
            return [self._row_to_invoice(row) for row in rows]

    async def count_invoices(self, company_key: str | None = None) -> int:
        """Count total invoices."""
        async with get_connection() as conn:
            if company_key:
                cursor = await conn.execute(
                    "SELECT COUNT(*) FROM invoices WHERE is_latest = 1 AND company_key = ?",
                    (company_key,),
                )
            else:
                cursor = await conn.execute("SELECT COUNT(*) FROM invoices WHERE is_latest = 1")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def search_invoices(self, query: str, limit: int = 20) -> list[Invoice]:
        """Search invoices by invoice_no, seller, or buyer."""
        async with get_connection() as conn:
            pattern = f"%{query}%"
            cursor = await conn.execute(
                """
                SELECT * FROM invoices
                WHERE is_latest = 1
                AND (invoice_no LIKE ? OR seller_name LIKE ? OR buyer_name LIKE ?)
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (pattern, pattern, pattern, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_invoice(row) for row in rows]

    # Audit operations

    async def create_audit_result(self, result: AuditResult) -> AuditResult:
        """Store audit result."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO audit_results (
                    invoice_id, trace_id, success, audit_type, status, filename,
                    document_intake_json, proforma_summary_json, items_table_json,
                    arithmetic_check_json, amount_words_check_json, bank_details_check_json,
                    commercial_terms_json, contract_summary_json, final_verdict_json,
                    issues_json, processing_time, llm_model, confidence, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.invoice_id,
                    result.trace_id,
                    1 if result.success else 0,
                    result.audit_type,
                    result.status.value,
                    result.filename,
                    json.dumps(result.document_intake),
                    json.dumps(result.proforma_summary),
                    json.dumps(result.items_table),
                    json.dumps(result.arithmetic_check.model_dump()),
                    json.dumps(result.amount_words_check),
                    json.dumps(result.bank_details_check),
                    json.dumps(result.commercial_terms_suggestions),
                    json.dumps(result.contract_summary),
                    json.dumps(result.final_verdict),
                    json.dumps([i.model_dump() for i in result.issues]),
                    result.processing_time,
                    result.llm_model,
                    result.confidence,
                    result.error_message,
                ),
            )
            result.id = cursor.lastrowid
            logger.info("audit_result_created", audit_id=result.id, invoice_id=result.invoice_id)
            return result

    async def get_audit_result(self, invoice_id: int) -> AuditResult | None:
        """Get latest audit result for invoice."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM audit_results
                WHERE invoice_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (invoice_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None
            return self._row_to_audit_result(row)

    async def list_audit_results(
        self,
        invoice_id: int | None = None,
        limit: int = 100,
    ) -> list[AuditResult]:
        """List audit results."""
        async with get_connection() as conn:
            if invoice_id:
                cursor = await conn.execute(
                    """
                    SELECT * FROM audit_results
                    WHERE invoice_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (invoice_id, limit),
                )
            else:
                cursor = await conn.execute(
                    "SELECT * FROM audit_results ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                )

            rows = await cursor.fetchall()
            return [self._row_to_audit_result(row) for row in rows]

    async def update_item_material_id(
        self, item_id: int, material_id: str
    ) -> bool:
        """Set matched_material_id on an invoice item."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                "UPDATE invoice_items SET matched_material_id = ? WHERE id = ?",
                (material_id, item_id),
            )
            updated = cursor.rowcount > 0
            if updated:
                logger.info(
                    "item_material_linked",
                    item_id=item_id,
                    material_id=material_id,
                )
            return updated

    async def get_items_for_indexing(
        self,
        last_item_id: int = 0,
        limit: int = 1000,
    ) -> list[dict[str, Any]]:
        """Get items that need indexing."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT ii.id, ii.item_name, ii.hs_code, ii.unit, ii.brand, ii.model,
                       ii.quantity, ii.unit_price
                FROM invoice_items ii
                INNER JOIN invoices inv ON ii.invoice_id = inv.id
                WHERE ii.id > ? AND ii.row_type = 'line_item' AND inv.is_latest = 1
                ORDER BY ii.id
                LIMIT ?
                """,
                (last_item_id, limit),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "item_name": row["item_name"],
                    "hs_code": row["hs_code"],
                    "unit": row["unit"],
                    "brand": row["brand"],
                    "model": row["model"],
                    "quantity": row["quantity"],
                    "unit_price": row["unit_price"],
                }
                for row in rows
            ]

    async def list_unmatched_items(self, limit: int = 500) -> list[dict[str, Any]]:
        """List line items with no matched material."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT ii.id, ii.item_name, ii.hs_code, ii.unit, ii.unit_price
                FROM invoice_items ii
                INNER JOIN invoices inv ON ii.invoice_id = inv.id
                WHERE ii.row_type = 'line_item'
                  AND (ii.matched_material_id IS NULL OR ii.matched_material_id = '')
                  AND inv.is_latest = 1
                  AND ii.item_name != ''
                ORDER BY ii.id DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = await cursor.fetchall()
            return [
                {
                    "id": row["id"],
                    "item_name": row["item_name"],
                    "hs_code": row["hs_code"],
                    "unit": row["unit"],
                    "unit_price": row["unit_price"],
                }
                for row in rows
            ]

    # Conversion helpers

    def _row_to_invoice(self, row: aiosqlite.Row) -> Invoice:
        """Convert database row to Invoice entity."""
        bank_details = None
        if row["bank_details_json"]:
            bd = json.loads(row["bank_details_json"])
            bank_details = BankDetails(**bd)

        return Invoice(
            id=row["id"],
            doc_id=row["doc_id"],
            invoice_no=row["invoice_no"],
            invoice_date=row["invoice_date"],
            seller_name=row["seller_name"],
            buyer_name=row["buyer_name"],
            company_key=row["company_key"],
            currency=row["currency"],
            total_amount=row["total_amount"],
            subtotal=row["subtotal"],
            tax_amount=row["tax_amount"],
            discount_amount=row["discount_amount"],
            total_quantity=row["total_quantity"],
            quality_score=row["quality_score"],
            confidence=row["confidence"],
            template_confidence=row["template_confidence"],
            parser_version=row["parser_version"],
            template_id=row["template_id"],
            parsing_status=ParsingStatus(row["parsing_status"]),
            error_message=row["error_message"],
            bank_details=bank_details,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    def _row_to_item(self, row: aiosqlite.Row) -> LineItem:
        """Convert database row to LineItem entity."""
        return LineItem(
            id=row["id"],
            invoice_id=row["invoice_id"],
            line_number=row["line_number"],
            item_name=row["item_name"],
            description=row["description"] or "",
            hs_code=row["hs_code"],
            unit=row["unit"],
            brand=row["brand"],
            model=row["model"],
            quantity=row["quantity"],
            unit_price=row["unit_price"],
            total_price=row["total_price"],
            matched_material_id=row["matched_material_id"] if "matched_material_id" in row.keys() else None,
            row_type=RowType(row["row_type"]),
        )

    def _row_to_audit_result(self, row: aiosqlite.Row) -> AuditResult:
        """Convert database row to AuditResult entity."""
        issues_data = json.loads(row["issues_json"]) if row["issues_json"] else []
        issues = [AuditIssue(**i) for i in issues_data]

        arithmetic_data = (
            json.loads(row["arithmetic_check_json"]) if row["arithmetic_check_json"] else {}
        )
        arithmetic = ArithmeticCheckContainer(**arithmetic_data) if arithmetic_data else ArithmeticCheckContainer()

        return AuditResult(
            id=row["id"],
            invoice_id=row["invoice_id"],
            trace_id=row["trace_id"],
            success=bool(row["success"]),
            audit_type=row["audit_type"],
            status=AuditStatus(row["status"]),
            filename=row["filename"] or "",
            document_intake=json.loads(row["document_intake_json"])
            if row["document_intake_json"]
            else {},
            proforma_summary=json.loads(row["proforma_summary_json"])
            if row["proforma_summary_json"]
            else {},
            items_table=json.loads(row["items_table_json"]) if row["items_table_json"] else [],
            arithmetic_check=arithmetic,
            amount_words_check=json.loads(row["amount_words_check_json"])
            if row["amount_words_check_json"]
            else {},
            bank_details_check=json.loads(row["bank_details_check_json"])
            if row["bank_details_check_json"]
            else {},
            commercial_terms_suggestions=json.loads(row["commercial_terms_json"])
            if row["commercial_terms_json"]
            else [],
            contract_summary=json.loads(row["contract_summary_json"])
            if row["contract_summary_json"]
            else {},
            final_verdict=json.loads(row["final_verdict_json"])
            if row["final_verdict_json"]
            else {},
            issues=issues,
            processing_time=row["processing_time"],
            llm_model=row["llm_model"],
            confidence=row["confidence"],
            error_message=row["error_message"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
