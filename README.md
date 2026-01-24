# SRG Invoice Processing API

A FastAPI microservice for invoice processing with RAG-powered chat capabilities.

## Features

- **Invoice Processing**: Upload, parse, and audit invoices
- **Document Indexing**: Full-text and semantic search with FAISS
- **RAG Chat**: Contextual chat using retrieved documents
- **Hybrid Search**: Combined FTS5 + vector search with reranking
- **Multi-LLM Support**: Switch between Ollama and llama-cpp

## Quick Start

### Prerequisites

- Python 3.11+
- Ollama (or llama-cpp-python)

### Installation

```bash
# Clone repository
cd SRG

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Run database migrations
make migrate

# Start development server
make dev
```

### Running with uv

```bash
uv sync
uv run uvicorn src.srg.main:app --reload
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/api/v1/health/detailed` | Detailed health status |
| POST | `/api/v1/invoices/upload` | Upload invoice |
| GET | `/api/v1/invoices` | List invoices |
| POST | `/api/v1/invoices/{id}/audit` | Audit invoice |
| POST | `/api/v1/documents/upload` | Upload document |
| GET | `/api/v1/documents` | List documents |
| POST | `/api/v1/search` | Search documents |
| GET | `/api/v1/search/quick?q=query` | Quick search |
| POST | `/api/v1/chat` | Send chat message |
| POST | `/api/v1/chat/stream` | Stream chat response |
| GET | `/api/v1/sessions` | List sessions |
| POST | `/api/v1/sessions` | Create session |

## Project Structure

```
SRG/
├── src/
│   ├── srg/                  # FastAPI microservice
│   │   ├── api/              # API routes
│   │   │   └── v1/endpoints/ # Versioned endpoints
│   │   ├── core/             # Security, database
│   │   ├── models/           # Database models
│   │   ├── schemas/          # Pydantic schemas
│   │   ├── services/         # Business logic
│   │   ├── config.py         # Settings
│   │   └── main.py           # FastAPI app
│   │
│   ├── core/                 # Domain layer
│   ├── infrastructure/       # Infrastructure
│   └── application/          # Use cases
│
├── tests/                    # Test suite
├── data/                     # Runtime data
├── templates/                # YAML templates
├── pyproject.toml
├── Makefile
└── README.md
```

## Configuration

Environment variables in `.env`:

```env
# LLM Provider
LLM_PROVIDER=ollama          # or llama_cpp
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Search
SEARCH_TOP_K=5
RERANKER_ENABLED=True

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
```

## Development

```bash
# Run tests
make test

# Run tests with coverage
make test-cov

# Lint code
make lint

# Format code
make format

# Type checking
make type-check
```

## Docker

```bash
# Build image
make docker-build

# Run container
make docker-run
```

## License

MIT
