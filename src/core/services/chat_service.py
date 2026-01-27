"""
Chat service with RAG and memory.

Layer-pure service managing conversations with context-aware responses.
NO infrastructure imports - depends only on core entities, interfaces, exceptions.
"""

from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any

from src.core.entities.session import (
    ChatSession,
    MemoryFact,
    MemoryFactType,
    Message,
    MessageRole,
)
from src.core.exceptions import ChatError
from src.core.interfaces import ILLMProvider, ISessionStore

# Import SearchService for type hints only - it's also a core service
from src.core.services.search_service import SearchService


class ChatService:
    """
    Chat service with RAG integration.

    Features:
    - Session management
    - Context retrieval via search
    - Memory fact extraction
    - Streaming responses
    - Graceful degradation when LLM unavailable

    Required interfaces for DI:
    - ISessionStore: Session and message persistence
    - ILLMProvider: LLM for responses and fact extraction
    - SearchService: RAG context retrieval (optional)
    """

    def __init__(
        self,
        session_store: ISessionStore,
        llm_provider: ILLMProvider,
        search_service: SearchService | None = None,
        max_history_messages: int = 10,
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ):
        """
        Initialize chat service with injected dependencies.

        Args:
            session_store: Session persistence (required)
            llm_provider: LLM provider (required)
            search_service: Optional search service for RAG
            max_history_messages: Max messages to include in context
            max_tokens: Default max tokens for LLM responses
            temperature: Default temperature for LLM responses
        """
        self._store = session_store
        self._llm = llm_provider
        self._search = search_service
        self._max_history = max_history_messages
        self._max_tokens = max_tokens
        self._temperature = temperature

    async def create_session(
        self,
        title: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ChatSession:
        """
        Create a new chat session.

        Args:
            title: Optional session title
            metadata: Optional metadata

        Returns:
            New ChatSession entity
        """
        session = ChatSession(
            title=title or "New Chat",
            metadata=metadata or {},
        )

        session = await self._store.create_session(session)
        return session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get session by ID."""
        return await self._store.get_session(session_id)

    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List recent sessions."""
        return await self._store.list_sessions(limit=limit, offset=offset)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        return await self._store.delete_session(session_id)

    async def chat(
        self,
        message: str,
        session_id: str | None = None,
        use_rag: bool = True,
        top_k: int = 5,
    ) -> Message:
        """
        Send a message and get a response.

        Args:
            message: User message
            session_id: Optional session ID (creates new if None)
            use_rag: Whether to use RAG for context
            top_k: Number of context chunks for RAG

        Returns:
            Assistant response Message

        Raises:
            ChatError: If chat fails
        """
        if not message or not message.strip():
            raise ChatError("Empty message")

        message = message.strip()

        # Get or create session
        if session_id:
            session = await self._store.get_session(session_id)
            if not session:
                raise ChatError(f"Session not found: {session_id}")
        else:
            session = await self.create_session()

        # Save user message
        user_msg = Message(
            session_id=session.session_id,
            role=MessageRole.USER,
            content=message,
        )
        user_msg = await self._store.add_message(user_msg)

        try:
            # Build context from RAG
            context = ""
            if use_rag and self._search:
                try:
                    search_context = await self._search.search_for_rag(
                        query=message,
                        top_k=top_k,
                    )
                    context = search_context.formatted_context
                except Exception:
                    # Graceful degradation - continue without RAG
                    pass

            # Get conversation history
            history = await self._store.get_messages(
                session.session_id, limit=self._max_history
            )

            # Build prompt
            prompt = self._build_prompt(
                message=message,
                history=history[:-1],  # Exclude just-added user message
                context=context,
            )

            # Generate response
            response = await self._llm.generate(
                prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            )
            response_text = response.text

            # Save assistant message
            assistant_msg = Message(
                session_id=session.session_id,
                role=MessageRole.ASSISTANT,
                content=response_text,
                metadata={"context_used": context} if context else {},
            )
            assistant_msg = await self._store.add_message(assistant_msg)

            # Extract and save memory facts (non-blocking, graceful)
            await self._extract_memory_facts(session.session_id, message, response_text)

            # Update session timestamp
            session.updated_at = datetime.now()
            await self._store.update_session(session)

            return assistant_msg

        except Exception as e:
            raise ChatError(f"Chat failed: {str(e)}")

    async def chat_stream(
        self,
        message: str,
        session_id: str | None = None,
        use_rag: bool = True,
        top_k: int = 5,
    ) -> AsyncIterator[str]:
        """
        Stream a chat response.

        Args:
            message: User message
            session_id: Optional session ID
            use_rag: Whether to use RAG
            top_k: Number of context chunks

        Yields:
            Response text chunks

        Raises:
            ChatError: If chat fails
        """
        if not message or not message.strip():
            raise ChatError("Empty message")

        message = message.strip()

        # Get or create session
        if session_id:
            session = await self._store.get_session(session_id)
            if not session:
                raise ChatError(f"Session not found: {session_id}")
        else:
            session = await self.create_session()

        # Save user message
        user_msg = Message(
            session_id=session.session_id,
            role=MessageRole.USER,
            content=message,
        )
        await self._store.add_message(user_msg)

        try:
            # Build context from RAG
            context = ""
            if use_rag and self._search:
                try:
                    search_context = await self._search.search_for_rag(
                        query=message,
                        top_k=top_k,
                    )
                    context = search_context.formatted_context
                except Exception:
                    pass

            # Get history
            history = await self._store.get_messages(
                session.session_id, limit=self._max_history
            )

            # Build prompt
            prompt = self._build_prompt(
                message=message,
                history=history[:-1],
                context=context,
            )

            # Stream response
            full_response = ""

            async for chunk in self._llm.generate_stream(
                prompt,
                max_tokens=self._max_tokens,
                temperature=self._temperature,
            ):
                full_response += chunk
                yield chunk

            # Save complete response
            assistant_msg = Message(
                session_id=session.session_id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                metadata={"context_used": context} if context else {},
            )
            await self._store.add_message(assistant_msg)

            # Update session timestamp
            session.updated_at = datetime.now()
            await self._store.update_session(session)

        except Exception as e:
            raise ChatError(f"Chat stream failed: {str(e)}")

    def _build_prompt(
        self,
        message: str,
        history: list[Message],
        context: str = "",
    ) -> str:
        """Build prompt with history and context."""
        parts = []

        # System context from RAG
        if context:
            parts.append(
                f"Use the following context to help answer the question:\n\n{context}\n\n---\n"
            )

        # Conversation history
        if history:
            parts.append("Previous conversation:\n")
            for msg in history[-6:]:  # Last 6 messages
                role = "User" if msg.role == MessageRole.USER else "Assistant"
                parts.append(f"{role}: {msg.content}\n")
            parts.append("\n")

        # Current message
        parts.append(f"User: {message}\n\nAssistant:")

        return "".join(parts)

    async def _extract_memory_facts(
        self,
        session_id: str,
        user_message: str,
        assistant_response: str,
    ) -> None:
        """Extract and save memory facts from conversation."""
        try:
            prompt = f"""Extract key facts from this conversation that might be useful later.

User: {user_message}
Assistant: {assistant_response}

List only important facts (entities, numbers, decisions).
Format: One fact per line, starting with "- ".
If no important facts, respond with "NONE".

Facts:"""

            llm_response = await self._llm.generate(
                prompt,
                max_tokens=200,
                temperature=0.1,
            )
            response = llm_response.text

            if "NONE" in response.upper():
                return

            for line in response.strip().split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    fact_text = line[2:].strip()
                    if fact_text and len(fact_text) > 5:
                        fact = MemoryFact(
                            session_id=session_id,
                            fact_type=MemoryFactType.ENTITY,
                            key=f"extracted_{hash(fact_text) % 10000}",
                            value=fact_text,
                        )
                        await self._store.save_memory_fact(fact)

        except Exception:
            # Graceful degradation - memory extraction is optional
            pass

    async def get_session_facts(self, session_id: str) -> list[MemoryFact]:
        """Get all memory facts for a session."""
        return await self._store.get_memory_facts(session_id=session_id)

    async def add_memory_fact(
        self,
        session_id: str,
        fact: str,
        fact_type: MemoryFactType = MemoryFactType.USER_PREFERENCE,
    ) -> MemoryFact:
        """Manually add a memory fact to a session."""
        memory_fact = MemoryFact(
            session_id=session_id,
            fact_type=fact_type,
            key=f"user_{hash(fact) % 10000}",
            value=fact,
        )
        return await self._store.save_memory_fact(memory_fact)

    async def get_session_summary(self, session_id: str) -> str:
        """Generate a summary of the session."""
        messages = await self._store.get_messages(session_id, limit=50)

        if not messages:
            return "Empty session"

        # Build conversation text
        conv_text = "\n".join(
            f"{msg.role.value}: {msg.content[:200]}" for msg in messages
        )

        prompt = f"""Summarize this conversation in 2-3 sentences:

{conv_text[:2000]}

Summary:"""

        try:
            summary_response = await self._llm.generate(
                prompt,
                max_tokens=150,
                temperature=0.3,
            )
            return summary_response.text.strip()
        except Exception:
            return "Unable to generate summary"

    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for a session."""
        return await self._store.get_messages(
            session_id=session_id,
            limit=limit,
            offset=offset,
        )
