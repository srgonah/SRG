"""Core interfaces (ports) for dependency injection."""

from src.core.interfaces.inventory_store import IInventoryStore
from src.core.interfaces.llm import (
    HealthStatus,
    IEmbeddingProvider,
    ILLMProvider,
    IVisionProvider,
    LLMProvider,
    LLMResponse,
    VisionResponse,
)
from src.core.interfaces.material_store import IMaterialStore
from src.core.interfaces.parser import (
    IInvoiceParser,
    IParserRegistry,
    ITemplateDetector,
    ITextExtractor,
    ParserResult,
    TemplateMatch,
)
from src.core.interfaces.price_history import IPriceHistoryStore
from src.core.interfaces.product_fetcher import IProductPageFetcher, ProductPageData
from src.core.interfaces.sales_store import ISalesStore
from src.core.interfaces.storage import (
    ICompanyDocumentStore,
    IDocumentStore,
    IHybridSearcher,
    IIndexingStateStore,
    IInvoiceStore,
    IReminderStore,
    IReranker,
    ISearchCache,
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
    "IInventoryStore",
    "ISalesStore",
    "IDocumentStore",
    "IInvoiceStore",
    "ISessionStore",
    "IMaterialStore",
    "IPriceHistoryStore",
    "ICompanyDocumentStore",
    "IReminderStore",
    "IVectorStore",
    "IIndexingStateStore",
    # Search interfaces
    "IHybridSearcher",
    "IReranker",
    "ISearchCache",
    # Product fetcher interfaces
    "IProductPageFetcher",
    "ProductPageData",
    # Parser interfaces
    "IInvoiceParser",
    "ITemplateDetector",
    "ITextExtractor",
    "IParserRegistry",
    "ParserResult",
    "TemplateMatch",
]
