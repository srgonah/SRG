"""
FTS5 full-text search implementation.

Provides keyword-based search using SQLite FTS5.
"""

import re

from src.config import get_logger
from src.core.entities import SearchResult
from src.infrastructure.storage.sqlite.connection import get_connection

logger = get_logger(__name__)


def _expand_query(query: str) -> str:
    """
    Expand query with code variants for better matching.

    Handles:
    - Dotted codes: "85.36.20.00" -> "85362000"
    - Hyphenated codes: "85-36-20-00" -> "85362000"
    """
    tokens = re.findall(r"[A-Za-z0-9._-]+", query.lower())
    extras = []

    for token in tokens:
        if "." in token or "-" in token:
            # Remove separators
            stripped = token.replace(".", "").replace("-", "")
            if stripped:
                extras.append(stripped)

            # Split into parts
            parts = re.split(r"[.-]+", token)
            extras.extend([p for p in parts if p])

    all_parts = [query] + extras
    return " ".join(all_parts)


class FTSSearcher:
    """
    FTS5-based full-text searcher.

    Provides keyword search over chunks and items using SQLite FTS5.
    """

    async def search_chunks(
        self,
        query: str,
        limit: int = 60,
    ) -> list[SearchResult]:
        """
        Search document chunks using FTS5.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of SearchResult with FTS scores
        """
        fts_query = _expand_query(query)

        async with get_connection() as conn:
            try:
                cursor = await conn.execute(
                    """
                    SELECT
                        c.id,
                        c.doc_id,
                        c.chunk_text,
                        c.metadata_json,
                        p.page_no,
                        p.page_type,
                        bm25(doc_chunks_fts) as score
                    FROM doc_chunks_fts fts
                    INNER JOIN doc_chunks c ON fts.rowid = c.id
                    LEFT JOIN doc_pages p ON c.page_id = p.id
                    WHERE doc_chunks_fts MATCH ?
                    ORDER BY bm25(doc_chunks_fts)
                    LIMIT ?
                    """,
                    (fts_query, limit),
                )

                rows = await cursor.fetchall()

                results = []
                for rank, row in enumerate(rows):
                    results.append(
                        SearchResult(
                            chunk_id=row["id"],
                            doc_id=row["doc_id"],
                            text=row["chunk_text"] or "",
                            fts_score=abs(row["score"]),  # BM25 returns negative scores
                            final_rank=rank,
                            page_no=row["page_no"],
                            page_type=row["page_type"],
                        )
                    )

                return results

            except Exception as e:
                logger.warning("fts_search_failed", error=str(e), query=query[:50])
                return []

    async def search_items(
        self,
        query: str,
        limit: int = 60,
    ) -> list[SearchResult]:
        """
        Search invoice items using FTS5.

        Args:
            query: Search query
            limit: Maximum results

        Returns:
            List of SearchResult with FTS scores
        """
        fts_query = _expand_query(query)

        async with get_connection() as conn:
            try:
                cursor = await conn.execute(
                    """
                    SELECT
                        ii.id,
                        ii.item_name,
                        ii.hs_code,
                        ii.quantity,
                        ii.unit_price,
                        ii.total_price,
                        inv.invoice_no,
                        inv.invoice_date,
                        inv.seller_name,
                        bm25(invoice_items_fts) as score
                    FROM invoice_items_fts fts
                    INNER JOIN invoice_items ii ON fts.rowid = ii.id
                    LEFT JOIN invoices inv ON ii.invoice_id = inv.id AND inv.is_latest = 1
                    WHERE invoice_items_fts MATCH ?
                    ORDER BY bm25(invoice_items_fts)
                    LIMIT ?
                    """,
                    (fts_query, limit),
                )

                rows = await cursor.fetchall()

                results = []
                for rank, row in enumerate(rows):
                    results.append(
                        SearchResult(
                            item_id=row["id"],
                            item_name=row["item_name"],
                            text=row["item_name"] or "",
                            fts_score=abs(row["score"]),
                            final_rank=rank,
                            hs_code=row["hs_code"],
                            quantity=row["quantity"],
                            unit_price=row["unit_price"],
                            total_price=row["total_price"],
                            invoice_no=row["invoice_no"],
                            invoice_date=row["invoice_date"],
                            seller_name=row["seller_name"],
                        )
                    )

                return results

            except Exception as e:
                logger.warning("fts_search_failed", error=str(e), query=query[:50])
                return []


# Singleton
_fts_searcher: FTSSearcher | None = None


def get_fts_searcher() -> FTSSearcher:
    """Get or create FTS searcher singleton."""
    global _fts_searcher
    if _fts_searcher is None:
        _fts_searcher = FTSSearcher()
    return _fts_searcher
