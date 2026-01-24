# SRG Project Onboarding Guide

Welcome to the SRG Invoice Processing API team! This guide will help you get up to speed quickly.

---

## Table of Contents

1. [Pre-Boarding Checklist](#pre-boarding-checklist)
2. [Day 1: Setup & Orientation](#day-1-setup--orientation)
3. [Week 1: Codebase Immersion](#week-1-codebase-immersion)
4. [Development Environment](#development-environment)
5. [Architecture Deep Dive](#architecture-deep-dive)
6. [Key Components Guide](#key-components-guide)
7. [30/60/90 Day Milestones](#306090-day-milestones)
8. [Resources & Learning Path](#resources--learning-path)

---

## Pre-Boarding Checklist

### Accounts to Request

- [ ] GitHub access to repository
- [ ] Slack workspace invitation
- [ ] Jira/project management tool access
- [ ] Cloud platform access (if applicable)

### Hardware Requirements

- Laptop with minimum 16GB RAM (32GB recommended for LLM work)
- GPU recommended for faster embeddings (CUDA-compatible)
- SSD storage (50GB+ free space for models)

### Software Prerequisites

- [ ] Python 3.11+ installed
- [ ] Git configured with SSH keys
- [ ] VS Code or preferred IDE
- [ ] Docker Desktop installed
- [ ] Ollama installed (for local LLM)

---

## Day 1: Setup & Orientation

### Morning (9:00 AM - 12:00 PM)

| Time | Activity | Duration |
|------|----------|----------|
| 9:00 | Manager welcome & team intro | 30 min |
| 9:30 | Project overview & architecture | 45 min |
| 10:15 | Break | 15 min |
| 10:30 | Development environment setup | 90 min |

### Afternoon (1:00 PM - 5:00 PM)

| Time | Activity | Duration |
|------|----------|----------|
| 1:00 | Team lunch (virtual/in-person) | 60 min |
| 2:00 | First code checkout & build | 60 min |
| 3:00 | API walkthrough with mentor | 45 min |
| 3:45 | Break | 15 min |
| 4:00 | First "good first issue" selection | 30 min |
| 4:30 | Day 1 retrospective | 30 min |

### Day 1 Commands

```powershell
# Clone repository
git clone <repository-url> C:\SrGonaH\SRG
cd C:\SrGonaH\SRG

# Create virtual environment
python -m venv .venv
.\.venv\Scripts\Activate

# Install dependencies
pip install -e ".[dev]"

# Copy environment file
copy .env.example .env

# Run database migrations
python -m src.infrastructure.storage.sqlite.migrations.migrator

# Start development server
uvicorn src.srg.main:app --reload

# Verify it works
curl http://localhost:8000/health
```

### Day 1 Verification Checklist

- [ ] Repository cloned successfully
- [ ] Virtual environment activated
- [ ] All dependencies installed
- [ ] Server starts without errors
- [ ] Health endpoint returns `{"status": "healthy"}`
- [ ] API docs accessible at http://localhost:8000/docs
- [ ] Tests pass: `pytest tests/ -v`

---

## Week 1: Codebase Immersion

### Day 2-3: Architecture Understanding

**Goal**: Understand the layered architecture

1. **Read these files first**:
   - `README.md` - Project overview
   - `src/srg/config.py` - Configuration system
   - `src/srg/main.py` - Application entry point
   - `src/core/entities/` - Domain models

2. **Architecture Diagram Study**:
```
┌─────────────────────────────────────────┐
│         API Layer (FastAPI)             │
│  /api/v1/invoices, /search, /chat       │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│    Application Layer (Use Cases)        │
│  UploadInvoice, AuditInvoice, Chat      │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│      Core Layer (Business Logic)        │
│  Entities, Services, Interfaces         │
└──────────────────┬──────────────────────┘
                   │
┌──────────────────▼──────────────────────┐
│    Infrastructure Layer (Adapters)      │
│  LLM, Storage, Parsers, Search          │
└─────────────────────────────────────────┘
```

3. **Pair programming sessions**:
   - Day 2: API routes walkthrough
   - Day 3: Storage and search deep dive

### Day 4-5: First Contribution

**Goal**: Submit your first PR

1. **Find a "good first issue"**:
   - Add a new validation rule
   - Improve error message
   - Add test coverage
   - Update documentation

2. **Development workflow**:
```bash
# Create feature branch
git checkout -b feature/your-feature-name

# Make changes
# Run tests
pytest tests/ -v

# Format code
ruff format src tests
ruff check --fix src tests

# Commit
git add .
git commit -m "feat: your feature description"

# Push and create PR
git push -u origin feature/your-feature-name
```

3. **PR checklist**:
   - [ ] Tests pass locally
   - [ ] Code formatted with ruff
   - [ ] Type hints added
   - [ ] Documentation updated (if needed)

---

## Development Environment

### Required Tools

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| pip/uv | Latest | Package management |
| Git | 2.40+ | Version control |
| Docker | 24+ | Containerization |
| Ollama | Latest | Local LLM |
| VS Code | Latest | IDE (recommended) |

### VS Code Extensions

```json
// Recommended extensions
{
  "recommendations": [
    "ms-python.python",
    "ms-python.vscode-pylance",
    "charliermarsh.ruff",
    "tamasfe.even-better-toml",
    "redhat.vscode-yaml",
    "ms-azuretools.vscode-docker"
  ]
}
```

### Environment Variables

```env
# Core Settings
PROJECT_NAME="SRG Invoice Processing API"
DEBUG=True
ENVIRONMENT=development

# API
API_V1_PREFIX=/api/v1
HOST=0.0.0.0
PORT=8000

# LLM (choose one)
LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=llama3.2

# Embeddings
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSION=1024

# Storage
DATABASE_URL=sqlite+aiosqlite:///./data/srg.db
FAISS_INDEX_PATH=./data/faiss_index
```

### Makefile Commands Reference

| Command | Description |
|---------|-------------|
| `make install` | Install all dependencies |
| `make dev` | Run development server |
| `make test` | Run test suite |
| `make test-cov` | Run tests with coverage |
| `make lint` | Check code style |
| `make format` | Format code |
| `make type-check` | Run type checker |
| `make migrate` | Run database migrations |
| `make clean` | Clean build artifacts |

---

## Architecture Deep Dive

### Layer Responsibilities

#### 1. API Layer (`src/api/`, `src/srg/api/`)

**Purpose**: HTTP request handling, validation, routing

**Key Files**:
- `main.py` - FastAPI app factory with lifespan
- `dependencies.py` - Dependency injection
- `routes/*.py` - Endpoint definitions
- `middleware/*.py` - Request/response processing

**Patterns Used**:
- FastAPI dependency injection
- Pydantic request/response models
- Async route handlers

#### 2. Application Layer (`src/application/`)

**Purpose**: Orchestrate business workflows

**Key Files**:
- `use_cases/*.py` - Business workflows
- `dto/*.py` - Data transfer objects

**Use Case Pattern**:
```python
class UploadInvoiceUseCase:
    async def execute(self, file, filename, request) -> UploadResult:
        # 1. Save file
        # 2. Parse invoice
        # 3. Store in database
        # 4. Index for search
        # 5. Audit (optional)
        return result
```

#### 3. Core Layer (`src/core/`)

**Purpose**: Business logic, domain models, interfaces

**Key Files**:
- `entities/*.py` - Domain models (Invoice, Document, Session)
- `services/*.py` - Business logic orchestration
- `interfaces/*.py` - Abstract contracts
- `exceptions.py` - Domain exceptions

**Entity Example**:
```python
class Invoice(BaseModel):
    id: str
    invoice_number: str
    vendor_name: str
    line_items: list[LineItem]

    @computed_field
    def calculated_total(self) -> float:
        return sum(item.total_price for item in self.line_items)
```

#### 4. Infrastructure Layer (`src/infrastructure/`)

**Purpose**: External integrations, technical implementations

**Subdirectories**:
- `llm/` - LLM providers (Ollama, llama-cpp)
- `embeddings/` - BGE-M3 embedding generation
- `storage/` - SQLite and FAISS storage
- `parsers/` - Invoice parsing strategies
- `search/` - Hybrid search implementation
- `cache/` - Memory and disk caching

---

## Key Components Guide

### 1. Invoice Parsing Pipeline

```
PDF Upload → Text Extraction → Parser Selection → Parsing → Validation
                                    ↓
                    ┌───────────────┼───────────────┐
                    │               │               │
              Template         Table-aware       Vision
              Parser            Parser          Parser
              (YAML)           (Columns)        (LLaVA)
```

**Files to study**:
- `src/infrastructure/parsers/registry.py`
- `src/infrastructure/parsers/template_parser.py`
- `src/infrastructure/parsers/table_aware_parser.py`
- `src/core/services/invoice_parser.py`

### 2. Hybrid Search System

```
Query → Embedding → FAISS Search ─┐
         ↓                        ├─→ RRF Fusion → Reranking → Results
      FTS5 Search ────────────────┘
```

**Key concepts**:
- **FAISS**: Vector similarity search
- **FTS5**: SQLite full-text search
- **RRF**: Reciprocal Rank Fusion (combining results)
- **Reranking**: Second-pass with BGE-reranker

**Files to study**:
- `src/infrastructure/search/hybrid.py`
- `src/infrastructure/search/fts.py`
- `src/infrastructure/search/reranker.py`
- `src/core/services/search_service.py`

### 3. RAG Chat System

```
User Message → Context Search → Prompt Building → LLM → Response
                   ↓
         Memory Facts Extraction
```

**Features**:
- Session-based conversations
- Automatic context retrieval
- Memory fact extraction
- Streaming responses

**Files to study**:
- `src/core/services/chat_service.py`
- `src/application/use_cases/chat_with_context.py`
- `src/api/routes/chat.py`

### 4. LLM Integration

**Provider Pattern**:
```python
# Factory creates appropriate provider based on config
provider = get_llm_provider()  # Returns OllamaProvider or LlamaCppProvider

# All providers implement same interface
response = await provider.generate(prompt, max_tokens=500)
```

**Files to study**:
- `src/core/interfaces/llm.py`
- `src/infrastructure/llm/factory.py`
- `src/infrastructure/llm/ollama.py`
- `src/infrastructure/llm/base.py` (circuit breaker)

---

## 30/60/90 Day Milestones

### 30-Day Checkpoint

**Technical Goals**:
- [ ] Complete development environment setup
- [ ] Understand codebase architecture
- [ ] Merge 3+ pull requests
- [ ] Write tests for one component
- [ ] Document one process or system

**Social Goals**:
- [ ] 1:1 with each team member
- [ ] Attend all team ceremonies
- [ ] Identify buddy/mentor relationship

**Deliverable**: Present 10-minute "What I've learned" to team

### 60-Day Checkpoint

**Technical Goals**:
- [ ] Own a small feature end-to-end
- [ ] Contribute to technical design discussion
- [ ] Shadow on-call (if applicable)
- [ ] Improve test coverage by 5%
- [ ] Participate in code reviews

**Knowledge Goals**:
- [ ] Understand all major components
- [ ] Know deployment process
- [ ] Familiar with monitoring/logging

**Deliverable**: Feature demo to stakeholders

### 90-Day Checkpoint

**Technical Goals**:
- [ ] Lead a feature implementation
- [ ] Propose process improvement
- [ ] Mentor newer team member
- [ ] Full code review participation
- [ ] Independent problem-solving

**Career Goals**:
- [ ] Performance review completed
- [ ] Development goals established
- [ ] Team integration confirmed

**Deliverable**: Technical proposal or improvement initiative

---

## Resources & Learning Path

### Internal Documentation

| Resource | Location |
|----------|----------|
| Project README | `README.md` |
| API Documentation | http://localhost:8000/docs |
| Configuration Guide | `src/srg/config.py` |
| Database Schema | `src/infrastructure/storage/sqlite/migrations/` |

### External Learning

**FastAPI**:
- [Official Tutorial](https://fastapi.tiangolo.com/tutorial/)
- [Advanced User Guide](https://fastapi.tiangolo.com/advanced/)

**Pydantic v2**:
- [Pydantic Docs](https://docs.pydantic.dev/latest/)

**FAISS**:
- [FAISS Wiki](https://github.com/facebookresearch/faiss/wiki)

**LLM/RAG**:
- [Ollama Documentation](https://ollama.ai/docs)
- [BGE-M3 Paper](https://arxiv.org/abs/2402.03216)

### Recommended Books

1. *Architecture Patterns with Python* - Harry Percival & Bob Gregory
2. *Designing Data-Intensive Applications* - Martin Kleppmann
3. *FastAPI Book* - Muhammad Yasoob Ullah Khalid

### Team Contacts

| Role | Contact | Topics |
|------|---------|--------|
| Tech Lead | @tech-lead | Architecture decisions |
| Senior Dev | @senior-dev | Code review, mentoring |
| DevOps | @devops | Deployment, infrastructure |
| Product | @product | Requirements, priorities |

---

## Frequently Asked Questions

### Q: How do I add a new API endpoint?

1. Create route file in `src/srg/api/v1/endpoints/`
2. Add schema in `src/srg/schemas/`
3. Create use case in `src/application/use_cases/`
4. Register route in `src/srg/api/v1/router.py`
5. Add tests in `tests/api/`

### Q: How do I add a new parser?

1. Implement `IInvoiceParser` interface
2. Add to `src/infrastructure/parsers/`
3. Register in `ParserRegistry`
4. Add tests

### Q: How do I switch LLM providers?

Change in `.env`:
```env
LLM_PROVIDER=llama_cpp  # or ollama
LLAMA_CPP_MODEL_PATH=/path/to/model.gguf
```

### Q: Where are logs stored?

- Development: Console output (colored)
- Production: JSON format to stdout (for log aggregation)

### Q: How do I debug a failing test?

```bash
# Run single test with verbose output
pytest tests/api/test_invoices.py::test_upload_invoice -vvs

# With debugger
pytest tests/api/test_invoices.py --pdb
```

---

## Onboarding Feedback

Please provide feedback to help improve this onboarding experience:

- Weekly pulse survey (5 questions)
- Buddy feedback at 30 days
- Manager 1:1 structured questions
- Anonymous feedback channel

**Questions to consider**:
1. What was most helpful?
2. What was confusing or unclear?
3. What would you add to this guide?
4. How could we improve Day 1?

---

*Last updated: January 2026*
*Version: 1.0*
