# SRG - Invoice Processing System

An invoice processing system with OCR/PDF parsing, automated auditing, hybrid semantic search, and RAG-powered chat. Built with FastAPI, SQLite, FAISS, and a React dashboard.

## Features

- **Invoice Parsing** - Extract structured data from PDF and image invoices using text and vision-based parsers
- **Automated Auditing** - Validate invoices with rule-based and LLM-powered audit checks
- **Hybrid Search** - Combine FAISS vector search with SQLite FTS5 keyword search using Reciprocal Rank Fusion
- **RAG Chat** - Ask questions about your invoices with retrieval-augmented generation and streaming responses
- **React Dashboard** - Dark-themed UI with upload, search, invoice management, and chat (WCAG 2.1 AA compliant)

## Architecture

Clean Architecture with four layers. Dependencies flow inward only:

```
API (FastAPI) -> Application (Use Cases) -> Core (Entities/Services) -> Infrastructure (Implementations)
```

| Layer | Path | Purpose |
|-------|------|---------|
| **Core** | `src/core/` | Entities, interfaces (ABCs), exceptions, domain services |
| **Application** | `src/application/` | Use cases orchestrating core services |
| **Infrastructure** | `src/infrastructure/` | SQLite, FAISS, Ollama, llama.cpp implementations |
| **API** | `src/api/` | FastAPI routes, dependency injection, middleware |

## Tech Stack

**Backend**: Python 3.11+, FastAPI, SQLite (aiosqlite), FAISS, Ollama/llama.cpp, sentence-transformers, PyMuPDF

**Frontend**: React 18, TypeScript, Vite, Tailwind CSS, React Router

## Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (for dashboard)
- [Ollama](https://ollama.ai/) with `llama3.1:8b` model (or configure an alternative)

### Backend

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Run database migrations
python -m src.infrastructure.storage.sqlite.migrations.migrator

# Start the API server
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

The API will be available at `http://localhost:8000` with interactive docs at `/docs`.

### Dashboard

```bash
cd dashboard
npm install
npm run dev
```

The dashboard will be available at `http://localhost:3001`.

### Configuration

Settings are loaded from environment variables with sensible defaults:

| Prefix | Section | Example |
|--------|---------|---------|
| `LLM_` | LLM provider | `LLM_MODEL_NAME=llama3.1:8b` |
| `EMBED_` | Embeddings | `EMBED_MODEL_NAME=BAAI/bge-m3` |
| `STORAGE_` | Storage paths | `STORAGE_DATA_DIR=data` |
| `SEARCH_` | Search tuning | `SEARCH_TOP_K=10` |

See [docs/configuration-reference.md](docs/configuration-reference.md) for the full reference.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/invoices/upload` | Upload and parse an invoice |
| `GET` | `/api/invoices` | List invoices |
| `GET` | `/api/invoices/{id}` | Get invoice details |
| `POST` | `/api/invoices/audit` | Audit an invoice |
| `POST` | `/api/search` | Hybrid search across documents |
| `POST` | `/api/chat` | Send a chat message (RAG) |
| `POST` | `/api/chat/stream` | Stream a chat response |
| `GET` | `/api/sessions` | List chat sessions |
| `GET` | `/api/sessions/{id}/messages` | Get session messages |

See [docs/api-reference.md](docs/api-reference.md) for full API documentation.

## Development

```bash
# Run all tests (630 tests)
pytest -v

# Run a specific test file
pytest tests/unit/services/test_chat_service_session_flow.py -v

# Lint and format
ruff check src tests
ruff format src tests

# Type checking
mypy src
```

## Project Structure

```
src/
  api/              # FastAPI routes, middleware, dependency injection
  application/      # Use cases (upload, chat, search, audit)
  core/             # Entities, interfaces, exceptions, domain services
  config/           # Pydantic settings
  infrastructure/
    llm/            # Ollama and llama.cpp providers
    search/         # FAISS vector store, FTS5, hybrid search, reranker
    storage/        # SQLite stores, document storage, migrations

dashboard/
  src/
    pages/          # Dashboard, Upload, Invoices, InvoiceDetail, Search, Chat
    components/     # Layout, shared components
    api/            # API client
    hooks/          # Custom React hooks

tests/
  unit/             # Unit tests (mocked interfaces)
  integration/      # Integration tests (real SQLite, mocked LLM)

docs/               # Architecture, API reference, user guide, configuration
```

## Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [API Reference](docs/api-reference.md)
- [Configuration Reference](docs/configuration-reference.md)
- [User Guide](docs/user-guide.md)
- [Contributing](docs/CONTRIBUTING.md)
- [Accessibility Audit](docs/accessibility-audit-report.md)

## License

MIT
