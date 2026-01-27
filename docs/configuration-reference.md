# SRG Configuration Reference

All settings are loaded from environment variables via [Pydantic Settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/). You can also use a `.env` file in the project root.

```python
from src.config.settings import get_settings
settings = get_settings()
```

---

## Application Settings

Top-level settings on the `Settings` class. No prefix required.

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `APP_NAME` | `str` | `"SRG Invoice System"` | Application display name |
| `APP_VERSION` | `str` | `"1.0.0"` | Application version string |
| `ENVIRONMENT` | `str` | `"development"` | Runtime environment: `development`, `staging`, or `production` |
| `LOG_LEVEL` | `str` | `"INFO"` | Log verbosity: `DEBUG`, `INFO`, `WARNING`, or `ERROR` |

**Logging behavior** depends on `ENVIRONMENT`:
- `development` — Colored console output via structlog
- `staging` / `production` — JSON-formatted structured logs

---

## LLM Settings (`LLM_` prefix)

Access: `settings.llm`

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LLM_PROVIDER` | `str` | `"ollama"` | LLM backend: `"ollama"` or `"llama_cpp"` |
| `LLM_MODEL_NAME` | `str` | `"llama3.1:8b"` | Text generation model identifier |
| `LLM_VISION_MODEL` | `str` | `"llava:13b"` | Vision model for image-based invoice parsing |
| `LLM_HOST` | `str` | `"http://localhost:11434"` | Ollama server URL |
| `LLM_TIMEOUT` | `int` | `120` | Request timeout in seconds |
| `LLM_MAX_TOKENS` | `int` | `4096` | Maximum tokens per generation |
| `LLM_TEMPERATURE` | `float` | `0.1` | Sampling temperature (0.0 = deterministic, 1.0 = creative) |

### Circuit Breaker

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LLM_FAILURE_THRESHOLD` | `int` | `3` | Consecutive failures before circuit opens |
| `LLM_COOLDOWN_SECONDS` | `int` | `60` | Seconds to wait before retrying after circuit opens |

### Retry Policy

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LLM_MAX_RETRIES` | `int` | `3` | Maximum retry attempts per request |
| `LLM_RETRY_DELAY` | `float` | `1.0` | Initial retry delay in seconds |
| `LLM_RETRY_MULTIPLIER` | `float` | `2.0` | Exponential backoff multiplier (delays: 1s, 2s, 4s) |

### Startup

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `LLM_WARMUP_ON_START` | `bool` | `false` | Send a warmup request to LLM on application startup |

---

## Embedding Settings (`EMBED_` prefix)

Access: `settings.embedding`

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `EMBED_MODEL_NAME` | `str` | `"BAAI/bge-m3"` | Sentence-transformer model for embeddings |
| `EMBED_DIMENSION` | `int` | `1024` | Embedding vector dimension (must match model) |
| `EMBED_BATCH_SIZE` | `int` | `32` | Number of texts to embed per batch |
| `EMBED_DEVICE` | `str` | `"cuda"` | Compute device: `"cuda"` (GPU) or `"cpu"` |
| `EMBED_NORMALIZE` | `bool` | `true` | L2-normalize vectors (required for cosine similarity) |

---

## Storage Settings (`STORAGE_` prefix)

Access: `settings.storage`

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STORAGE_DATA_DIR` | `path` | `"data"` | Root directory for all data files |
| `STORAGE_DB_NAME` | `str` | `"srg.db"` | SQLite database filename |
| `STORAGE_FAISS_CHUNKS_INDEX` | `str` | `"faiss_chunks.bin"` | FAISS index file for document chunks |
| `STORAGE_FAISS_ITEMS_INDEX` | `str` | `"faiss_items.bin"` | FAISS index file for line items |

### SQLite Connection Pool

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `STORAGE_POOL_SIZE` | `int` | `5` | Connection pool size |
| `STORAGE_BUSY_TIMEOUT` | `int` | `30000` | SQLite busy timeout in milliseconds |

### Derived Paths

These are computed properties, not configurable via env vars:

| Property | Value |
|----------|-------|
| `storage.db_path` | `{data_dir}/{db_name}` → `data/srg.db` |
| `storage.chunks_index_path` | `{data_dir}/{faiss_chunks_index}` → `data/faiss_chunks.bin` |
| `storage.items_index_path` | `{data_dir}/{faiss_items_index}` → `data/faiss_items.bin` |

---

## Search Settings (`SEARCH_` prefix)

Access: `settings.search`

### Hybrid Search

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SEARCH_RRF_K` | `int` | `60` | Reciprocal Rank Fusion constant `k`. Formula: `score(d) = Σ 1/(k + rank)` |
| `SEARCH_FAISS_CANDIDATES` | `int` | `60` | Number of candidates retrieved from FAISS vector search |
| `SEARCH_FTS_CANDIDATES` | `int` | `60` | Number of candidates retrieved from FTS5 keyword search |

### Reranker

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SEARCH_RERANKER_ENABLED` | `bool` | `true` | Enable neural reranking of search results |
| `SEARCH_RERANKER_MODEL` | `str` | `"BAAI/bge-reranker-v2-m3"` | Cross-encoder reranking model |
| `SEARCH_RERANKER_TOP_K` | `int` | `10` | Number of results to keep after reranking |

### Chunking

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `SEARCH_CHUNK_SIZE` | `int` | `512` | Token count per document chunk |
| `SEARCH_CHUNK_OVERLAP` | `int` | `50` | Overlapping tokens between consecutive chunks |

---

## Parser Settings (`PARSER_` prefix)

Access: `settings.parser`

### Template Matching

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PARSER_TEMPLATE_DIR` | `path` | `"templates/companies"` | Directory containing vendor invoice templates |
| `PARSER_TEMPLATE_MIN_CONFIDENCE` | `float` | `0.7` | Minimum confidence to accept a template match (0.0-1.0) |

### Table Parsing

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PARSER_MIN_COLUMN_GAP` | `int` | `2` | Minimum character gap between table columns |
| `PARSER_HEADER_SEARCH_LINES` | `int` | `50` | Number of lines to scan for table headers |

### Vision Fallback

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `PARSER_VISION_ENABLED` | `bool` | `true` | Enable vision model fallback when text parsing fails |
| `PARSER_VISION_MIN_CONFIDENCE` | `float` | `0.6` | Minimum confidence for vision parser results (0.0-1.0) |

---

## API Settings (`API_` prefix)

Access: `settings.api`

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `API_HOST` | `str` | `"0.0.0.0"` | Server bind address |
| `API_PORT` | `int` | `8000` | Server port |
| `API_DEBUG` | `bool` | `false` | Enable debug mode (auto-reload, verbose errors) |
| `API_CORS_ORIGINS` | `list[str]` | `["*"]` | Allowed CORS origins (comma-separated in env) |

### Upload Limits

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `API_MAX_UPLOAD_SIZE` | `int` | `52428800` | Maximum upload file size in bytes (default: 50 MB) |
| `API_ALLOWED_EXTENSIONS` | `list[str]` | `[".pdf", ".png", ".jpg", ".jpeg"]` | Accepted file extensions for upload |

---

## Cache Settings (`CACHE_` prefix)

Access: `settings.cache`

### Memory Cache

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_EMBEDDING_CACHE_SIZE` | `int` | `10000` | Maximum number of cached embedding vectors (LRU) |
| `CACHE_SEARCH_CACHE_SIZE` | `int` | `1000` | Maximum number of cached search results (LRU) |
| `CACHE_SEARCH_CACHE_TTL` | `int` | `300` | Search cache time-to-live in seconds |

### Disk Cache

| Variable | Type | Default | Description |
|----------|------|---------|-------------|
| `CACHE_VISION_CACHE_ENABLED` | `bool` | `true` | Cache vision model results to disk |
| `CACHE_VISION_CACHE_DIR` | `path` | `"data/cache/vision"` | Directory for cached vision results |

---

## Example `.env` File

```bash
# Application
ENVIRONMENT=development
LOG_LEVEL=INFO

# LLM
LLM_PROVIDER=ollama
LLM_MODEL_NAME=llama3.1:8b
LLM_VISION_MODEL=llava:13b
LLM_HOST=http://localhost:11434
LLM_TIMEOUT=120
LLM_MAX_TOKENS=4096
LLM_TEMPERATURE=0.1
LLM_WARMUP_ON_START=false

# Embeddings
EMBED_MODEL_NAME=BAAI/bge-m3
EMBED_DIMENSION=1024
EMBED_DEVICE=cuda

# Storage
STORAGE_DATA_DIR=data
STORAGE_DB_NAME=srg.db
STORAGE_POOL_SIZE=5

# Search
SEARCH_RRF_K=60
SEARCH_RERANKER_ENABLED=true
SEARCH_CHUNK_SIZE=512
SEARCH_CHUNK_OVERLAP=50

# Parser
PARSER_TEMPLATE_DIR=templates/companies
PARSER_VISION_ENABLED=true

# API
API_HOST=0.0.0.0
API_PORT=8000
API_DEBUG=false
API_CORS_ORIGINS=["http://localhost:3000","http://localhost:3001"]

# Cache
CACHE_EMBEDDING_CACHE_SIZE=10000
CACHE_SEARCH_CACHE_TTL=300
CACHE_VISION_CACHE_ENABLED=true
```

---

## Configuration Precedence

Settings are resolved in this order (highest priority first):

1. **Environment variables** — e.g. `export LLM_PROVIDER=llama_cpp`
2. **`.env` file** — in project root directory
3. **Defaults** — hardcoded in the `Settings` classes

---

## Production Recommendations

| Setting | Development | Production |
|---------|-------------|------------|
| `ENVIRONMENT` | `development` | `production` |
| `LOG_LEVEL` | `DEBUG` | `INFO` or `WARNING` |
| `API_DEBUG` | `true` | `false` |
| `API_CORS_ORIGINS` | `["*"]` | Specific origins only |
| `EMBED_DEVICE` | `cpu` | `cuda` |
| `LLM_WARMUP_ON_START` | `false` | `true` |
| `CACHE_SEARCH_CACHE_TTL` | `300` | `3600` |
| `STORAGE_POOL_SIZE` | `5` | `10-20` |
