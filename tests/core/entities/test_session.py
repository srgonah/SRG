"""Unit tests for session domain entities."""

from datetime import datetime, timedelta

from src.core.entities.session import (
    ChatSession,
    MemoryFact,
    MemoryFactType,
    Message,
    MessageRole,
    MessageType,
    SessionStatus,
)


class TestMessageRole:
    """Tests for MessageRole enum."""

    def test_all_roles_exist(self):
        expected = {"user", "assistant", "system"}
        actual = {r.value for r in MessageRole}
        assert actual == expected


class TestMessageType:
    """Tests for MessageType enum."""

    def test_all_types_exist(self):
        expected = {"text", "search_query", "search_result", "document_ref", "error"}
        actual = {t.value for t in MessageType}
        assert actual == expected


class TestMemoryFactType:
    """Tests for MemoryFactType enum."""

    def test_all_types_exist(self):
        expected = {
            "user_preference",
            "document_context",
            "entity",
            "relationship",
            "temporal",
        }
        actual = {t.value for t in MemoryFactType}
        assert actual == expected


class TestSessionStatus:
    """Tests for SessionStatus enum."""

    def test_all_statuses_exist(self):
        expected = {"active", "archived", "deleted"}
        actual = {s.value for s in SessionStatus}
        assert actual == expected


class TestMessage:
    """Tests for Message entity."""

    def test_required_fields(self):
        msg = Message(
            session_id="test-session-id",
            role=MessageRole.USER,
            content="Hello, world!",
        )
        assert msg.session_id == "test-session-id"
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello, world!"

    def test_default_values(self):
        msg = Message(
            session_id="test",
            role=MessageRole.USER,
            content="Test",
        )
        assert msg.id is None
        assert msg.message_type == MessageType.TEXT
        assert msg.search_query is None
        assert msg.search_results == []
        assert msg.sources == []
        assert msg.token_count == 0
        assert msg.metadata == {}

    def test_with_rag_context(self):
        msg = Message(
            session_id="test",
            role=MessageRole.ASSISTANT,
            content="Based on the search results...",
            search_query="test query",
            search_results=[{"doc_id": 1, "text": "Result"}],
            sources=["doc1.pdf", "doc2.pdf"],
        )
        assert msg.search_query == "test query"
        assert len(msg.search_results) == 1
        assert len(msg.sources) == 2

    def test_timestamp_auto_generated(self):
        before = datetime.utcnow()
        msg = Message(
            session_id="test",
            role=MessageRole.USER,
            content="Test",
        )
        after = datetime.utcnow()
        assert before <= msg.created_at <= after


class TestMemoryFact:
    """Tests for MemoryFact entity."""

    def test_required_fields(self):
        fact = MemoryFact(
            fact_type=MemoryFactType.USER_PREFERENCE,
            key="language",
            value="english",
        )
        assert fact.fact_type == MemoryFactType.USER_PREFERENCE
        assert fact.key == "language"
        assert fact.value == "english"

    def test_default_values(self):
        fact = MemoryFact(
            fact_type=MemoryFactType.ENTITY,
            key="test",
            value="value",
        )
        assert fact.id is None
        assert fact.session_id is None
        assert fact.confidence == 1.0
        assert fact.related_doc_ids == []
        assert fact.related_invoice_ids == []
        assert fact.access_count == 0
        assert fact.last_accessed is None
        assert fact.expires_at is None

    def test_with_relationships(self):
        fact = MemoryFact(
            fact_type=MemoryFactType.DOCUMENT_CONTEXT,
            key="vendor_preference",
            value="Test Vendor",
            related_doc_ids=[1, 2, 3],
            related_invoice_ids=[10, 20],
        )
        assert fact.related_doc_ids == [1, 2, 3]
        assert fact.related_invoice_ids == [10, 20]

    def test_with_expiration(self):
        expires = datetime.utcnow() + timedelta(days=30)
        fact = MemoryFact(
            fact_type=MemoryFactType.TEMPORAL,
            key="deadline",
            value="2024-02-15",
            expires_at=expires,
        )
        assert fact.expires_at == expires


class TestChatSession:
    """Tests for ChatSession entity."""

    def test_default_values(self):
        session = ChatSession()
        assert session.id is None
        assert session.session_id is not None
        assert len(session.session_id) == 36  # UUID format
        assert session.title is None
        assert session.status == SessionStatus.ACTIVE
        assert session.company_key is None
        assert session.active_doc_ids == []
        assert session.active_invoice_ids == []
        assert session.messages == []
        assert session.memory_facts == []
        assert session.conversation_summary is None
        assert session.summary_message_count == 0
        assert session.total_tokens == 0
        assert session.max_context_tokens == 8000
        assert session.system_prompt is None
        assert session.temperature == 0.7
        assert session.metadata == {}
        assert session.last_message_at is None

    def test_custom_session_id(self):
        session = ChatSession(session_id="custom-id-123")
        assert session.session_id == "custom-id-123"


class TestChatSessionAddMessage:
    """Tests for ChatSession.add_message method."""

    def test_add_message(self):
        session = ChatSession()
        msg = session.add_message(MessageRole.USER, "Hello!")
        assert len(session.messages) == 1
        assert msg.role == MessageRole.USER
        assert msg.content == "Hello!"
        assert msg.session_id == session.session_id

    def test_add_message_updates_timestamps(self):
        session = ChatSession()
        before = datetime.utcnow()
        msg = session.add_message(MessageRole.USER, "Test")
        assert session.last_message_at == msg.created_at
        assert session.updated_at == msg.created_at
        assert session.updated_at >= before

    def test_add_message_with_kwargs(self):
        session = ChatSession()
        msg = session.add_message(
            MessageRole.ASSISTANT,
            "Search results show...",
            search_query="test query",
            sources=["doc1.pdf"],
        )
        assert msg.search_query == "test query"
        assert msg.sources == ["doc1.pdf"]


class TestChatSessionGetContextMessages:
    """Tests for ChatSession.get_context_messages method."""

    def test_empty_session(self):
        session = ChatSession()
        context = session.get_context_messages()
        assert context == []

    def test_all_messages_fit(self):
        session = ChatSession()
        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content="Hi", token_count=10),
            Message(session_id=session.session_id, role=MessageRole.ASSISTANT, content="Hello!", token_count=15),
        ]
        context = session.get_context_messages(max_tokens=100)
        assert len(context) == 2

    def test_truncates_to_fit(self):
        session = ChatSession()
        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content="Old msg", token_count=50),
            Message(session_id=session.session_id, role=MessageRole.ASSISTANT, content="Old reply", token_count=50),
            Message(session_id=session.session_id, role=MessageRole.USER, content="Recent msg", token_count=30),
        ]
        context = session.get_context_messages(max_tokens=40)
        assert len(context) == 1
        assert context[0].content == "Recent msg"

    def test_preserves_order(self):
        session = ChatSession()
        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content="First", token_count=10),
            Message(session_id=session.session_id, role=MessageRole.ASSISTANT, content="Second", token_count=10),
            Message(session_id=session.session_id, role=MessageRole.USER, content="Third", token_count=10),
        ]
        context = session.get_context_messages(max_tokens=100)
        assert [m.content for m in context] == ["First", "Second", "Third"]


class TestChatSessionAddMemoryFact:
    """Tests for ChatSession.add_memory_fact method."""

    def test_add_new_fact(self):
        session = ChatSession()
        fact = session.add_memory_fact(
            MemoryFactType.USER_PREFERENCE,
            "language",
            "english",
        )
        assert len(session.memory_facts) == 1
        assert fact.key == "language"
        assert fact.value == "english"
        assert fact.session_id == session.session_id

    def test_update_existing_fact(self):
        session = ChatSession()
        _fact1 = session.add_memory_fact(
            MemoryFactType.USER_PREFERENCE,
            "language",
            "english",
        )
        fact2 = session.add_memory_fact(
            MemoryFactType.USER_PREFERENCE,
            "language",
            "arabic",
        )
        assert len(session.memory_facts) == 1  # Not duplicated
        assert fact2.value == "arabic"
        assert fact2.access_count == 1  # Incremented

    def test_add_fact_with_kwargs(self):
        session = ChatSession()
        fact = session.add_memory_fact(
            MemoryFactType.DOCUMENT_CONTEXT,
            "vendor",
            "Test Vendor",
            confidence=0.9,
            related_doc_ids=[1, 2],
        )
        assert fact.confidence == 0.9
        assert fact.related_doc_ids == [1, 2]


class TestChatSessionProperties:
    """Tests for ChatSession computed properties."""

    def test_message_count(self):
        session = ChatSession()
        assert session.message_count == 0

        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content="1"),
            Message(session_id=session.session_id, role=MessageRole.ASSISTANT, content="2"),
        ]
        assert session.message_count == 2

    def test_needs_summary_false_when_few_messages(self):
        session = ChatSession()
        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content=str(i))
            for i in range(15)
        ]
        assert session.needs_summary is False

    def test_needs_summary_true_when_many_new_messages(self):
        session = ChatSession()
        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content=str(i))
            for i in range(25)
        ]
        session.summary_message_count = 10  # Already summarized up to msg 10
        assert session.needs_summary is True  # 25 - 10 = 15 > 10

    def test_needs_summary_false_when_recently_summarized(self):
        session = ChatSession()
        session.messages = [
            Message(session_id=session.session_id, role=MessageRole.USER, content=str(i))
            for i in range(25)
        ]
        session.summary_message_count = 20  # Recently summarized
        assert session.needs_summary is False  # 25 - 20 = 5 < 10
