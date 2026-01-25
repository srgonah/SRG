"""
Unit tests for ChatWithContextUseCase.

Tests the RAG-powered chat flow with mocked services.
"""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.application.dto.requests import ChatRequest, CreateSessionRequest
from src.application.use_cases.chat_with_context import (
    ChatResultDTO,
    ChatWithContextUseCase,
)
from src.core.entities.session import ChatSession, Message, MessageRole


# Test fixtures
@pytest.fixture
def sample_session() -> ChatSession:
    """Create a sample chat session for testing."""
    return ChatSession(
        session_id="sess_123",
        title="Test Session",
        messages=[],
        memory_facts=[],
        created_at=datetime.now(),
        updated_at=datetime.now(),
        metadata={},
    )


@pytest.fixture
def sample_message():
    """Create a sample message mock for testing."""
    # Use MagicMock to allow arbitrary attributes like context_used
    msg = MagicMock()
    msg.id = "456"
    msg.session_id = "sess_123"
    msg.role = MessageRole.ASSISTANT  # Enum with .value = "assistant"
    msg.content = "This is a test response based on your invoice data."
    msg.created_at = datetime.now()
    msg.context_used = "[1] Invoice INV-2024-001: Test Product..."
    msg.token_count = None
    return msg


@pytest.fixture
def sample_user_message():
    """Create a sample user message mock."""
    msg = MagicMock()
    msg.id = "789"
    msg.session_id = "sess_123"
    msg.role = MessageRole.USER
    msg.content = "What invoices do we have from VOLTA HUB?"
    msg.created_at = datetime.now()
    return msg


@pytest.fixture
def mock_chat_service(sample_session, sample_message):
    """Create a mock chat service."""
    mock = MagicMock()
    mock.get_session = AsyncMock(return_value=sample_session)
    mock.create_session = AsyncMock(return_value=sample_session)
    mock.list_sessions = AsyncMock(return_value=[sample_session])
    mock.delete_session = AsyncMock(return_value=True)
    mock.get_session_summary = AsyncMock(return_value="Session about invoices")

    # Mock chat method to return message mock
    # sample_message is already a MagicMock with context_used set
    mock.chat = AsyncMock(return_value=sample_message)

    return mock


class TestChatWithContextUseCase:
    """Tests for ChatWithContextUseCase."""

    @pytest.mark.asyncio
    async def test_execute_new_session(
        self,
        sample_session,
        sample_message,
        mock_chat_service,
    ):
        """Test chat execution with new session creation."""
        # When request.session_id is None, get_session is only called once (after chat)
        # The mock returns sample_session directly
        mock_chat_service.get_session.return_value = sample_session

        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Execute without session_id (creates new)
        request = ChatRequest(
            message="Hello, what invoices do we have?",
            session_id=None,
            use_rag=True,
            top_k=5,
        )
        result = await use_case.execute(request)

        # Assertions
        assert isinstance(result, ChatResultDTO)
        assert result.session is not None
        assert result.message is not None

        # Verify chat was called with RAG enabled
        mock_chat_service.chat.assert_called_once()
        call_kwargs = mock_chat_service.chat.call_args[1]
        assert call_kwargs["use_rag"] is True
        assert call_kwargs["top_k"] == 5

    @pytest.mark.asyncio
    async def test_execute_existing_session(
        self,
        sample_session,
        sample_message,
        mock_chat_service,
    ):
        """Test chat execution with existing session."""
        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Execute with existing session_id
        request = ChatRequest(
            message="Tell me more about those invoices",
            session_id="sess_123",
            use_rag=True,
        )
        result = await use_case.execute(request)

        # Assertions
        assert result.session.session_id == "sess_123"

        # Verify session was retrieved
        mock_chat_service.get_session.assert_called()

    @pytest.mark.asyncio
    async def test_execute_without_rag(
        self,
        sample_session,
        sample_message,
        mock_chat_service,
    ):
        """Test chat execution with RAG disabled."""
        # Configure mock - no context when RAG disabled
        sample_message.context_used = None
        # When request.session_id is None, get_session is only called once (after chat)
        mock_chat_service.get_session.return_value = sample_session

        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Execute without RAG
        request = ChatRequest(
            message="Just say hello",
            session_id=None,
            use_rag=False,
        )
        result = await use_case.execute(request)

        # Verify RAG was disabled
        call_kwargs = mock_chat_service.chat.call_args[1]
        assert call_kwargs["use_rag"] is False

    @pytest.mark.asyncio
    async def test_execute_counts_context_chunks(
        self,
        sample_session,
        sample_message,
        mock_chat_service,
    ):
        """Test that context chunks are counted correctly."""
        # Configure mock with multiple context references
        # Add context_used attribute dynamically (use case expects this)
        sample_message.context_used = "[1] First chunk... [2] Second chunk... [3] Third"

        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Execute
        request = ChatRequest(message="Search query", use_rag=True)
        result = await use_case.execute(request)

        # Should count 3 chunks based on "[" characters
        assert result.context_chunks == 3

    @pytest.mark.asyncio
    async def test_create_session(
        self,
        sample_session,
        mock_chat_service,
    ):
        """Test session creation."""
        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Create session
        request = CreateSessionRequest(
            title="New Invoice Discussion",
            metadata={"topic": "invoices"},
        )
        session = await use_case.create_session(request)

        # Assertions
        assert session is not None
        mock_chat_service.create_session.assert_called_once_with(
            title="New Invoice Discussion",
            metadata={"topic": "invoices"},
        )

    @pytest.mark.asyncio
    async def test_list_sessions(
        self,
        sample_session,
        mock_chat_service,
    ):
        """Test session listing."""
        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # List sessions
        sessions = await use_case.list_sessions(limit=10, offset=0)

        # Assertions
        assert len(sessions) == 1
        assert sessions[0].session_id == "sess_123"
        mock_chat_service.list_sessions.assert_called_once_with(limit=10, offset=0)

    @pytest.mark.asyncio
    async def test_delete_session(
        self,
        mock_chat_service,
    ):
        """Test session deletion."""
        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Delete session
        result = await use_case.delete_session("sess_123")

        # Assertions
        assert result is True
        mock_chat_service.delete_session.assert_called_once_with("sess_123")

    @pytest.mark.asyncio
    async def test_get_session_summary(
        self,
        mock_chat_service,
    ):
        """Test session summary generation."""
        # Create use case
        use_case = ChatWithContextUseCase(chat_service=mock_chat_service)

        # Get summary
        summary = await use_case.get_session_summary("sess_123")

        # Assertions
        assert summary == "Session about invoices"
        mock_chat_service.get_session_summary.assert_called_once_with("sess_123")

    def test_to_response(
        self,
        sample_session,
        sample_message,
    ):
        """Test conversion to API response format."""
        # Create result
        result = ChatResultDTO(
            session=sample_session,
            message=sample_message,
            context_chunks=2,
        )

        # Create use case and convert
        use_case = ChatWithContextUseCase()
        response = use_case.to_response(result)

        # Verify response structure
        assert response.session_id == "sess_123"
        assert response.message.role == "assistant"
        assert response.context_chunks == 2

    def test_session_to_response(
        self,
        sample_session,
    ):
        """Test session to response conversion."""
        # Create use case
        use_case = ChatWithContextUseCase()

        # Convert
        response = use_case.session_to_response(sample_session)

        # Verify
        assert response.id == "sess_123"
        assert response.title == "Test Session"

    def test_sessions_to_response(
        self,
        sample_session,
    ):
        """Test sessions list to response conversion."""
        # Create use case
        use_case = ChatWithContextUseCase()

        # Convert
        response = use_case.sessions_to_response([sample_session], total=1)

        # Verify
        assert response.total == 1
        assert len(response.sessions) == 1
        assert response.sessions[0].id == "sess_123"


class TestChatRequestValidation:
    """Tests for ChatRequest DTO validation."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = ChatRequest(
            message="What invoices are from VOLTA HUB?",
            session_id="sess_123",
            use_rag=True,
            top_k=5,
        )
        assert request.message == "What invoices are from VOLTA HUB?"
        assert request.session_id == "sess_123"
        assert request.use_rag is True
        assert request.top_k == 5

    def test_default_values(self):
        """Test default values are applied."""
        request = ChatRequest(message="Hello")
        assert request.session_id is None
        assert request.use_rag is True
        assert request.top_k == 5
        assert request.stream is False
        assert request.include_sources is True
        assert request.extract_memory is True

    def test_message_min_length(self):
        """Test message minimum length validation."""
        with pytest.raises(ValueError):
            ChatRequest(message="")

    def test_message_max_length(self):
        """Test message maximum length validation."""
        with pytest.raises(ValueError):
            ChatRequest(message="x" * 5000)  # Over 4000 chars

    def test_top_k_bounds(self):
        """Test top_k parameter bounds."""
        # Valid
        request = ChatRequest(message="test", top_k=1)
        assert request.top_k == 1

        request = ChatRequest(message="test", top_k=20)
        assert request.top_k == 20

        # Invalid - too low
        with pytest.raises(ValueError):
            ChatRequest(message="test", top_k=0)

        # Invalid - too high
        with pytest.raises(ValueError):
            ChatRequest(message="test", top_k=25)


class TestCreateSessionRequestValidation:
    """Tests for CreateSessionRequest DTO validation."""

    def test_valid_request(self):
        """Test valid request creation."""
        request = CreateSessionRequest(
            title="Invoice Discussion",
            metadata={"department": "finance"},
        )
        assert request.title == "Invoice Discussion"
        assert request.metadata == {"department": "finance"}

    def test_default_values(self):
        """Test default values."""
        request = CreateSessionRequest()
        assert request.title is None
        assert request.metadata is None

    def test_title_max_length(self):
        """Test title maximum length."""
        # Valid
        request = CreateSessionRequest(title="x" * 200)
        assert len(request.title) == 200

        # Invalid - too long
        with pytest.raises(ValueError):
            CreateSessionRequest(title="x" * 201)
