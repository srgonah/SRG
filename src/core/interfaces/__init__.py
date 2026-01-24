"""Core interfaces (ports) for dependency injection."""

from src.core.interfaces.llm import (
    HealthStatus,
    IEmbeddingProvider,
    ILLMProvider,
    IVisionProvider,
    LLMProvider,
    LLMResponse,
    VisionResponse,
)
from src.core.interfaces.parser import (
    IInvoiceParser,
    IParserRegistry,
    ITemplateDetector,
    ITextExtractor,
    ParserResult,
    TemplateMatch,
)
from src.core.interfaces.storage import (
    IDocumentStore,
    IIndexingStateStore,
    IInvoiceStore,
    ISessionStore,
    IVectorStore,
)

__all__ = [
    # LLM interfaces
    "ILLMProvider",
    "IVisionProvider",
    "IEmbeddingProvider",
    "LLMProvider",
    "LLMResponse",
    "VisionResponse",
    "HealthStatus",
    # Storage interfaces
    "IDocumentStore",
    "IInvoiceStore",
    "ISessionStore",
    "IVectorStore",
    "IIndexingStateStore",
    # Parser interfaces
    "IInvoiceParser",
    "ITemplateDetector",
    "ITextExtractor",
    "IParserRegistry",
    "ParserResult",
    "TemplateMatch",
]
