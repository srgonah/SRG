# SRG Architecture Documentation

## Overview

SRG follows **Clean Architecture** principles with clear separation between layers. This document explains the architectural decisions and patterns used.

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                       API Layer (FastAPI)                       │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌────────────┐│
│  │  /invoices  │ │  /search    │ │   /chat     │ │ /documents ││
│  └─────────────┘ └─────────────┘ └─────────────┘ └────────────┘│
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                   Application Layer (Use Cases)                  │
│  ┌─────────────────┐ ┌─────────────────┐ ┌───────────────────┐ │
│  │ UploadInvoice   │ │ SearchDocuments │ │ ChatWithContext   │ │
│  │ AuditInvoice    │ │                 │ │                   │ │
│  └─────────────────┘ └─────────────────┘ └───────────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                      Core Layer (Domain)                         │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────┐ │
│  │  Entities  │ │  Services  │ │ Interfaces │ │  Exceptions  │ │
│  │  - Invoice │ │  - Parser  │ │  - ILLMPr  │ │  - ParserErr │ │
│  │  - Document│ │  - Auditor │ │  - IStore  │ │  - SearchErr │ │
│  │  - Session │ │  - Search  │ │  - IParser │ │  - LLMError  │ │
│  └────────────┘ └────────────┘ └────────────┘ └──────────────┘ │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                  Infrastructure Layer (Adapters)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌───────┐ │
│  │   LLM    │ │ Embeddings│ │  Storage │ │  Search  │ │ Cache │ │
│  │- Ollama  │ │- BGE-M3   │ │- SQLite  │ │- Hybrid  │ │- LRU  │ │
│  │- LlamaCpp│ │           │ │- FAISS   │ │- Reranker│ │- Disk │ │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └───────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Layer Details

### 1. API Layer

**Location**: `src/api/`, `src/srg/api/`

**Purpose**: Handle HTTP requests, validation, and routing.

**Components**:
- **Routes**: Endpoint definitions (invoices, search, chat, etc.)
- **Middleware**: Logging, error handling, CORS
- **Dependencies**: FastAPI dependency injection

**Key Patterns**:
```python
# Dependency injection
@router.post("/invoices/upload")
async def upload_invoice(
    file: UploadFile,
    use_case: UploadInvoiceUseCase = Depends(get_upload_use_case),
):
    return await use_case.execute(file)
```

### 2. Application Layer

**Location**: `src/application/`

**Purpose**: Orchestrate business workflows (use cases).

**Components**:
- **Use Cases**: Business workflow implementations
- **DTOs**: Request/Response data transfer objects

**Pattern**:
```python
class UploadInvoiceUseCase:
    def __init__(self, parser, auditor, indexer):
        self._parser = parser
        self._auditor = auditor
        self._indexer = indexer

    async def execute(self, file, filename, request) -> UploadResult:
        # Orchestrate the workflow
        document = await self._indexer.index_document(file)
        invoice = await self._parser.parse_invoice(document)
        audit = await self._auditor.audit_invoice(invoice)
        return UploadResult(invoice, document, audit)
```

### 3. Core Layer

**Location**: `src/core/`

**Purpose**: Pure business logic with no external dependencies.

**Components**:

#### Entities
Domain models with business logic:
```python
class Invoice(BaseModel):
    id: str
    invoice_number: str
    line_items: list[LineItem]

    @computed_field
    def calculated_total(self) -> float:
        return sum(item.total_price for item in self.line_items)
```

#### Services
Business logic orchestration:
```python
class InvoiceParserService:
    def __init__(self, parser_registry):
        self._registry = parser_registry

    async def parse_invoice(self, document, pages) -> Invoice:
        for parser in self._registry.get_parsers_by_priority():
            result = await parser.parse(document)
            if result:
                return result
        raise ParserError("All parsers failed")
```

#### Interfaces
Abstract contracts for infrastructure:
```python
class ILLMProvider(ABC):
    @abstractmethod
    async def generate(self, prompt: str, **kwargs) -> str:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass
```

### 4. Infrastructure Layer

**Location**: `src/infrastructure/`

**Purpose**: Implement interfaces with external systems.

**Components**:

#### LLM Providers
```python
class OllamaProvider(ILLMProvider):
    async def generate(self, prompt: str, **kwargs) -> str:
        response = await self._client.post("/api/generate", json={...})
        return response.json()["response"]
```

#### Storage
```python
class InvoiceStore(IInvoiceStore):
    async def save_invoice(self, invoice: Invoice) -> None:
        async with self._pool.connection() as conn:
            await conn.execute("INSERT INTO invoices ...", invoice.dict())
```

## Key Design Patterns

### 1. Dependency Injection

All services use constructor-based dependency injection:

```python
# Service with dependencies
class SearchService:
    def __init__(
        self,
        searcher: HybridSearcher,
        reranker: Reranker,
        cache: SearchCache,
    ):
        self._searcher = searcher
        self._reranker = reranker
        self._cache = cache
```

### 2. Factory Pattern

Used for creating LLM providers based on configuration:

```python
def get_llm_provider() -> ILLMProvider:
    settings = get_settings()
    if settings.LLM_PROVIDER == "ollama":
        return OllamaProvider()
    elif settings.LLM_PROVIDER == "llama_cpp":
        return LlamaCppProvider()
    raise ConfigurationError(f"Unknown provider: {settings.LLM_PROVIDER}")
```

### 3. Strategy Pattern

Used for parser selection:

```python
class ParserRegistry:
    def get_parsers_by_priority(self) -> list[IInvoiceParser]:
        return sorted(self._parsers, key=lambda p: p.priority, reverse=True)
```

### 4. Circuit Breaker

Protects against cascading failures:

```python
class CircuitBreakerMixin:
    def __init__(self, failure_threshold=3, recovery_timeout=60):
        self._failures = 0
        self._threshold = failure_threshold
        self._timeout = recovery_timeout
        self._last_failure = None

    async def call_with_breaker(self, func):
        if self._is_open:
            raise CircuitOpenError()
        try:
            result = await func()
            self._failures = 0
            return result
        except Exception:
            self._failures += 1
            self._last_failure = time.time()
            raise
```

### 5. Repository Pattern

Used for data access:

```python
class IInvoiceStore(ABC):
    @abstractmethod
    async def save_invoice(self, invoice: Invoice) -> None: ...

    @abstractmethod
    async def get_invoice(self, invoice_id: str) -> Optional[Invoice]: ...

    @abstractmethod
    async def list_invoices(self, limit: int, offset: int) -> list[Invoice]: ...
```

## Data Flow

### Invoice Upload Flow

```
1. HTTP Request (multipart/form-data)
       ↓
2. API Route validates request
       ↓
3. UploadInvoiceUseCase orchestrates:
   a. DocumentIndexerService extracts text
   b. InvoiceParserService parses invoice
   c. InvoiceAuditorService audits (optional)
   d. InvoiceStore persists data
       ↓
4. HTTP Response (JSON)
```

### Search Flow

```
1. Search Query
       ↓
2. SearchService orchestrates:
   a. EmbeddingProvider generates query embedding
   b. FAISSStore performs vector search
   c. FTSSearcher performs keyword search
   d. HybridSearcher combines with RRF
   e. Reranker re-scores top results
       ↓
3. Ranked Results
```

### Chat Flow

```
1. User Message
       ↓
2. ChatService:
   a. SearchService retrieves context (RAG)
   b. Prompt is built with context + history
   c. LLMProvider generates response
   d. Memory facts extracted
   e. Message stored
       ↓
3. Assistant Response
```

## Configuration

### Settings Hierarchy

```python
class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    # Grouped settings
    llm: LLMSettings
    embedding: EmbeddingSettings
    storage: StorageSettings
    search: SearchSettings
```

### Environment-Based Config

```
.env (local development)
    ↓
Environment variables (production)
    ↓
Settings class with validation
```

## Error Handling

### Exception Hierarchy

```
SRGError (base)
├── StorageError
├── LLMError
├── ParserError
├── SearchError
├── ValidationError
├── ConfigurationError
├── AuditError
├── IndexingError
└── ChatError
```

### Middleware Handling

```python
class ErrorHandlerMiddleware:
    async def dispatch(self, request, call_next):
        try:
            return await call_next(request)
        except SRGError as e:
            return self._handle_domain_error(e)
        except Exception as e:
            return self._handle_unexpected_error(e)
```

## Testing Strategy

### Test Pyramid

```
     /\
    /  \     E2E Tests (few)
   /----\
  /      \   Integration Tests
 /--------\
/          \ Unit Tests (many)
```

### Test Organization

```
tests/
├── conftest.py          # Shared fixtures
├── api/                 # API integration tests
│   ├── test_invoices.py
│   ├── test_search.py
│   └── test_chat.py
├── unit/                # Unit tests
│   ├── test_parser.py
│   └── test_auditor.py
└── integration/         # Integration tests
    └── test_full_flow.py
```

## Performance Considerations

### Caching

- **Embedding Cache**: LRU cache for embeddings (10,000 items)
- **Search Cache**: TTL-based cache for search results (300s)
- **Disk Cache**: Vision processing results

### Async Operations

- All I/O operations are async
- Connection pooling for database
- Batch processing for embeddings

### Indexing

- Incremental FAISS updates
- Background indexing for large documents

## Security

### Input Validation

- Pydantic models validate all inputs
- File type checking for uploads
- Size limits on requests

### Secrets Management

- Environment variables for secrets
- No secrets in code or logs
- Secret rotation support

---

*Last updated: January 2026*
