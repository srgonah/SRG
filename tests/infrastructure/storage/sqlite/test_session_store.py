"""Unit tests for SQLiteSessionStore."""

from unittest.mock import patch

import pytest

from src.core.entities import (
    ChatSession,
    MemoryFact,
    MemoryFactType,
    Message,
    MessageRole,
    MessageType,
    SessionStatus,
)
from src.infrastructure.storage.sqlite.session_store import SQLiteSessionStore


class TestSQLiteSessionStoreCreateSession:
    """Tests for SQLiteSessionStore.create_session()."""

    @pytest.mark.asyncio
    async def test_create_session_returns_session_with_id(
        self, initialized_db, sample_session, mock_settings
    ):
        """create_session() assigns ID to session."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            result = await store.create_session(sample_session)

            assert result.id is not None
            assert result.id > 0
            assert result.session_id == sample_session.session_id

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_create_session_persists_all_fields(
        self, initialized_db, sample_session, mock_settings
    ):
        """create_session() persists all session fields."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            # Retrieve and verify
            retrieved = await store.get_session(created.session_id)
            assert retrieved is not None
            assert retrieved.title == sample_session.title
            assert retrieved.status == sample_session.status
            assert retrieved.company_key == sample_session.company_key
            assert retrieved.active_doc_ids == sample_session.active_doc_ids
            assert retrieved.active_invoice_ids == sample_session.active_invoice_ids
            assert retrieved.total_tokens == sample_session.total_tokens
            assert retrieved.temperature == sample_session.temperature

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreGetSession:
    """Tests for SQLiteSessionStore.get_session()."""

    @pytest.mark.asyncio
    async def test_get_session_returns_session(
        self, initialized_db, sample_session, mock_settings
    ):
        """get_session() returns session by session_id."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            result = await store.get_session(created.session_id)
            assert result is not None
            assert result.session_id == created.session_id

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_session_returns_none_for_missing(
        self, initialized_db, mock_settings
    ):
        """get_session() returns None for non-existent session_id."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            result = await store.get_session("nonexistent-session-id")

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_session_loads_messages(
        self, initialized_db, sample_session, sample_message, mock_settings
    ):
        """get_session() loads associated messages."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            # Add messages
            sample_message.session_id = created.session_id
            await store.add_message(sample_message)

            # Retrieve and verify messages loaded
            result = await store.get_session(created.session_id)
            assert len(result.messages) == 1
            assert result.messages[0].content == sample_message.content

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_session_loads_memory_facts(
        self, initialized_db, sample_session, sample_memory_fact, mock_settings
    ):
        """get_session() loads associated memory facts."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            # Add memory fact
            sample_memory_fact.session_id = created.session_id
            await store.save_memory_fact(sample_memory_fact)

            # Retrieve and verify facts loaded
            result = await store.get_session(created.session_id)
            assert len(result.memory_facts) == 1
            assert result.memory_facts[0].key == sample_memory_fact.key

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreUpdateSession:
    """Tests for SQLiteSessionStore.update_session()."""

    @pytest.mark.asyncio
    async def test_update_session_modifies_fields(
        self, initialized_db, sample_session, mock_settings
    ):
        """update_session() modifies session fields."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            # Modify
            created.title = "Updated Title"
            created.status = SessionStatus.ARCHIVED
            created.total_tokens = 2000

            await store.update_session(created)

            # Verify
            result = await store.get_session(created.session_id)
            assert result.title == "Updated Title"
            assert result.status == SessionStatus.ARCHIVED
            assert result.total_tokens == 2000

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_update_session_updates_timestamp(
        self, initialized_db, sample_session, mock_settings
    ):
        """update_session() updates the updated_at timestamp."""
        import asyncio

        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)
            original_updated = created.updated_at

            await asyncio.sleep(0.01)

            created.title = "Modified"
            updated = await store.update_session(created)

            assert updated.updated_at > original_updated

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreSaveSession:
    """Tests for SQLiteSessionStore.save_session()."""

    @pytest.mark.asyncio
    async def test_save_session_creates_if_not_exists(
        self, initialized_db, sample_session, mock_settings
    ):
        """save_session() creates new session if not exists."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            result = await store.save_session(sample_session)

            assert result.id is not None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_save_session_updates_if_exists(
        self, initialized_db, sample_session, mock_settings
    ):
        """save_session() updates existing session."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()

            # Create first
            created = await store.create_session(sample_session)

            # Modify and save
            created.title = "Saved Title"
            await store.save_session(created)

            # Verify update
            result = await store.get_session(created.session_id)
            assert result.title == "Saved Title"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreDeleteSession:
    """Tests for SQLiteSessionStore.delete_session()."""

    @pytest.mark.asyncio
    async def test_delete_session_returns_true(
        self, initialized_db, sample_session, mock_settings
    ):
        """delete_session() returns True on success."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            result = await store.delete_session(created.session_id)
            assert result is True

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_session_removes_session(
        self, initialized_db, sample_session, mock_settings
    ):
        """delete_session() removes session from database."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            created = await store.create_session(sample_session)

            await store.delete_session(created.session_id)
            result = await store.get_session(created.session_id)

            assert result is None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_session_returns_false_for_missing(
        self, initialized_db, mock_settings
    ):
        """delete_session() returns False for non-existent session."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            result = await store.delete_session("nonexistent-id")

            assert result is False

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreListSessions:
    """Tests for SQLiteSessionStore.list_sessions()."""

    @pytest.mark.asyncio
    async def test_list_sessions_returns_list(
        self, initialized_db, sample_session, mock_settings
    ):
        """list_sessions() returns list of sessions."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            await store.create_session(sample_session)

            result = await store.list_sessions()
            assert isinstance(result, list)
            assert len(result) >= 1

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_list_sessions_respects_limit(
        self, initialized_db, mock_settings
    ):
        """list_sessions() respects limit parameter."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()

            # Create multiple sessions
            for i in range(5):
                session = ChatSession(
                    session_id=f"sess-{i}",
                    title=f"Session {i}",
                )
                await store.create_session(session)

            result = await store.list_sessions(limit=3)
            assert len(result) == 3

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_list_sessions_filters_by_status(
        self, initialized_db, mock_settings
    ):
        """list_sessions() filters by status."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()

            # Create sessions with different statuses
            from uuid import uuid4
            for i, status in enumerate([SessionStatus.ACTIVE, SessionStatus.ARCHIVED, SessionStatus.ACTIVE]):
                session = ChatSession(
                    session_id=f"sess-{status.value}-{i}-{uuid4().hex[:8]}",
                    status=status,
                )
                await store.create_session(session)

            result = await store.list_sessions(status="active")
            assert all(s.status == SessionStatus.ACTIVE for s in result)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreMessageOperations:
    """Tests for message operations."""

    @pytest.mark.asyncio
    async def test_add_message_returns_message_with_id(
        self, initialized_db, sample_session, sample_message, mock_settings
    ):
        """add_message() assigns ID to message."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            sample_message.session_id = session.session_id
            result = await store.add_message(sample_message)

            assert result.id is not None
            assert result.id > 0

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_add_message_updates_session_last_message_at(
        self, initialized_db, sample_session, sample_message, mock_settings
    ):
        """add_message() updates session's last_message_at."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            sample_message.session_id = session.session_id
            await store.add_message(sample_message)

            # Verify session was updated
            updated_session = await store.get_session(session.session_id)
            assert updated_session.last_message_at is not None

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_messages_returns_messages(
        self, initialized_db, sample_session, mock_settings
    ):
        """get_messages() returns messages for session."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            # Add multiple messages
            for i in range(3):
                msg = Message(
                    session_id=session.session_id,
                    role=MessageRole.USER,
                    content=f"Message {i}",
                )
                await store.add_message(msg)

            result = await store.get_messages(session.session_id)
            assert len(result) == 3

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_messages_returns_chronological_order(
        self, initialized_db, sample_session, mock_settings
    ):
        """get_messages() returns messages in chronological order."""
        import asyncio

        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            # Add messages with slight delays
            for i in range(3):
                msg = Message(
                    session_id=session.session_id,
                    role=MessageRole.USER,
                    content=f"Message {i}",
                )
                await store.add_message(msg)
                await asyncio.sleep(0.01)

            result = await store.get_messages(session.session_id)

            # Should be in chronological order
            assert result[0].content == "Message 0"
            assert result[1].content == "Message 1"
            assert result[2].content == "Message 2"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_messages_respects_limit(
        self, initialized_db, sample_session, mock_settings
    ):
        """get_messages() respects limit parameter."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            # Add many messages
            for i in range(10):
                msg = Message(
                    session_id=session.session_id,
                    role=MessageRole.USER,
                    content=f"Message {i}",
                )
                await store.add_message(msg)

            result = await store.get_messages(session.session_id, limit=5)
            assert len(result) == 5

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreMemoryFactOperations:
    """Tests for memory fact operations."""

    @pytest.mark.asyncio
    async def test_save_memory_fact_creates_new(
        self, initialized_db, sample_session, sample_memory_fact, mock_settings
    ):
        """save_memory_fact() creates new fact."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            sample_memory_fact.session_id = session.session_id
            result = await store.save_memory_fact(sample_memory_fact)

            assert result.id is not None
            assert result.id > 0

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_save_memory_fact_updates_existing(
        self, initialized_db, sample_session, sample_memory_fact, mock_settings
    ):
        """save_memory_fact() updates existing fact."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            sample_memory_fact.session_id = session.session_id
            created = await store.save_memory_fact(sample_memory_fact)

            # Modify and save
            created.value = "EUR"
            created.confidence = 0.8
            await store.save_memory_fact(created)

            # Verify update
            facts = await store.get_memory_facts(session_id=session.session_id)
            assert len(facts) == 1
            assert facts[0].value == "EUR"
            assert facts[0].confidence == 0.8

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_memory_facts_filters_by_session(
        self, initialized_db, mock_settings
    ):
        """get_memory_facts() filters by session_id."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()

            # Create two sessions
            session1 = ChatSession(session_id="sess-1")
            session2 = ChatSession(session_id="sess-2")
            await store.create_session(session1)
            await store.create_session(session2)

            # Add facts to each
            await store.save_memory_fact(MemoryFact(
                session_id="sess-1",
                fact_type=MemoryFactType.USER_PREFERENCE,
                key="key1",
                value="value1",
            ))
            await store.save_memory_fact(MemoryFact(
                session_id="sess-2",
                fact_type=MemoryFactType.USER_PREFERENCE,
                key="key2",
                value="value2",
            ))

            # Filter by session
            result = await store.get_memory_facts(session_id="sess-1")
            assert len(result) == 1
            assert result[0].key == "key1"

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_get_memory_facts_filters_by_type(
        self, initialized_db, sample_session, mock_settings
    ):
        """get_memory_facts() filters by fact_type."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            # Add facts with different types
            await store.save_memory_fact(MemoryFact(
                session_id=session.session_id,
                fact_type=MemoryFactType.USER_PREFERENCE,
                key="pref",
                value="val",
            ))
            await store.save_memory_fact(MemoryFact(
                session_id=session.session_id,
                fact_type=MemoryFactType.DOCUMENT_CONTEXT,
                key="ctx",
                value="val",
            ))

            # Filter by type
            result = await store.get_memory_facts(fact_type="preference")
            assert all(f.fact_type == MemoryFactType.USER_PREFERENCE for f in result)

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_memory_fact_returns_true(
        self, initialized_db, sample_session, sample_memory_fact, mock_settings
    ):
        """delete_memory_fact() returns True on success."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            sample_memory_fact.session_id = session.session_id
            created = await store.save_memory_fact(sample_memory_fact)

            result = await store.delete_memory_fact(created.id)
            assert result is True

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_memory_fact_removes_fact(
        self, initialized_db, sample_session, sample_memory_fact, mock_settings
    ):
        """delete_memory_fact() removes fact from database."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            sample_memory_fact.session_id = session.session_id
            created = await store.save_memory_fact(sample_memory_fact)

            await store.delete_memory_fact(created.id)

            facts = await store.get_memory_facts(session_id=session.session_id)
            assert len(facts) == 0

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_delete_memory_fact_returns_false_for_missing(
        self, initialized_db, mock_settings
    ):
        """delete_memory_fact() returns False for non-existent ID."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            result = await store.delete_memory_fact(99999)

            assert result is False

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()


class TestSQLiteSessionStoreRowConversion:
    """Tests for row-to-entity conversion methods."""

    @pytest.mark.asyncio
    async def test_row_to_session_converts_json_arrays(
        self, initialized_db, sample_session, mock_settings
    ):
        """_row_to_session() parses JSON arrays."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            sample_session.active_doc_ids = [1, 2, 3]
            sample_session.active_invoice_ids = [10, 20]
            created = await store.create_session(sample_session)

            result = await store.get_session(created.session_id)
            assert result.active_doc_ids == [1, 2, 3]
            assert result.active_invoice_ids == [10, 20]

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_row_to_message_converts_enums(
        self, initialized_db, sample_session, mock_settings
    ):
        """_row_to_message() converts role and type enums."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            msg = Message(
                session_id=session.session_id,
                role=MessageRole.ASSISTANT,
                content="Test",
                message_type=MessageType.SEARCH_QUERY,
            )
            await store.add_message(msg)

            messages = await store.get_messages(session.session_id)
            assert isinstance(messages[0].role, MessageRole)
            assert messages[0].role == MessageRole.ASSISTANT
            assert isinstance(messages[0].message_type, MessageType)
            assert messages[0].message_type == MessageType.SEARCH_QUERY

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()

    @pytest.mark.asyncio
    async def test_row_to_fact_converts_enums(
        self, initialized_db, sample_session, mock_settings
    ):
        """_row_to_fact() converts fact_type enum."""
        import src.infrastructure.storage.sqlite.connection as conn_module

        conn_module._pool = None
        mock_settings.storage.db_path = initialized_db

        with patch.object(conn_module, "get_settings", return_value=mock_settings):
            store = SQLiteSessionStore()
            session = await store.create_session(sample_session)

            fact = MemoryFact(
                session_id=session.session_id,
                fact_type=MemoryFactType.ENTITY,
                key="test",
                value="value",
            )
            await store.save_memory_fact(fact)

            facts = await store.get_memory_facts(session_id=session.session_id)
            assert isinstance(facts[0].fact_type, MemoryFactType)
            assert facts[0].fact_type == MemoryFactType.ENTITY

            from src.infrastructure.storage.sqlite.connection import close_pool

            await close_pool()
