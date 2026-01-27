# SRG User Guide

A practical guide to installing, configuring, and using the SRG Invoice Processing System.

---

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Installation](#installation)
3. [Starting the Server](#starting-the-server)
4. [Web Dashboard](#web-dashboard)
5. [Uploading Invoices](#uploading-invoices)
6. [Searching Documents](#searching-documents)
7. [Chat with RAG](#chat-with-rag)
8. [Auditing Invoices](#auditing-invoices)
9. [Managing Sessions](#managing-sessions)
10. [CLI Scripts](#cli-scripts)
11. [Troubleshooting](#troubleshooting)

---

## Prerequisites

| Requirement | Version | Purpose |
|-------------|---------|---------|
| Python | 3.11+ | Runtime |
| Ollama | latest | LLM and vision models |
| Node.js | 18+ | Dashboard (optional) |
| CUDA toolkit | 11.8+ | GPU embeddings (optional) |

### Install Ollama

```bash
# Download from https://ollama.com
# Then pull the required models:
ollama pull llama3.1:8b
ollama pull llava:13b
```

Verify Ollama is running:

```bash
curl http://localhost:11434/api/tags
```

---

## Installation

### 1. Clone and Enter the Project

```bash
cd SRG
```

### 2. Create a Virtual Environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
# Standard install (with dev tools)
pip install -e ".[dev]"

# GPU support (optional)
pip install -e ".[dev,gpu]"
```

### 4. Configure Environment

```bash
cp .env.example .env
```

Edit `.env` to match your setup. Key settings:

```bash
LLM_PROVIDER=ollama
LLM_HOST=http://localhost:11434
LLM_MODEL_NAME=llama3.1:8b
EMBED_DEVICE=cuda   # or "cpu" if no GPU
```

See [Configuration Reference](./configuration-reference.md) for all options.

### 5. Initialize the Database

```bash
python -m src.infrastructure.storage.sqlite.migrations.migrator
```

This creates the SQLite database with 27 tables at `data/srg.db`.

---

## Starting the Server

### Development Mode

```bash
uvicorn src.api.main:app --reload --host 0.0.0.0 --port 8000
```

### Using the CLI Entry Point

```bash
srg
```

### Verify the Server

```bash
curl http://localhost:8000/api/health
```

Expected response:

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "uptime_seconds": 5.2
}
```

Check all subsystems:

```bash
curl http://localhost:8000/api/health/full
```

### Interactive API Docs

Open in your browser: `http://localhost:8000/docs` (Swagger UI)

---

## Web Dashboard

SRG includes a React dashboard with pages for upload, search, chat, and invoice management.

### Start the Dashboard

```bash
cd dashboard
npm install
npm run dev
```

The dashboard runs at `http://localhost:3000` (or next available port) and proxies API requests to the backend at port 8000.

### Dashboard Pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | System status, quick actions, recent activity |
| Upload | `/upload` | Drag-and-drop invoice upload with parsing options |
| Invoices | `/invoices` | Paginated list with confidence scores |
| Invoice Detail | `/invoices/:id` | Full details, line items, audit results |
| Search | `/search` | Hybrid/semantic/keyword search with reranker toggle |
| Chat | `/chat` | Session-based RAG chat with streaming |

---

## Uploading Invoices

### Via Dashboard

1. Go to the **Upload** page
2. Drag a PDF/PNG/JPG file into the upload area (or click to browse)
3. Optionally set:
   - **Vendor hint** — helps template matching
   - **Auto audit** — run audit checks automatically
   - **Auto index** — make the document searchable
4. Click **Upload**

### Via API

```bash
curl -X POST http://localhost:8000/api/invoices/upload \
  -F "file=@invoice.pdf" \
  -F "vendor_hint=VOLTA HUB" \
  -F "auto_audit=true" \
  -F "auto_index=true"
```

### What Happens During Upload

1. **Document saved** — file stored and hash recorded (duplicates rejected)
2. **Parsing** — parsers tried in priority order:
   - Template parser (priority 100) — matches known vendor layouts
   - Table-aware parser (priority 80) — detects table structures
   - Vision parser (priority 60) — multimodal LLM fallback
3. **Invoice persisted** — extracted fields and line items saved
4. **Audit** (if enabled) — rule-based + optional LLM analysis
5. **Indexing** (if enabled) — document chunked, embedded, added to FAISS

### Supported File Types

- PDF (text-based and scanned)
- PNG, JPG, JPEG (processed via vision model)

Maximum file size: 50 MB (configurable via `API_MAX_UPLOAD_SIZE`).

---

## Searching Documents

### Via Dashboard

1. Go to the **Search** page
2. Enter a query (e.g., "PVC cable 4mm prices")
3. Choose search type:
   - **Hybrid** (default) — combines semantic + keyword search
   - **Semantic** — vector similarity only
   - **Keyword** — FTS5 full-text search only
4. Toggle **Reranker** for improved relevance ranking
5. View results with scores, metadata, and highlighted snippets

### Via API

```bash
# Full search
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"query": "cable prices", "top_k": 10, "search_type": "hybrid"}'

# Quick search (GET)
curl "http://localhost:8000/api/search/quick?q=cable+prices&top_k=5"
```

### How Hybrid Search Works

1. Query is embedded using bge-m3 → FAISS returns top-60 vector matches
2. Query runs through SQLite FTS5 → returns top-60 keyword matches
3. Reciprocal Rank Fusion (RRF) merges both result sets
4. Optional: bge-reranker-v2-m3 re-scores the merged results
5. Top-k results returned with scores and metadata

---

## Chat with RAG

### Via Dashboard

1. Go to the **Chat** page
2. Create a new session or select an existing one from the sidebar
3. Type a message and press Enter or click Send
4. The assistant responds with context from your indexed documents
5. Citations appear below each response showing source documents

### Via API

```bash
# Start a new conversation
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "What was the total from VOLTA HUB?",
    "use_rag": true,
    "top_k": 5
  }'

# Continue in the same session
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Break it down by line item",
    "session_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  }'
```

### Streaming Chat

The chat endpoint supports Server-Sent Events (SSE) for token-by-token streaming:

```bash
curl -N http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{"message": "Summarize all invoices", "stream": true}'
```

### Chat Features

- **Session persistence** — conversations are saved and resumable
- **RAG context** — relevant document chunks injected into prompts
- **Memory extraction** — facts about user preferences are remembered
- **Source citations** — each response includes document references
- **Context preview** — test what context a query retrieves without generating a response:

```bash
curl "http://localhost:8000/api/chat/context?query=cable+prices&top_k=5"
```

---

## Auditing Invoices

Auditing validates parsed invoice data using rule-based checks and optional LLM analysis.

### Automatic Audit

Enabled by default during upload (`auto_audit=true`). Runs immediately after parsing.

### Manual Audit

```bash
curl -X POST http://localhost:8000/api/invoices/{invoice_id}/audit \
  -H "Content-Type: application/json" \
  -d '{"use_llm": true, "strict_mode": false}'
```

### Audit Checks

- Line item totals match (quantity x unit_price = line total)
- Subtotal matches sum of line items
- Tax calculation verification
- Total = subtotal + tax
- Date validity (not in the future, due date after invoice date)
- LLM semantic analysis (when enabled) — checks for anomalies

### Audit Results

Each audit produces:
- **passed** — boolean overall result
- **findings** — list of errors and warnings with details
- **confidence** — overall confidence score
- **summary** — human-readable summary

View audit history:

```bash
curl http://localhost:8000/api/invoices/{invoice_id}/audits
```

---

## Managing Sessions

### List All Sessions

```bash
curl http://localhost:8000/api/sessions
```

### Create a Session

```bash
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"title": "Q1 Invoice Review"}'
```

### View Session Messages

```bash
curl http://localhost:8000/api/sessions/{session_id}/messages
```

### Generate Session Summary

```bash
curl http://localhost:8000/api/sessions/{session_id}/summary
```

### Delete a Session

```bash
curl -X DELETE http://localhost:8000/api/sessions/{session_id}
```

---

## CLI Scripts

SRG provides command-line scripts defined in `pyproject.toml`:

| Command | Description |
|---------|-------------|
| `srg` | Start the API server |
| `srg-migrate` | Run database migrations |
| `srg-index` | Rebuild FAISS vector indexes |

### Bulk Index a Directory

```bash
curl -X POST http://localhost:8000/api/documents/index-directory \
  -H "Content-Type: application/json" \
  -d '{
    "directory": "/path/to/invoices",
    "recursive": true,
    "extensions": [".pdf", ".txt"]
  }'
```

### Reindex a Single Document

```bash
curl -X POST http://localhost:8000/api/documents/{document_id}/reindex
```

### Check Index Stats

```bash
curl http://localhost:8000/api/documents/stats
```

---

## Troubleshooting

### Server won't start

**Symptom**: `ModuleNotFoundError`

```bash
# Make sure virtual environment is active
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Reinstall
pip install -e ".[dev]"
```

### LLM not responding

**Symptom**: `503 LLMError — LLM provider unavailable`

```bash
# Check Ollama is running
curl http://localhost:11434/api/tags

# If not running, start it
ollama serve

# Pull the required model
ollama pull llama3.1:8b
```

The circuit breaker may be open after 3 consecutive failures. Wait 60 seconds (configurable via `LLM_COOLDOWN_SECONDS`) or restart the server.

### Embedding model slow on CPU

**Symptom**: Indexing and search take a long time

Set `EMBED_DEVICE=cuda` in `.env` if you have an NVIDIA GPU. Install GPU dependencies:

```bash
pip install -e ".[gpu]"
```

### Duplicate document error

**Symptom**: `409 DuplicateDocumentError`

The same file (by hash) has already been indexed. To reindex:

```bash
curl -X POST http://localhost:8000/api/documents/{document_id}/reindex
```

### Search returns no results

1. Verify documents are indexed:
   ```bash
   curl http://localhost:8000/api/documents/stats
   ```
2. Check that FAISS index has vectors (the `vectors` count should be > 0)
3. Try keyword search to rule out embedding issues:
   ```bash
   curl -X POST http://localhost:8000/api/search \
     -H "Content-Type: application/json" \
     -d '{"query": "test", "search_type": "keyword"}'
   ```

### Database locked errors

**Symptom**: `database is locked`

Increase the busy timeout:

```bash
STORAGE_BUSY_TIMEOUT=60000  # 60 seconds
```

Or increase the connection pool:

```bash
STORAGE_POOL_SIZE=10
```

---

## Further Reading

- [API Reference](./api-reference.md) — complete endpoint documentation
- [Architecture Diagrams](./architecture-diagrams.md) — visual system architecture
- [Configuration Reference](./configuration-reference.md) — all environment variables
