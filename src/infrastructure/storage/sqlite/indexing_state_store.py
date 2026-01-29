"""SQLite implementation of indexing state store."""

from datetime import datetime

from src.core.entities.document import IndexingState
from src.core.interfaces.storage import IIndexingStateStore
from src.infrastructure.storage.sqlite.connection import get_connection


class SQLiteIndexingStateStore(IIndexingStateStore):
    """SQLite-based indexing state storage."""

    async def get_state(self, index_name: str) -> IndexingState | None:
        """Get current indexing state for an index."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT id, index_name, last_doc_id, last_chunk_id, last_item_id,
                       total_indexed, pending_count, is_building, last_error, last_run_at
                FROM indexing_state
                WHERE index_name = ?
                """,
                (index_name,),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            return IndexingState(
                id=row[0],
                index_name=row[1],
                last_doc_id=row[2] or 0,
                last_chunk_id=row[3] or 0,
                last_item_id=row[4] or 0,
                total_indexed=row[5] or 0,
                pending_count=row[6] or 0,
                is_building=bool(row[7]),
                last_error=row[8],
                last_run_at=datetime.fromisoformat(row[9]) if row[9] else None,
            )

    async def update_state(self, state: IndexingState) -> IndexingState:
        """Update indexing state."""
        async with get_connection() as conn:
            now = datetime.utcnow().isoformat()
            await conn.execute(
                """
                UPDATE indexing_state
                SET last_doc_id = ?,
                    last_chunk_id = ?,
                    last_item_id = ?,
                    total_indexed = ?,
                    pending_count = ?,
                    is_building = ?,
                    last_error = ?,
                    last_run_at = ?,
                    updated_at = ?
                WHERE index_name = ?
                """,
                (
                    state.last_doc_id,
                    state.last_chunk_id,
                    state.last_item_id,
                    state.total_indexed,
                    state.pending_count,
                    1 if state.is_building else 0,
                    state.last_error,
                    state.last_run_at.isoformat() if state.last_run_at else now,
                    now,
                    state.index_name,
                ),
            )
            await conn.commit()
            return state

    async def reset_state(self, index_name: str) -> bool:
        """Reset indexing state for full rebuild."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                UPDATE indexing_state
                SET last_doc_id = 0,
                    last_chunk_id = 0,
                    last_item_id = 0,
                    total_indexed = 0,
                    pending_count = 0,
                    is_building = 0,
                    last_error = NULL,
                    updated_at = datetime('now')
                WHERE index_name = ?
                """,
                (index_name,),
            )
            await conn.commit()
            return cursor.rowcount > 0
