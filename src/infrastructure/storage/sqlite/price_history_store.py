"""
SQLite implementation of price history storage.

Reads from existing v002 tables (item_price_history, v_item_price_stats).
"""

from typing import Any

from src.config import get_logger
from src.core.interfaces.price_history import IPriceHistoryStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLitePriceHistoryStore(IPriceHistoryStore):
    """SQLite implementation of price history queries."""

    async def get_price_history(
        self,
        item_name: str | None = None,
        seller: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get price history entries with optional filters."""
        async with get_connection() as conn:
            conditions: list[str] = []
            params: list[Any] = []

            if item_name:
                conditions.append("item_name_normalized LIKE ?")
                params.append(f"%{item_name.strip().lower()}%")

            if seller:
                conditions.append("seller_name LIKE ?")
                params.append(f"%{seller}%")

            if date_from:
                conditions.append("invoice_date >= ?")
                params.append(date_from)

            if date_to:
                conditions.append("invoice_date <= ?")
                params.append(date_to)

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            params.append(limit)

            cursor = await conn.execute(
                f"""
                SELECT
                    item_name_normalized AS item_name,
                    hs_code,
                    seller_name,
                    invoice_date,
                    quantity,
                    unit_price,
                    currency
                FROM item_price_history
                {where_clause}
                ORDER BY invoice_date DESC
                LIMIT ?
                """,
                params,
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def get_price_stats(
        self,
        item_name: str | None = None,
        seller: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get price statistics from the stats view."""
        async with get_connection() as conn:
            conditions: list[str] = []
            params: list[Any] = []

            if item_name:
                conditions.append("item_name_normalized LIKE ?")
                params.append(f"%{item_name.strip().lower()}%")

            if seller:
                conditions.append("seller_name LIKE ?")
                params.append(f"%{seller}%")

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            cursor = await conn.execute(
                f"""
                SELECT
                    item_name_normalized AS item_name,
                    hs_code,
                    seller_name,
                    currency,
                    occurrence_count,
                    min_price,
                    max_price,
                    avg_price,
                    price_trend,
                    first_seen,
                    last_seen
                FROM v_item_price_stats
                {where_clause}
                ORDER BY occurrence_count DESC
                """,
                params,
            )
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def link_material(
        self, material_id: str, item_name_normalized: str
    ) -> int:
        """Link price history rows to a material. Returns rows updated."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                UPDATE item_price_history
                SET material_id = ?
                WHERE item_name_normalized = ?
                """,
                (material_id, item_name_normalized),
            )
            updated = cursor.rowcount
            logger.info(
                "price_history_linked",
                material_id=material_id,
                item_name=item_name_normalized,
                rows_updated=updated,
            )
            return updated
