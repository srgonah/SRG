# SRG - Invoice Processing System

An invoice processing system with OCR/PDF parsing, automated auditing, hybrid semantic search, RAG-powered chat, inventory management, and sales tracking. Built with FastAPI, SQLite, FAISS, and a React + Material-UI dashboard.

## Features

- **Invoice Parsing** - Extract structured data from PDF and image invoices using text and vision-based parsers
- **Automated Auditing** - Validate invoices with rule-based and LLM-powered audit checks
- **Hybrid Search** - Combine FAISS vector search with SQLite FTS5 keyword search using Reciprocal Rank Fusion
- **RAG Chat** - Ask questions about your invoices with retrieval-augmented generation and streaming responses
- **Material Catalog** - Manage materials with fuzzy matching to invoice line items and Amazon product import
- **Inventory Management** - Track stock levels with movement history, low-stock alerts, and categorization
- **Sales Tracking** - Record sales transactions linked to inventory with automatic stock updates
- **Price History** - Track price changes over time with anomaly detection
- **Company Documents** - Manage business documents with expiration tracking and renewal reminders
- **Proforma Invoices** - Generate professional PDF proforma invoices
- **React Dashboard** - Material-UI based dark-themed dashboard (WCAG 2.1 AA compliant)

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

**Backend**: Python 3.11+, FastAPI, SQLite (aiosqlite), FAISS, Ollama/llama.cpp, sentence-transformers, PyMuPDF, fpdf2

**Frontend**: React 18, TypeScript, Vite, Material-UI (MUI), React Router, Vitest

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

### Unified Serving (Recommended)

Use `manage.py` to build the dashboard and serve everything from one host:

```bash
python manage.py start          # Build dashboard + start on :8000
python manage.py start --port 9000 --skip-build
python manage.py stop            # Graceful shutdown
python manage.py restart         # Stop + start
python manage.py status          # Check if running
python manage.py build           # Build dashboard only
python manage.py dev             # Backend (reload) + Vite dev server
```

Visit `http://localhost:8000` for the dashboard and API.

### Dashboard (standalone dev server)

```bash
cd webui
npm install
npm run dev
```

The dashboard dev server will be available at `http://localhost:5173` (proxies API to `:8000`).

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

### Core
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/health` | Health check with component status |
| `POST` | `/api/invoices/upload` | Upload and parse an invoice |
| `GET` | `/api/invoices` | List invoices with filtering |
| `GET` | `/api/invoices/{id}` | Get invoice details with line items |
| `POST` | `/api/invoices/{id}/audit` | Audit an invoice |
| `POST` | `/api/search` | Hybrid search across documents |
| `POST` | `/api/chat` | Send a chat message (RAG) |
| `POST` | `/api/chat/stream` | Stream a chat response |

### Catalog & Materials
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/catalog` | List materials with search |
| `POST` | `/api/catalog` | Create a new material |
| `GET` | `/api/catalog/{id}/matches` | Get fuzzy matches for a material |
| `POST` | `/api/amazon-import` | Import materials from Amazon URLs |

### Inventory & Sales
| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/inventory` | List inventory items |
| `POST` | `/api/inventory` | Create inventory item |
| `GET` | `/api/inventory/low-stock` | Get low stock alerts |
| `GET` | `/api/sales` | List sales transactions |
| `POST` | `/api/sales` | Record a sale |

### Documents & More
| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/api/documents/upload` | Upload and index a document |
| `GET` | `/api/documents` | List indexed documents |
| `GET` | `/api/company-documents` | List company documents |
| `GET` | `/api/reminders` | List reminders |
| `POST` | `/api/creators/proforma` | Generate proforma PDF |

See [docs/api-reference.md](docs/api-reference.md) for full API documentation.

## Development

```bash
# Run all backend tests (1153 tests)
pytest -v

# Run frontend tests
cd webui && npm test

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
    routes/         # Invoice, catalog, inventory, sales, documents, chat, search
  application/      # Use cases and service factories
  core/             # Entities, interfaces, exceptions, domain services
  config/           # Pydantic settings
  infrastructure/
    llm/            # Ollama and llama.cpp providers
    search/         # FAISS vector store, FTS5, hybrid search, reranker
    storage/        # SQLite stores, document storage, migrations
    pdf/            # PDF generation (proforma invoices)
    scrapers/       # Amazon product fetcher

webui/              # Material-UI React dashboard
  src/
    pages/          # Dashboard, Invoices, Catalog, Inventory, Sales, Documents, Chat
    components/     # Layout, shared components
    api/            # API client
    hooks/          # Custom React hooks

tests/
  unit/             # Unit tests (mocked interfaces)
  integration/      # Integration tests (real SQLite, mocked LLM)

docs/               # Architecture, API reference, user guide, configuration
tools/              # PowerShell scripts for Windows development
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
