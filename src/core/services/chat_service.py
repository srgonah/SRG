"""
Chat service with RAG and memory.

Manages conversations with context-aware responses.
"""

from collections.abc import AsyncIterator
from datetime import datetime

from src.config import get_logger, get_settings
from src.core.entities.session import (
    ChatSession,
    MemoryFact,
    Message,
    MessageRole,
)
from src.core.exceptions import ChatError
from src.core.services.search_service import SearchService, get_search_service
from src.infrastructure.llm import ILLMProvider, get_llm_provider
from src.infrastructure.storage.sqlite import SessionStore, get_session_store

logger = get_logger(__name__)


class ChatService:
    """
    Chat service with RAG integration.

    Features:
    - Session management
    - Context retrieval via search
    - Memory fact extraction
    - Streaming responses
    """

    def __init__(
        self,
        llm_provider: ILLMProvider | None = None,
        search_service: SearchService | None = None,
        session_store: SessionStore | None = None,
    ):
        """
        Initialize chat service.

        Args:
            llm_provider: Optional custom LLM provider
            search_service: Optional custom search service
            session_store: Optional custom session store
        """
        self._llm = llm_provider
        self._search = search_service
        self._store = session_store
        self._settings = get_settings()

    def _get_llm(self) -> ILLMProvider:
        """Lazy load LLM provider."""
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    def _get_search(self) -> SearchService:
        """Lazy load search service."""
        if self._search is None:
            self._search = get_search_service()
        return self._search

    async def _get_store(self) -> SessionStore:
        """Lazy load session store."""
        if self._store is None:
            self._store = await get_session_store()
        return self._store

    async def create_session(
        self,
        title: str | None = None,
        metadata: dict | None = None,
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

        store = await self._get_store()
        await store.save_session(session)

        logger.info("session_created", session_id=session.id)

        return session

    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get session by ID."""
        store = await self._get_store()
        return await store.get_session(session_id)

    async def list_sessions(
        self,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ChatSession]:
        """List recent sessions."""
        store = await self._get_store()
        return await store.list_sessions(limit=limit, offset=offset)

    async def delete_session(self, session_id: str) -> bool:
        """Delete a session and its messages."""
        store = await self._get_store()
        result = await store.delete_session(session_id)

        if result:
            logger.info("session_deleted", session_id=session_id)

        return result

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
        """
        if not message or not message.strip():
            raise ChatError("Empty message")

        message = message.strip()
        store = await self._get_store()

        # Get or create session
        if session_id:
            session = await store.get_session(session_id)
            if not session:
                raise ChatError(f"Session not found: {session_id}")
        else:
            session = await self.create_session()

        # Save user message
        user_msg = Message(
            session_id=session.id,
            role=MessageRole.USER,
            content=message,
        )
        await store.save_message(user_msg)

        logger.info(
            "chat_request",
            session_id=session.id,
            message_length=len(message),
            use_rag=use_rag,
        )

        try:
            # Build context
            context = ""
            if use_rag:
                search = self._get_search()
                search_context = await search.search_for_rag(
                    query=message,
                    top_k=top_k,
                )
                context = search_context.formatted_context

            # Get conversation history
            history = await store.get_messages(session.id, limit=10)

            # Build prompt
            prompt = self._build_prompt(
                message=message,
                history=history[:-1],  # Exclude just-added user message
                context=context,
            )

            # Generate response
            llm = self._get_llm()
            response_text = await llm.generate(
                prompt,
                max_tokens=self._settings.llm.max_tokens,
                temperature=self._settings.llm.temperature,
            )

            # Save assistant message
            assistant_msg = Message(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=response_text,
                context_used=context if context else None,
            )
            await store.save_message(assistant_msg)

            # Extract and save memory facts (async, non-blocking)
            await self._extract_memory_facts(session.id, message, response_text)

            # Update session
            session.message_count += 2
            session.updated_at = datetime.now()
            await store.save_session(session)

            logger.info(
                "chat_response",
                session_id=session.id,
                response_length=len(response_text),
            )

            return assistant_msg

        except Exception as e:
            logger.error("chat_failed", session_id=session.id, error=str(e))
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
        """
        if not message or not message.strip():
            raise ChatError("Empty message")

        message = message.strip()
        store = await self._get_store()

        # Get or create session
        if session_id:
            session = await store.get_session(session_id)
            if not session:
                raise ChatError(f"Session not found: {session_id}")
        else:
            session = await self.create_session()

        # Save user message
        user_msg = Message(
            session_id=session.id,
            role=MessageRole.USER,
            content=message,
        )
        await store.save_message(user_msg)

        try:
            # Build context
            context = ""
            if use_rag:
                search = self._get_search()
                search_context = await search.search_for_rag(
                    query=message,
                    top_k=top_k,
                )
                context = search_context.formatted_context

            # Get history
            history = await store.get_messages(session.id, limit=10)

            # Build prompt
            prompt = self._build_prompt(
                message=message,
                history=history[:-1],
                context=context,
            )

            # Stream response
            llm = self._get_llm()
            full_response = ""

            async for chunk in llm.generate_stream(
                prompt,
                max_tokens=self._settings.llm.max_tokens,
                temperature=self._settings.llm.temperature,
            ):
                full_response += chunk
                yield chunk

            # Save complete response
            assistant_msg = Message(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=full_response,
                context_used=context if context else None,
            )
            await store.save_message(assistant_msg)

            # Update session
            session.message_count += 2
            session.updated_at = datetime.now()
            await store.save_session(session)

        except Exception as e:
            logger.error("chat_stream_failed", error=str(e))
            raise ChatError(f"Chat stream failed: {str(e)}")

    def _build_prompt(
        self,
        message: str,
        history: list[Message],
        context: str = "",
    ) -> str:
        """Build prompt with history and context."""
        parts = []

        # System context
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
            llm = self._get_llm()

            prompt = f"""Extract key facts from this conversation that might be useful later.

User: {user_message}
Assistant: {assistant_response}

List only important facts (entities, numbers, decisions).
Format: One fact per line, starting with "- ".
If no important facts, respond with "NONE".

Facts:"""

            response = await llm.generate(
                prompt,
                max_tokens=200,
                temperature=0.1,
            )

            if "NONE" in response.upper():
                return

            store = await self._get_store()

            for line in response.strip().split("\n"):
                line = line.strip()
                if line.startswith("- "):
                    fact_text = line[2:].strip()
                    if fact_text and len(fact_text) > 5:
                        fact = MemoryFact(
                            session_id=session_id,
                            fact=fact_text,
                            source="extraction",
                        )
                        await store.save_memory_fact(fact)

        except Exception as e:
            logger.debug("memory_extraction_failed", error=str(e))

    async def get_session_summary(self, session_id: str) -> str:
        """Generate a summary of the session."""
        store = await self._get_store()
        messages = await store.get_messages(session_id, limit=50)

        if not messages:
            return "Empty session"

        # Build conversation text
        conv_text = "\n".join(f"{msg.role.value}: {msg.content[:200]}" for msg in messages)

        llm = self._get_llm()

        prompt = f"""Summarize this conversation in 2-3 sentences:

{conv_text[:2000]}

Summary:"""

        summary = await llm.generate(
            prompt,
            max_tokens=150,
            temperature=0.3,
        )

        return summary.strip()


# Singleton
_chat_service: ChatService | None = None


async def get_chat_service() -> ChatService:
    """Get or create chat service singleton."""
    global _chat_service
    if _chat_service is None:
        _chat_service = ChatService()
    return _chat_service
