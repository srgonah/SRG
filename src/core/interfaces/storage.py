"""
Abstract interfaces for storage providers.

Defines contracts for document, invoice, session, and vector stores.
"""

from abc import ABC, abstractmethod
from typing import Any

from src.core.entities.document import (
    Chunk,
    Document,
    IndexingState,
    Page,
)
from src.core.entities.invoice import AuditResult, Invoice
from src.core.entities.session import ChatSession, MemoryFact, Message


class IDocumentStore(ABC):
    """
    Abstract interface for document storage.

    Handles documents, pages, and chunks.
    """

    # Document operations
    @abstractmethod
    async def create_document(self, document: Document) -> Document:
        """Create a new document record."""
        pass

    @abstractmethod
    async def get_document(self, doc_id: int) -> Document | None:
        """Get document by ID."""
        pass

    @abstractmethod
    async def get_document_by_hash(self, file_hash: str) -> Document | None:
        """Get document by file hash (for deduplication)."""
        pass

    @abstractmethod
    async def update_document(self, document: Document) -> Document:
        """Update existing document."""
        pass

    @abstractmethod
    async def delete_document(self, doc_id: int) -> bool:
        """Delete document and related data."""
        pass

    @abstractmethod
    async def list_documents(
        self,
        limit: int = 100,
        offset: int = 0,
        status: str | None = None,
    ) -> list[Document]:
        """List documents with pagination."""
        pass

    # Page operations
    @abstractmethod
    async def create_page(self, page: Page) -> Page:
        """Create a new page record."""
        pass

    @abstractmethod
    async def get_pages(self, doc_id: int) -> list[Page]:
        """Get all pages for a document."""
        pass

    @abstractmethod
    async def update_page(self, page: Page) -> Page:
        """Update page record."""
        pass

    # Chunk operations
    @abstractmethod
    async def create_chunks(self, chunks: list[Chunk]) -> list[Chunk]:
        """Create multiple chunk records."""
        pass

    @abstractmethod
    async def get_chunks(self, doc_id: int) -> list[Chunk]:
        """Get all chunks for a document."""
        pass

    @abstractmethod
    async def get_chunk_by_id(self, chunk_id: int) -> Chunk | None:
        """Get chunk by ID."""
        pass

    @abstractmethod
    async def get_chunks_for_indexing(
        self,
        last_chunk_id: int = 0,
        limit: int = 1000,
    ) -> list[Chunk]:
        """Get chunks that need indexing."""
        pass


class IInvoiceStore(ABC):
    """
    Abstract interface for invoice storage.

    Handles invoices, line items, and audit results.
    """

    # Invoice operations
    @abstractmethod
    async def create_invoice(self, invoice: Invoice) -> Invoice:
        """Create a new invoice record."""
        pass

    @abstractmethod
    async def get_invoice(self, invoice_id: int) -> Invoice | None:
        """Get invoice by ID with items."""
        pass

    @abstractmethod
    async def get_invoice_by_doc_id(self, doc_id: int) -> Invoice | None:
        """Get invoice by document ID."""
        pass

    @abstractmethod
    async def update_invoice(self, invoice: Invoice) -> Invoice:
        """Update invoice record."""
        pass

    @abstractmethod
    async def delete_invoice(self, invoice_id: int) -> bool:
        """Delete invoice and items."""
        pass

    @abstractmethod
    async def list_invoices(
        self,
        limit: int = 100,
        offset: int = 0,
        company_key: str | None = None,
    ) -> list[Invoice]:
        """List invoices with pagination."""
        pass

    @abstractmethod
    async def search_invoices(
        self,
        query: str,
        limit: int = 20,
    ) -> list[Invoice]:
        """Search invoices by invoice_no, seller, or buyer."""
        pass

    # Audit operations
    @abstractmethod
    async def create_audit_result(self, result: AuditResult) -> AuditResult:
        """Store audit result."""
        pass

    @abstractmethod
    async def get_audit_result(self, invoice_id: int) -> AuditResult | None:
        """Get latest audit result for invoice."""
        pass

    @abstractmethod
    async def list_audit_results(
        self,
        invoice_id: int | None = None,
        limit: int = 100,
    ) -> list[AuditResult]:
        """List audit results."""
        pass

    # Item operations for search
    @abstractmethod
    async def get_items_for_indexing(
        self,
        last_item_id: int = 0,
        limit: int = 1000,
    ) -> list[dict]:
        """Get items that need indexing."""
        pass


class ISessionStore(ABC):
    """
    Abstract interface for chat session storage.

    Replaces JSON file storage with proper persistence.
    """

    @abstractmethod
    async def create_session(self, session: ChatSession) -> ChatSession:
        """Create a new chat session."""
        pass

    @abstractmethod
    async def get_session(self, session_id: str) -> ChatSession | None:
        """Get session by ID with messages."""
        pass

    @abstractmethod
    async def update_session(self, session: ChatSession) -> ChatSession:
        """Update session metadata."""
        pass

    @abstractmethod
    async def delete_session(self, session_id: str) -> bool:
        """Delete session and messages."""
        pass

    @abstractmethod
    async def list_sessions(
        self,
        limit: int = 50,
        offset: int = 0,
        status: str | None = None,
    ) -> list[ChatSession]:
        """List sessions with pagination."""
        pass

    # Message operations
    @abstractmethod
    async def add_message(self, message: Message) -> Message:
        """Add message to session."""
        pass

    @abstractmethod
    async def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[Message]:
        """Get messages for session."""
        pass

    # Memory operations
    @abstractmethod
    async def save_memory_fact(self, fact: MemoryFact) -> MemoryFact:
        """Save or update memory fact."""
        pass

    @abstractmethod
    async def get_memory_facts(
        self,
        session_id: str | None = None,
        fact_type: str | None = None,
    ) -> list[MemoryFact]:
        """Get memory facts, optionally filtered."""
        pass

    @abstractmethod
    async def delete_memory_fact(self, fact_id: int) -> bool:
        """Delete a memory fact."""
        pass


class IVectorStore(ABC):
    """
    Abstract interface for vector search storage.

    Handles FAISS index management and search.
    """

    @abstractmethod
    async def build_index(
        self,
        index_name: str,
        embeddings: Any,  # np.ndarray
        ids: list[int],
        force_rebuild: bool = False,
    ) -> bool:
        """Build or rebuild a FAISS index."""
        pass

    @abstractmethod
    async def add_vectors(
        self,
        index_name: str,
        embeddings: Any,  # np.ndarray
        ids: list[int],
    ) -> bool:
        """Add vectors to existing index (incremental)."""
        pass

    @abstractmethod
    async def search(
        self,
        index_name: str,
        query_vector: Any,  # np.ndarray
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """
        Search index for similar vectors.

        Returns:
            List of (id, score) tuples
        """
        pass

    @abstractmethod
    async def get_index_stats(self, index_name: str) -> dict:
        """Get index statistics."""
        pass

    @abstractmethod
    async def save_index(self, index_name: str) -> bool:
        """Save index to disk."""
        pass

    @abstractmethod
    async def load_index(self, index_name: str) -> bool:
        """Load index from disk."""
        pass

    # ID mapping
    @abstractmethod
    async def save_id_mapping(
        self,
        index_name: str,
        faiss_id: int,
        entity_id: int,
    ) -> None:
        """Save FAISS ID to entity ID mapping."""
        pass

    @abstractmethod
    async def get_entity_id(
        self,
        index_name: str,
        faiss_id: int,
    ) -> int | None:
        """Get entity ID from FAISS ID."""
        pass

    @abstractmethod
    async def get_entity_ids(
        self,
        index_name: str,
        faiss_ids: list[int],
    ) -> dict[int, int]:
        """Get multiple entity IDs from FAISS IDs."""
        pass


class IIndexingStateStore(ABC):
    """
    Interface for tracking indexing state.

    Enables incremental indexing without full rebuilds.
    """

    @abstractmethod
    async def get_state(self, index_name: str) -> IndexingState | None:
        """Get current indexing state."""
        pass

    @abstractmethod
    async def update_state(self, state: IndexingState) -> IndexingState:
        """Update indexing state."""
        pass

    @abstractmethod
    async def reset_state(self, index_name: str) -> bool:
        """Reset indexing state (for full rebuild)."""
        pass


class IHybridSearcher(ABC):
    """
    Abstract interface for hybrid search (vector + keyword).

    Combines semantic search with BM25/FTS keyword search.
    """

    @abstractmethod
    async def search(
        self,
        query: str,
        top_k: int = 10,
        search_type: str = "hybrid",
        filters: dict[str, Any] | None = None,
    ) -> list[Any]:  # Returns list of SearchResult
        """
        Perform hybrid search.

        Args:
            query: Search query text
            top_k: Number of results to return
            search_type: "hybrid", "semantic", or "keyword"
            filters: Optional metadata filters

        Returns:
            List of SearchResult entities
        """
        pass

    @abstractmethod
    async def search_items(
        self,
        query: str,
        top_k: int = 10,
        filters: dict[str, Any] | None = None,
    ) -> list[Any]:  # Returns list of SearchResult
        """Search invoice line items."""
        pass


class IReranker(ABC):
    """
    Abstract interface for search result reranking.

    Reranks search results for better relevance.
    """

    @abstractmethod
    async def rerank(
        self,
        query: str,
        texts: list[str],
        top_k: int = 10,
    ) -> list[tuple[int, float]]:
        """
        Rerank texts by relevance to query.

        Args:
            query: Original search query
            texts: List of texts to rerank
            top_k: Number of results to return

        Returns:
            List of (original_index, score) tuples, sorted by relevance
        """
        pass

    @abstractmethod
    def is_enabled(self) -> bool:
        """Check if reranker is enabled and available."""
        pass


class ISearchCache(ABC):
    """
    Abstract interface for search result caching.

    Caches search results to reduce repeated queries.
    """

    @abstractmethod
    def get(
        self,
        query: str,
        search_type: str,
        top_k: int,
        filters: str = "",
    ) -> list[Any] | None:
        """Get cached search results."""
        pass

    @abstractmethod
    def set(
        self,
        query: str,
        search_type: str,
        top_k: int,
        results: list[Any],
        filters: str = "",
        ttl: int | None = None,
    ) -> None:
        """Cache search results."""
        pass

    @abstractmethod
    def invalidate(self) -> None:
        """Clear all cached results."""
        pass

    @abstractmethod
    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        pass
