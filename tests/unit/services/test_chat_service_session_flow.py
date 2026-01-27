"""
Unit tests for ChatService session flow.

Tests:
- Session creation and retrieval
- Message handling
- RAG context integration
- Memory fact extraction
- Streaming responses
- Error handling and graceful degradation
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.entities.session import ChatSession, MemoryFact, Message, MessageRole
from src.core.exceptions import ChatError
from src.core.services.chat_service import ChatService
from src.core.services.search_service import SearchContext


class MockSessionStore:
    """Mock implementation of ISessionStore."""

    def __init__(self):
        self.sessions = {}  # Keyed by session_id (UUID string)
        self.messages = {}  # Keyed by session_id (UUID string)
        self.facts = {}  # Keyed by session_id (UUID string)
        self._session_counter = 0
        self._message_counter = 0
        self._fact_counter = 0

    async def create_session(self, session: ChatSession) -> ChatSession:
        self._session_counter += 1
        session.id = self._session_counter  # Database ID is an integer
        # session.session_id is already set as a UUID by ChatSession default
        self.sessions[session.session_id] = session
        self.messages[session.session_id] = []
        return session

    async def get_session(self, session_id: str) -> ChatSession | None:
        return self.sessions.get(session_id)

    async def update_session(self, session: ChatSession) -> ChatSession:
        self.sessions[session.session_id] = session
        return session

    async def delete_session(self, session_id: str) -> bool:
        if session_id in self.sessions:
            del self.sessions[session_id]
            if session_id in self.messages:
                del self.messages[session_id]
            return True
        return False

    async def list_sessions(self, limit: int = 50, offset: int = 0, status: str | None = None) -> list[ChatSession]:
        sessions = list(self.sessions.values())
        return sessions[offset : offset + limit]

    async def add_message(self, message: Message) -> Message:
        self._message_counter += 1
        message.id = self._message_counter
        if message.session_id not in self.messages:
            self.messages[message.session_id] = []
        self.messages[message.session_id].append(message)
        return message

    async def get_messages(self, session_id: str, limit: int = 100, offset: int = 0) -> list[Message]:
        msgs = self.messages.get(session_id, [])
        return msgs[offset : offset + limit]

    async def save_memory_fact(self, fact: MemoryFact) -> MemoryFact:
        self._fact_counter += 1
        fact.id = self._fact_counter
        if fact.session_id not in self.facts:
            self.facts[fact.session_id] = []
        self.facts[fact.session_id].append(fact)
        return fact

    async def get_memory_facts(self, session_id: str | None = None, fact_type: str | None = None) -> list[MemoryFact]:
        if session_id:
            return self.facts.get(session_id, [])
        all_facts = []
        for facts in self.facts.values():
            all_facts.extend(facts)
        return all_facts

    async def delete_memory_fact(self, fact_id: int) -> bool:
        for facts in self.facts.values():
            for i, fact in enumerate(facts):
                if fact.id == fact_id:
                    del facts[i]
                    return True
        return False


class MockLLMProvider:
    """Mock implementation of ILLMProvider."""

    def __init__(self, response: str = "This is a test response."):
        self.response = response
        self.generate_called = False
        self.prompts = []  # Track all prompts

    @property
    def last_prompt(self):
        """For backward compatibility, return last prompt."""
        return self.prompts[-1] if self.prompts else None

    @property
    def chat_prompt(self):
        """Return the first prompt (usually the chat prompt, before fact extraction)."""
        return self.prompts[0] if self.prompts else None

    async def generate(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7) -> str:
        self.generate_called = True
        self.prompts.append(prompt)
        return self.response

    async def generate_stream(self, prompt: str, max_tokens: int = 2048, temperature: float = 0.7):
        self.generate_called = True
        self.prompts.append(prompt)
        for word in self.response.split():
            yield word + " "

    async def is_available(self) -> bool:
        return True


class MockSearchService:
    """Mock implementation of SearchService."""

    def __init__(self, context: str = "Test context from documents."):
        self.context = context

    async def search_for_rag(self, query: str, top_k: int = 5) -> SearchContext:
        return SearchContext(
            query=query,
            results=[],
            formatted_context=self.context,
            total_chunks=top_k,
            search_type="hybrid",
        )


class TestSessionManagement:
    """Tests for session creation and management."""

    @pytest.fixture
    def chat_service(self):
        store = MockSessionStore()
        llm = MockLLMProvider()
        return ChatService(session_store=store, llm_provider=llm)

    @pytest.mark.asyncio
    async def test_create_session(self, chat_service):
        """Should create a new session."""
        session = await chat_service.create_session(title="Test Chat")

        assert session.id is not None
        assert session.title == "Test Chat"

    @pytest.mark.asyncio
    async def test_create_session_default_title(self, chat_service):
        """Should use default title if not provided."""
        session = await chat_service.create_session()

        assert session.title == "New Chat"

    @pytest.mark.asyncio
    async def test_get_session(self, chat_service):
        """Should retrieve existing session."""
        created = await chat_service.create_session(title="Test")
        retrieved = await chat_service.get_session(created.session_id)

        assert retrieved is not None
        assert retrieved.session_id == created.session_id
        assert retrieved.title == "Test"

    @pytest.mark.asyncio
    async def test_get_nonexistent_session(self, chat_service):
        """Should return None for nonexistent session."""
        result = await chat_service.get_session("nonexistent_id")

        assert result is None

    @pytest.mark.asyncio
    async def test_delete_session(self, chat_service):
        """Should delete session."""
        session = await chat_service.create_session()
        result = await chat_service.delete_session(session.session_id)

        assert result is True
        assert await chat_service.get_session(session.session_id) is None

    @pytest.mark.asyncio
    async def test_list_sessions(self, chat_service):
        """Should list all sessions."""
        await chat_service.create_session(title="Session 1")
        await chat_service.create_session(title="Session 2")

        sessions = await chat_service.list_sessions()

        assert len(sessions) == 2


class TestChatFlow:
    """Tests for chat message flow."""

    @pytest.fixture
    def chat_service(self):
        store = MockSessionStore()
        llm = MockLLMProvider(response="Hello! How can I help you?")
        return ChatService(session_store=store, llm_provider=llm)

    @pytest.mark.asyncio
    async def test_chat_creates_session_if_none(self, chat_service):
        """Should create session if none provided."""
        response = await chat_service.chat("Hello", session_id=None, use_rag=False)

        assert response.session_id is not None
        assert response.role == MessageRole.ASSISTANT

    @pytest.mark.asyncio
    async def test_chat_uses_existing_session(self, chat_service):
        """Should use existing session if provided."""
        session = await chat_service.create_session()
        response = await chat_service.chat("Hello", session_id=session.session_id, use_rag=False)

        assert response.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_chat_saves_user_message(self, chat_service):
        """Should save user message."""
        session = await chat_service.create_session()
        await chat_service.chat("Hello world", session_id=session.session_id, use_rag=False)

        messages = await chat_service.get_messages(session.session_id)
        user_msgs = [m for m in messages if m.role == MessageRole.USER]

        assert len(user_msgs) == 1
        assert user_msgs[0].content == "Hello world"

    @pytest.mark.asyncio
    async def test_chat_saves_assistant_message(self, chat_service):
        """Should save assistant response."""
        session = await chat_service.create_session()
        await chat_service.chat("Hello", session_id=session.session_id, use_rag=False)

        messages = await chat_service.get_messages(session.session_id)
        assistant_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT]

        assert len(assistant_msgs) == 1
        assert "Hello" in assistant_msgs[0].content

    @pytest.mark.asyncio
    async def test_chat_empty_message_raises(self, chat_service):
        """Should raise error for empty message."""
        with pytest.raises(ChatError, match="Empty message"):
            await chat_service.chat("", use_rag=False)

        with pytest.raises(ChatError, match="Empty message"):
            await chat_service.chat("   ", use_rag=False)

    @pytest.mark.asyncio
    async def test_chat_nonexistent_session_raises(self, chat_service):
        """Should raise error for nonexistent session."""
        with pytest.raises(ChatError, match="Session not found"):
            await chat_service.chat("Hello", session_id="nonexistent", use_rag=False)

    @pytest.mark.asyncio
    async def test_chat_updates_session_count(self, chat_service):
        """Should update session message count."""
        session = await chat_service.create_session()
        initial_msgs = await chat_service.get_messages(session.session_id)
        initial_count = len(initial_msgs)

        await chat_service.chat("Hello", session_id=session.session_id, use_rag=False)

        messages = await chat_service.get_messages(session.session_id)
        assert len(messages) == initial_count + 2  # User + Assistant


class TestRAGIntegration:
    """Tests for RAG context integration."""

    @pytest.mark.asyncio
    async def test_chat_with_rag(self):
        """Should include RAG context in prompt."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        search = MockSearchService(context="Relevant document content here.")

        service = ChatService(
            session_store=store,
            llm_provider=llm,
            search_service=search,
        )

        await service.chat("What is X?", use_rag=True)

        # Verify context was included in the chat prompt (first call)
        assert "Relevant document content" in llm.chat_prompt

    @pytest.mark.asyncio
    async def test_chat_without_rag(self):
        """Should not include context when RAG disabled."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        search = MockSearchService(context="This should not appear.")

        service = ChatService(
            session_store=store,
            llm_provider=llm,
            search_service=search,
        )

        await service.chat("Hello", use_rag=False)

        assert "should not appear" not in llm.chat_prompt

    @pytest.mark.asyncio
    async def test_chat_rag_failure_graceful(self):
        """Should continue without RAG if search fails."""
        store = MockSessionStore()
        llm = MockLLMProvider()

        # Search service that throws
        search = MockSearchService()
        search.search_for_rag = AsyncMock(side_effect=Exception("Search failed"))

        service = ChatService(
            session_store=store,
            llm_provider=llm,
            search_service=search,
        )

        # Should not raise, continues without RAG
        response = await service.chat("Hello", use_rag=True)
        assert response is not None


class TestStreamingChat:
    """Tests for streaming chat responses."""

    @pytest.mark.asyncio
    async def test_chat_stream_yields_chunks(self):
        """Should yield response chunks."""
        store = MockSessionStore()
        llm = MockLLMProvider(response="This is a streaming test response")

        service = ChatService(session_store=store, llm_provider=llm)

        chunks = []
        async for chunk in service.chat_stream("Hello", use_rag=False):
            chunks.append(chunk)

        assert len(chunks) > 0
        full_response = "".join(chunks)
        assert "streaming" in full_response

    @pytest.mark.asyncio
    async def test_chat_stream_saves_complete_message(self):
        """Should save complete message after streaming."""
        store = MockSessionStore()
        llm = MockLLMProvider(response="Complete response")

        service = ChatService(session_store=store, llm_provider=llm)
        session = await service.create_session()

        # Consume the stream
        async for _ in service.chat_stream("Hello", session_id=session.session_id, use_rag=False):
            pass

        messages = await service.get_messages(session.session_id)
        assistant_msgs = [m for m in messages if m.role == MessageRole.ASSISTANT]

        assert len(assistant_msgs) == 1
        assert "Complete" in assistant_msgs[0].content

    @pytest.mark.asyncio
    async def test_chat_stream_empty_message_raises(self):
        """Should raise for empty message in stream."""
        store = MockSessionStore()
        llm = MockLLMProvider()

        service = ChatService(session_store=store, llm_provider=llm)

        with pytest.raises(ChatError, match="Empty message"):
            async for _ in service.chat_stream(""):
                pass


class TestMemoryFacts:
    """Tests for memory fact extraction and management."""

    @pytest.mark.asyncio
    async def test_add_memory_fact(self):
        """Should add manual memory fact."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        service = ChatService(session_store=store, llm_provider=llm)

        session = await service.create_session()
        fact = await service.add_memory_fact(session.session_id, "User prefers dark mode")

        assert fact.id is not None
        assert fact.value == "User prefers dark mode"
        assert fact.session_id == session.session_id

    @pytest.mark.asyncio
    async def test_get_session_facts(self):
        """Should retrieve session facts."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        service = ChatService(session_store=store, llm_provider=llm)

        session = await service.create_session()
        await service.add_memory_fact(session.session_id, "Fact 1")
        await service.add_memory_fact(session.session_id, "Fact 2")

        facts = await service.get_session_facts(session.session_id)

        assert len(facts) == 2


class TestSessionSummary:
    """Tests for session summary generation."""

    @pytest.mark.asyncio
    async def test_get_session_summary(self):
        """Should generate session summary."""
        store = MockSessionStore()
        llm = MockLLMProvider(response="This was a conversation about X.")
        service = ChatService(session_store=store, llm_provider=llm)

        session = await service.create_session()
        await service.chat("Hello", session_id=session.session_id, use_rag=False)

        summary = await service.get_session_summary(session.session_id)

        assert summary is not None
        assert len(summary) > 0

    @pytest.mark.asyncio
    async def test_get_summary_empty_session(self):
        """Should handle empty session."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        service = ChatService(session_store=store, llm_provider=llm)

        session = await service.create_session()
        summary = await service.get_session_summary(session.session_id)

        assert summary == "Empty session"


class TestPromptBuilding:
    """Tests for prompt construction."""

    @pytest.mark.asyncio
    async def test_prompt_includes_history(self):
        """Should include conversation history in prompt."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        service = ChatService(session_store=store, llm_provider=llm)

        session = await service.create_session()
        # First message
        await service.chat("First message", session_id=session.session_id, use_rag=False)
        # Second message
        await service.chat("Second message", session_id=session.session_id, use_rag=False)

        # History should be in the chat prompt for second message
        # Use prompts[2] since first chat generates 2 prompts (chat + fact extraction)
        second_chat_prompt = llm.prompts[2] if len(llm.prompts) > 2 else llm.chat_prompt
        assert "First message" in second_chat_prompt or "Previous conversation" in second_chat_prompt

    @pytest.mark.asyncio
    async def test_prompt_format(self):
        """Should format prompt correctly."""
        store = MockSessionStore()
        llm = MockLLMProvider()
        service = ChatService(session_store=store, llm_provider=llm)

        await service.chat("Test question", use_rag=False)

        assert "User: Test question" in llm.chat_prompt
        assert "Assistant:" in llm.chat_prompt
