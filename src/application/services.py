"""
Service factory functions for dependency injection.

This module provides factory functions that wire infrastructure
implementations to core services. Use cases should import from here.

Clean Architecture: Application layer orchestrates DI, not core layer.
"""

from typing import TYPE_CHECKING, cast

from src.core.interfaces import (
    IHybridSearcher,
    IReranker,
    ISearchCache,
)
from src.core.services import (
    ChatService,
    DocumentIndexerService,
    InvoiceAuditorService,
    InvoiceParserService,
    SearchService,
)

if TYPE_CHECKING:
    from src.core.interfaces import (
        IDocumentStore,
        IEmbeddingProvider,
        IInvoiceStore,
        ILLMProvider,
        IParserRegistry,
        ISessionStore,
        IVectorStore,
    )


# Singleton service instances
_invoice_parser_service: InvoiceParserService | None = None
_invoice_auditor_service: InvoiceAuditorService | None = None
_document_indexer_service: DocumentIndexerService | None = None
_search_service: SearchService | None = None
_chat_service: ChatService | None = None


def get_invoice_parser_service(
    parser_registry: "IParserRegistry | None" = None,
    document_store: "IDocumentStore | None" = None,
    invoice_store: "IInvoiceStore | None" = None,
) -> InvoiceParserService:
    """
    Get or create InvoiceParserService instance.

    Creates infrastructure dependencies if not provided.
    Uses singleton pattern for efficiency.

    Args:
        parser_registry: Optional parser registry override
        document_store: Optional document store override
        invoice_store: Optional invoice store override

    Returns:
        Configured InvoiceParserService
    """
    global _invoice_parser_service

    if _invoice_parser_service is not None and parser_registry is None:
        return _invoice_parser_service

    # Lazy import infrastructure to avoid circular imports
    from src.infrastructure.parsers import get_parser_registry

    registry = parser_registry or get_parser_registry()
    # Note: These are async but we handle sync for now
    doc_store = document_store
    inv_store = invoice_store

    service = InvoiceParserService(
        parser_registry=registry,
        document_store=doc_store,
        invoice_store=inv_store,
    )

    if parser_registry is None:
        _invoice_parser_service = service

    return service


def get_invoice_auditor_service(
    llm_provider: "ILLMProvider | None" = None,
    invoice_store: "IInvoiceStore | None" = None,
) -> InvoiceAuditorService:
    """
    Get or create InvoiceAuditorService instance.

    Creates infrastructure dependencies if not provided.
    LLM provider is optional - audit degrades gracefully without it.

    Args:
        llm_provider: Optional LLM provider override
        invoice_store: Optional invoice store override

    Returns:
        Configured InvoiceAuditorService
    """
    global _invoice_auditor_service

    if _invoice_auditor_service is not None and llm_provider is None:
        return _invoice_auditor_service

    # Lazy import infrastructure
    from src.infrastructure.llm import get_llm_provider

    llm = llm_provider
    if llm is None:
        try:
            llm = get_llm_provider()
        except Exception:
            # LLM provider optional - graceful degradation
            llm = None

    service = InvoiceAuditorService(
        llm_provider=llm,
        invoice_store=invoice_store,
    )

    if llm_provider is None:
        _invoice_auditor_service = service

    return service


async def get_document_indexer_service(
    document_store: "IDocumentStore | None" = None,
    embedding_provider: "IEmbeddingProvider | None" = None,
    vector_store: "IVectorStore | None" = None,
) -> DocumentIndexerService:
    """
    Get or create DocumentIndexerService instance.

    Async because infrastructure initialization may be async.

    Args:
        document_store: Optional document store override
        embedding_provider: Optional embedding provider override
        vector_store: Optional vector store override

    Returns:
        Configured DocumentIndexerService
    """
    global _document_indexer_service

    if _document_indexer_service is not None and document_store is None:
        return _document_indexer_service

    # Lazy import infrastructure
    from src.infrastructure.embeddings import get_embedding_provider
    from src.infrastructure.storage.sqlite import get_document_store as get_doc_store
    from src.infrastructure.storage.vector import get_vector_store

    doc_store = document_store or await get_doc_store()
    embedder = embedding_provider or get_embedding_provider()
    vec_store = vector_store or get_vector_store()

    service = DocumentIndexerService(  # type: ignore[call-arg]
        document_store=doc_store,
        embedding_provider=embedder,
        vector_store=vec_store,
    )

    if document_store is None:
        _document_indexer_service = service

    return service


def get_search_service(
    searcher: "IHybridSearcher | None" = None,
    reranker: "IReranker | None" = None,
    cache: "ISearchCache | None" = None,
) -> SearchService:
    """
    Get or create SearchService instance.

    Reranker and cache are optional for graceful degradation.

    Args:
        searcher: Optional hybrid searcher override
        reranker: Optional reranker override
        cache: Optional search cache override

    Returns:
        Configured SearchService
    """
    global _search_service

    if _search_service is not None and searcher is None:
        return _search_service

    # Lazy import infrastructure
    from src.infrastructure.cache import get_search_cache
    from src.infrastructure.search import get_hybrid_searcher, get_reranker

    hybrid_searcher: IHybridSearcher = searcher or cast(IHybridSearcher, get_hybrid_searcher())

    # Optional components with graceful degradation
    result_reranker: IReranker | None = reranker
    if result_reranker is None:
        try:
            result_reranker = cast(IReranker, get_reranker())
        except Exception:
            result_reranker = None

    search_cache: ISearchCache | None = cache
    if search_cache is None:
        try:
            search_cache = cast(ISearchCache, get_search_cache())
        except Exception:
            search_cache = None

    service = SearchService(
        searcher=hybrid_searcher,
        reranker=result_reranker,
        cache=search_cache,
    )

    if searcher is None:
        _search_service = service

    return service


async def get_chat_service(
    session_store: "ISessionStore | None" = None,
    llm_provider: "ILLMProvider | None" = None,
    search_service: SearchService | None = None,
) -> ChatService:
    """
    Get or create ChatService instance.

    Async because session store initialization may be async.

    Args:
        session_store: Optional session store override
        llm_provider: Optional LLM provider override
        search_service: Optional search service override (for RAG)

    Returns:
        Configured ChatService
    """
    global _chat_service

    if _chat_service is not None and session_store is None:
        return _chat_service

    # Lazy import infrastructure
    from src.infrastructure.llm import get_llm_provider
    from src.infrastructure.storage.sqlite import get_session_store as get_sess_store

    sess_store = session_store or await get_sess_store()

    llm = llm_provider
    if llm is None:
        try:
            llm = get_llm_provider()
        except Exception:
            llm = None

    # Search service for RAG (optional)
    search = search_service
    if search is None:
        try:
            search = get_search_service()
        except Exception:
            search = None

    service = ChatService(
        session_store=sess_store,
        llm_provider=llm,  # type: ignore[arg-type]
        search_service=search,
    )

    if session_store is None:
        _chat_service = service

    return service


def reset_services() -> None:
    """
    Reset all singleton service instances.

    Useful for testing or when configuration changes.
    """
    global _invoice_parser_service
    global _invoice_auditor_service
    global _document_indexer_service
    global _search_service
    global _chat_service

    _invoice_parser_service = None
    _invoice_auditor_service = None
    _document_indexer_service = None
    _search_service = None
    _chat_service = None


__all__ = [
    # Factory functions
    "get_invoice_parser_service",
    "get_invoice_auditor_service",
    "get_document_indexer_service",
    "get_search_service",
    "get_chat_service",
    # Reset
    "reset_services",
]
