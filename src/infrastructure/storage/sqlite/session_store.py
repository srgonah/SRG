"""
SQLite implementation of session storage.

Handles chat sessions, messages, and memory facts.
"""

import json
from datetime import datetime

import aiosqlite

from src.config import get_logger
from src.core.entities import (
    ChatSession,
    MemoryFact,
    MemoryFactType,
    Message,
    MessageRole,
    MessageType,
    SessionStatus,
)
from src.core.interfaces import ISessionStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


class SQLiteSessionStore(ISessionStore):
    """SQLite implementation of session storage."""

    async def create_session(self, session: ChatSession) -> ChatSession:
        """Create a new chat session."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO chat_sessions (
                    session_id, title, status, company_key,
                    active_doc_ids_json, active_invoice_ids_json,
                    conversation_summary, summary_message_count,
                    total_tokens, max_context_tokens, system_prompt,
                    temperature, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.title,
                    session.status.value,
                    session.company_key,
                    json.dumps(session.active_doc_ids),
                    json.dumps(session.active_invoice_ids),
                    session.conversation_summary,
                    session.summary_message_count,
                    session.total_tokens,
                    session.max_context_tokens,
                    session.system_prompt,
                    session.temperature,
                    session.created_at.isoformat(),
                    session.updated_at.isoformat(),
                ),
            )
            session.id = cursor.lastrowid
            logger.info("session_created", session_id=session.session_id)
            return session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get session by ID with messages."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            session = self._row_to_session(row)

            # Load messages
            msg_cursor = await conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at
                """,
                (session_id,),
            )
            msg_rows = await msg_cursor.fetchall()
            session.messages = [self._row_to_message(r) for r in msg_rows]

            # Load memory facts
            fact_cursor = await conn.execute(
                "SELECT * FROM memory_facts WHERE session_id = ?",
                (session_id,),
            )
            fact_rows = await fact_cursor.fetchall()
            session.memory_facts = [self._row_to_fact(r) for r in fact_rows]

            return session

    async def update_session(self, session: ChatSession) -> ChatSession:
        """Update session metadata."""
        session.updated_at = datetime.utcnow()
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE chat_sessions SET
                    title = ?, status = ?, company_key = ?,
                    active_doc_ids_json = ?, active_invoice_ids_json = ?,
                    conversation_summary = ?, summary_message_count = ?,
                    total_tokens = ?, system_prompt = ?, temperature = ?,
                    updated_at = ?, last_message_at = ?
                WHERE session_id = ?
                """,
                (
                    session.title,
                    session.status.value,
                    session.company_key,
                    json.dumps(session.active_doc_ids),
                    json.dumps(session.active_invoice_ids),
                    session.conversation_summary,
                    session.summary_message_count,
                    session.total_tokens,
                    session.system_prompt,
                    session.temperature,
                    session.updated_at.isoformat(),
                    session.last_message_at.isoformat() if session.last_message_at else None,
                    session.session_id,
                ),
            )
            return session

    async def save_session(self, session: ChatSession) -> ChatSession:
        """Save session (create if new, update if exists)."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT id FROM chat_sessions WHERE session_id = ?",
                (session.session_id,),
            )
            exists = await cursor.fetchone() is not None

        if exists:
            return await self.update_session(session)
        else:
            return await self.create_session(session)

    async def delete_session(self, session_id: str) -> bool:
        """Delete session and messages."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                "SELECT id FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            )
            if await cursor.fetchone() is None:
                return False

            await conn.execute(
                "DELETE FROM chat_sessions WHERE session_id = ?",
                (session_id,),
            )
            logger.info("session_deleted", session_id=session_id)
            return True

    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[ChatSession]:
        """List sessions with pagination."""
        async with get_connection() as conn:
            if status:
                cursor = await conn.execute(
                    """
                    SELECT * FROM chat_sessions
                    WHERE status = ?
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (status, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM chat_sessions
                    ORDER BY updated_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = await cursor.fetchall()
            return [self._row_to_session(row) for row in rows]

    # Message operations

    async def add_message(self, message: Message) -> Message:
        """Add message to session."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                """
                INSERT INTO chat_messages (
                    session_id, role, content, message_type,
                    search_query, search_results_json, sources_json,
                    token_count, metadata_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.session_id,
                    message.role.value,
                    message.content,
                    message.message_type.value,
                    message.search_query,
                    json.dumps(message.search_results),
                    json.dumps(message.sources),
                    message.token_count,
                    json.dumps(message.metadata),
                    message.created_at.isoformat(),
                ),
            )
            message.id = cursor.lastrowid

            # Update session last_message_at
            await conn.execute(
                """
                UPDATE chat_sessions
                SET last_message_at = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (message.created_at.isoformat(), datetime.utcnow().isoformat(), message.session_id),
            )

            return message

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for session."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT * FROM chat_messages
                WHERE session_id = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (session_id, limit, offset),
            )
            rows = await cursor.fetchall()
            # Reverse to get chronological order
            return [self._row_to_message(row) for row in reversed(list(rows))]

    # Memory operations

    async def save_memory_fact(self, fact: MemoryFact) -> MemoryFact:
        """Save or update memory fact."""
        async with get_transaction() as conn:
            if fact.id:
                # Update existing
                fact.updated_at = datetime.utcnow()
                await conn.execute(
                    """
                    UPDATE memory_facts SET
                        value = ?, confidence = ?, access_count = ?,
                        last_accessed = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        fact.value,
                        fact.confidence,
                        fact.access_count,
                        fact.last_accessed.isoformat() if fact.last_accessed else None,
                        fact.updated_at.isoformat(),
                        fact.id,
                    ),
                )
            else:
                # Insert new
                cursor = await conn.execute(
                    """
                    INSERT INTO memory_facts (
                        session_id, fact_type, key, value, confidence,
                        related_doc_ids_json, related_invoice_ids_json,
                        access_count, created_at, updated_at, expires_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        fact.session_id,
                        fact.fact_type.value,
                        fact.key,
                        fact.value,
                        fact.confidence,
                        json.dumps(fact.related_doc_ids),
                        json.dumps(fact.related_invoice_ids),
                        fact.access_count,
                        fact.created_at.isoformat(),
                        fact.updated_at.isoformat(),
                        fact.expires_at.isoformat() if fact.expires_at else None,
                    ),
                )
                fact.id = cursor.lastrowid

            return fact

    async def get_memory_facts(
        self,
        session_id: str | None = None,
        fact_type: str | None = None,
    ) -> list[MemoryFact]:
        """Get memory facts, optionally filtered."""
        async with get_connection() as conn:
            conditions = []
            params = []

            if session_id:
                conditions.append("session_id = ?")
                params.append(session_id)
            if fact_type:
                conditions.append("fact_type = ?")
                params.append(fact_type)

            where = " AND ".join(conditions) if conditions else "1=1"

            cursor = await conn.execute(
                f"""
                SELECT * FROM memory_facts
                WHERE {where}
                ORDER BY updated_at DESC
                """,
                params,
            )
            rows = await cursor.fetchall()
            return [self._row_to_fact(row) for row in rows]

    async def delete_memory_fact(self, fact_id: int) -> bool:
        """Delete a memory fact."""
        async with get_transaction() as conn:
            cursor = await conn.execute("SELECT id FROM memory_facts WHERE id = ?", (fact_id,))
            if await cursor.fetchone() is None:
                return False

            await conn.execute("DELETE FROM memory_facts WHERE id = ?", (fact_id,))
            return True

    # Conversion helpers

    def _row_to_session(self, row: aiosqlite.Row) -> ChatSession:
        """Convert database row to ChatSession entity."""
        return ChatSession(
            id=row["id"],
            session_id=row["session_id"],
            title=row["title"],
            status=SessionStatus(row["status"]),
            company_key=row["company_key"],
            active_doc_ids=json.loads(row["active_doc_ids_json"])
            if row["active_doc_ids_json"]
            else [],
            active_invoice_ids=json.loads(row["active_invoice_ids_json"])
            if row["active_invoice_ids_json"]
            else [],
            conversation_summary=row["conversation_summary"],
            summary_message_count=row["summary_message_count"],
            total_tokens=row["total_tokens"],
            max_context_tokens=row["max_context_tokens"],
            system_prompt=row["system_prompt"],
            temperature=row["temperature"],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            last_message_at=datetime.fromisoformat(row["last_message_at"])
            if row["last_message_at"]
            else None,
        )

    def _row_to_message(self, row: aiosqlite.Row) -> Message:
        """Convert database row to Message entity."""
        return Message(
            id=row["id"],
            session_id=row["session_id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            message_type=MessageType(row["message_type"]),
            search_query=row["search_query"],
            search_results=json.loads(row["search_results_json"])
            if row["search_results_json"]
            else [],
            sources=json.loads(row["sources_json"]) if row["sources_json"] else [],
            token_count=row["token_count"],
            metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def _row_to_fact(self, row: aiosqlite.Row) -> MemoryFact:
        """Convert database row to MemoryFact entity."""
        return MemoryFact(
            id=row["id"],
            session_id=row["session_id"],
            fact_type=MemoryFactType(row["fact_type"]),
            key=row["key"],
            value=row["value"],
            confidence=row["confidence"],
            related_doc_ids=json.loads(row["related_doc_ids_json"])
            if row["related_doc_ids_json"]
            else [],
            related_invoice_ids=json.loads(row["related_invoice_ids_json"])
            if row["related_invoice_ids_json"]
            else [],
            access_count=row["access_count"],
            last_accessed=datetime.fromisoformat(row["last_accessed"])
            if row["last_accessed"]
            else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
        )
