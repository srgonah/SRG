# SRG Architecture Diagrams

Visual architecture reference with Mermaid diagrams. For detailed text descriptions, see [ARCHITECTURE.md](./ARCHITECTURE.md).

---

## System Overview

```mermaid
graph TB
    subgraph "Clients"
        WEB[Web Dashboard<br/>React + Vite]
        API_CLIENT[API Clients<br/>curl / SDK]
    end

    subgraph "API Layer"
        FASTAPI[FastAPI Application<br/>port 8000]
        MW[Middleware<br/>Logging + Error Handling]
        ROUTES[Route Modules<br/>chat, invoices, search,<br/>sessions, documents, health]
    end

    subgraph "Application Layer"
        UC_UPLOAD[UploadInvoiceUseCase]
        UC_AUDIT[AuditInvoiceUseCase]
        UC_CHAT[ChatWithContextUseCase]
        UC_SEARCH[SearchDocumentsUseCase]
    end

    subgraph "Core Domain"
        ENT[Entities<br/>Invoice, Document,<br/>ChatSession]
        SVC[Services<br/>ChatService, SearchService,<br/>ParserService, AuditorService,<br/>DocumentIndexer]
        IFC[Interfaces / ABCs<br/>ILLMProvider, IVectorStore,<br/>IDocumentStore, IInvoiceParser]
    end

    subgraph "Infrastructure"
        direction LR
        OLLAMA[Ollama<br/>LLM + Vision]
        LLAMA[llama.cpp<br/>Local LLM]
        BGE[bge-m3<br/>Embeddings]
        SQLITE[(SQLite<br/>+ FTS5)]
        FAISS[(FAISS<br/>Vector Index)]
        PARSERS[Parser Registry<br/>Template / Table / Vision]
        RERANKER[bge-reranker<br/>v2-m3]
    end

    WEB --> FASTAPI
    API_CLIENT --> FASTAPI
    FASTAPI --> MW --> ROUTES
    ROUTES --> UC_UPLOAD
    ROUTES --> UC_AUDIT
    ROUTES --> UC_CHAT
    ROUTES --> UC_SEARCH
    UC_UPLOAD --> SVC
    UC_AUDIT --> SVC
    UC_CHAT --> SVC
    UC_SEARCH --> SVC
    SVC --> IFC
    IFC --> OLLAMA
    IFC --> LLAMA
    IFC --> BGE
    IFC --> SQLITE
    IFC --> FAISS
    IFC --> PARSERS
    IFC --> RERANKER
```

---

## Clean Architecture Layers

```
┌──────────────────────────────────────────────────┐
│  API Layer (src/api/)                            │
│  FastAPI routes, middleware, dependency injection │
├──────────────────────────────────────────────────┤
│  Application Layer (src/application/)            │
│  Use cases, DTOs (request/response schemas)      │
├──────────────────────────────────────────────────┤
│  Core Layer (src/core/)                          │
│  Entities, interfaces (ABCs), domain services    │
│  *** ZERO external dependencies ***              │
├──────────────────────────────────────────────────┤
│  Infrastructure Layer (src/infrastructure/)      │
│  SQLite, FAISS, Ollama, parsers, cache           │
└──────────────────────────────────────────────────┘

  Dependencies flow INWARD only:
  API → Application → Core ← Infrastructure
```

---

## Invoice Upload Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant UC as UploadInvoiceUseCase
    participant DS as DocumentStore
    participant PS as ParserService
    participant IS as InvoiceStore
    participant AS as AuditorService
    participant DI as DocumentIndexer

    C->>R: POST /api/invoices/upload (PDF)
    R->>UC: execute(file, options)
    UC->>DS: save_document(file)
    DS-->>UC: document_id

    UC->>PS: parse(document)
    Note over PS: Try parsers by priority:<br/>1. Template (100)<br/>2. Table (80)<br/>3. Vision (60)
    PS-->>UC: invoice + line_items

    UC->>IS: save_invoice(invoice)
    IS-->>UC: invoice_id

    alt auto_audit enabled
        UC->>AS: audit(invoice)
        Note over AS: Rule-based checks +<br/>optional LLM analysis
        AS-->>UC: audit_result
    end

    alt auto_index enabled
        UC->>DI: index(document)
        Note over DI: Chunk → Embed → FAISS
        DI-->>UC: indexed
    end

    UC-->>R: UploadInvoiceResponse
    R-->>C: 200 OK (JSON)
```

---

## RAG Chat Flow

```mermaid
sequenceDiagram
    participant C as Client
    participant R as Route
    participant UC as ChatWithContextUseCase
    participant SS as SessionStore
    participant SE as SearchService
    participant LLM as LLM Provider

    C->>R: POST /api/chat {message, session_id}
    R->>UC: execute(request)

    alt session_id is null
        UC->>SS: create_session()
        SS-->>UC: new session
    else
        UC->>SS: get_session(session_id)
        SS-->>UC: existing session
    end

    UC->>SS: add_message(user_message)

    alt use_rag enabled
        UC->>SE: hybrid_search(message, top_k)
        Note over SE: FAISS vector search<br/>+ FTS5 keyword search<br/>+ RRF fusion<br/>+ optional reranking
        SE-->>UC: context chunks + citations
    end

    UC->>LLM: generate(prompt + context + history)
    LLM-->>UC: assistant response

    UC->>SS: add_message(assistant_response)
    UC-->>R: ChatResponse
    R-->>C: 200 OK (JSON)
```

---

## Hybrid Search Pipeline

```mermaid
flowchart LR
    Q[Query] --> EMB[Embed Query<br/>bge-m3]
    Q --> FTS[FTS5 Keyword<br/>Search]

    EMB --> FAISS[FAISS Vector<br/>Search]
    FAISS --> |top 60| RRF[Reciprocal Rank<br/>Fusion]
    FTS --> |top 60| RRF

    RRF --> RR{Reranker<br/>enabled?}
    RR -->|Yes| RERANK[bge-reranker<br/>v2-m3]
    RR -->|No| OUT[Results]
    RERANK --> OUT
```

**RRF Formula**: `score(d) = Σ 1 / (k + rank_i(d))` where `k = 60` (configurable via `SEARCH_RRF_K`)

---

## Parser Registry (Strategy Pattern)

```mermaid
flowchart TD
    DOC[Document] --> REG[Parser Registry]

    REG --> |Priority 100| TP[Template Parser<br/>Known vendor templates]
    REG --> |Priority 80| TAP[Table-Aware Parser<br/>Table detection + extraction]
    REG --> |Priority 60| VP[Vision Parser<br/>Multimodal LLM fallback]

    TP --> |Success?| CHK1{confidence > 0.7?}
    CHK1 -->|Yes| DONE[Return Invoice]
    CHK1 -->|No| TAP

    TAP --> |Success?| CHK2{confidence > 0.5?}
    CHK2 -->|Yes| DONE
    CHK2 -->|No| VP

    VP --> |Always tried last| DONE
```

---

## LLM Circuit Breaker

```mermaid
stateDiagram-v2
    [*] --> Closed
    Closed --> Open: failures >= 3
    Open --> HalfOpen: cooldown 60s expires
    HalfOpen --> Closed: success
    HalfOpen --> Open: failure

    state Closed {
        [*] --> Healthy
        Healthy --> Counting: failure
        Counting --> Healthy: success resets counter
    }
```

---

## Entity Relationship Diagram

```mermaid
erDiagram
    Document ||--o{ Page : has
    Document ||--o{ Chunk : has
    Page ||--o{ Chunk : contains
    Document ||--o| Invoice : parsed_from
    Invoice ||--o{ LineItem : has
    Invoice ||--o{ AuditResult : audited_by
    AuditResult ||--o{ AuditFinding : contains
    ChatSession ||--o{ Message : contains
    ChatSession ||--o{ MemoryFact : remembers

    Document {
        string id PK
        string filename
        string file_hash
        string status
        int page_count
    }

    Invoice {
        string id PK
        string document_id FK
        string invoice_number
        string vendor_name
        float total_amount
        float confidence
    }

    LineItem {
        string id PK
        string invoice_id FK
        string description
        float quantity
        float unit_price
        float total_price
    }

    AuditResult {
        string id PK
        string invoice_id FK
        bool passed
        string status
        int error_count
    }

    ChatSession {
        string session_id PK
        string title
        int message_count
    }

    Message {
        string id PK
        string session_id FK
        string role
        string content
    }

    Chunk {
        string id PK
        string document_id FK
        string chunk_text
        int faiss_id
    }
```

---

## Exception Hierarchy

```mermaid
classDiagram
    SRGError <|-- StorageError
    SRGError <|-- ChatError
    SRGError <|-- SearchError
    SRGError <|-- ParsingError
    SRGError <|-- AuditError
    SRGError <|-- LLMError
    StorageError <|-- DocumentNotFoundError
    StorageError <|-- InvoiceNotFoundError
    StorageError <|-- SessionNotFoundError
    StorageError <|-- DuplicateDocumentError

    class SRGError {
        +str message
        +str code
        +dict details
        +to_dict()
    }
```

---

## Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Framework | FastAPI | Async HTTP API |
| Database | SQLite + aiosqlite | Structured data (27 tables) |
| Full-Text Search | SQLite FTS5 | Keyword search (BM25) |
| Vector Store | FAISS | Semantic similarity search |
| Embeddings | BAAI/bge-m3 | Multilingual embeddings (dim=1024) |
| LLM | Ollama / llama.cpp | Text generation + vision |
| Reranker | BAAI/bge-reranker-v2-m3 | Search result reranking |
| Validation | Pydantic v2 | Request/response schemas |
| Logging | structlog | Structured JSON logging |
| Dashboard | React + Vite + Tailwind | Web UI |
