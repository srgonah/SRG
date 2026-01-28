"""SQLite implementation of local sales storage."""

from datetime import date, datetime

import aiosqlite

from src.config import get_logger
from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem
from src.core.interfaces.sales_store import ISalesStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteSalesStore(ISalesStore):
    """SQLite implementation of local sales invoice storage."""

    async def create_invoice(self, invoice: LocalSalesInvoice) -> LocalSalesInvoice:
        """Create a sales invoice with all its items."""
        now = datetime.utcnow()
        invoice.created_at = now
        invoice.updated_at = now
        async with get_transaction() as conn:
            # Insert invoice header
            cursor = await conn.execute(
                """
                INSERT INTO local_sales_invoices (
                    invoice_number, customer_name, sale_date,
                    subtotal, tax_amount, total_amount,
                    total_cost, total_profit, notes,
                    created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.invoice_number,
                    invoice.customer_name,
                    invoice.sale_date.isoformat(),
                    invoice.subtotal,
                    invoice.tax_amount,
                    invoice.total_amount,
                    invoice.total_cost,
                    invoice.total_profit,
                    invoice.notes,
                    invoice.created_at.isoformat(),
                    invoice.updated_at.isoformat(),
                ),
            )
            invoice.id = cursor.lastrowid

            # Insert items
            for item in invoice.items:
                item.sales_invoice_id = invoice.id
                item.created_at = now
                item_cursor = await conn.execute(
                    """
                    INSERT INTO local_sales_items (
                        sales_invoice_id, inventory_item_id, material_id,
                        description, quantity, unit_price,
                        cost_basis, line_total, profit, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item.sales_invoice_id,
                        item.inventory_item_id,
                        item.material_id,
                        item.description,
                        item.quantity,
                        item.unit_price,
                        item.cost_basis,
                        item.line_total,
                        item.profit,
                        item.created_at.isoformat(),
                    ),
                )
                item.id = item_cursor.lastrowid

            logger.info(
                "sales_invoice_created",
                invoice_id=invoice.id,
                items=len(invoice.items),
                total=invoice.total_amount,
            )
            return invoice

    async def get_invoice(self, invoice_id: int) -> LocalSalesInvoice | None:
        """Get sales invoice by ID with items."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM local_sales_invoices WHERE id = ?",
                (invoice_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            # Load items
            items_cursor = await conn.execute(
                """
                SELECT * FROM local_sales_items
                WHERE sales_invoice_id = ?
                ORDER BY id
                """,
                (invoice_id,),
            )
            item_rows = await items_cursor.fetchall()
            items = [self._row_to_sales_item(r) for r in item_rows]

            return self._row_to_sales_invoice(row, items)

    async def list_invoices(
        self, limit: int = 100, offset: int = 0
    ) -> list[LocalSalesInvoice]:
        """List sales invoices with pagination."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM local_sales_invoices
                ORDER BY sale_date DESC, id DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )
            rows = await cursor.fetchall()

            invoices = []
            for row in rows:
                inv_id = row["id"]
                items_cursor = await conn.execute(
                    """
                    SELECT * FROM local_sales_items
                    WHERE sales_invoice_id = ?
                    ORDER BY id
                    """,
                    (inv_id,),
                )
                item_rows = await items_cursor.fetchall()
                items = [self._row_to_sales_item(r) for r in item_rows]
                invoices.append(self._row_to_sales_invoice(row, items))

            return invoices

    @staticmethod
    def _row_to_sales_invoice(
        row: aiosqlite.Row, items: list[LocalSalesItem]
    ) -> LocalSalesInvoice:
        """Convert a database row to a LocalSalesInvoice entity."""
        sale_date = date.today()
        if row["sale_date"]:
            try:
                sale_date = date.fromisoformat(row["sale_date"])
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

        return LocalSalesInvoice(
            id=row["id"],
            invoice_number=row["invoice_number"],
            customer_name=row["customer_name"],
            sale_date=sale_date,
            subtotal=float(row["subtotal"]),
            tax_amount=float(row["tax_amount"]),
            total_amount=float(row["total_amount"]),
            total_cost=float(row["total_cost"]),
            total_profit=float(row["total_profit"]),
            notes=row["notes"],
            items=items,
            created_at=created_at,
            updated_at=updated_at,
        )

    @staticmethod
    def _row_to_sales_item(row: aiosqlite.Row) -> LocalSalesItem:
        """Convert a database row to a LocalSalesItem entity."""
        created_at = datetime.utcnow()
        if row["created_at"]:
            try:
                created_at = datetime.fromisoformat(row["created_at"])
            except (ValueError, TypeError):
                pass

        return LocalSalesItem(
            id=row["id"],
            sales_invoice_id=row["sales_invoice_id"],
            inventory_item_id=row["inventory_item_id"],
            material_id=row["material_id"],
            description=row["description"],
            quantity=float(row["quantity"]),
            unit_price=float(row["unit_price"]),
            cost_basis=float(row["cost_basis"]),
            line_total=float(row["line_total"]),
            profit=float(row["profit"]),
            created_at=created_at,
        )
