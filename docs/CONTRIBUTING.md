# Contributing to SRG

Thank you for your interest in contributing to SRG! This guide will help you get started.

## Development Setup

### Prerequisites

- Python 3.11+
- Git
- Docker (optional)
- Ollama (for LLM features)

### Quick Start

```bash
# Clone and setup
git clone <repository-url>
cd SRG

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\Activate

# Install with dev dependencies
pip install -e ".[dev]"

# Copy environment file
cp .env.example .env

# Run migrations
make migrate

# Start development server
make dev
```

## Code Style

### Formatting

We use **ruff** for formatting and linting:

```bash
# Format code
make format

# Check for issues
make lint

# Auto-fix issues
make lint-fix
```

### Type Hints

All code must have type hints. We use **mypy** in strict mode:

```bash
make type-check
```

### Example

```python
from typing import Optional

async def process_invoice(
    invoice_id: str,
    options: Optional[dict[str, str]] = None,
) -> InvoiceResult:
    """Process an invoice with optional configuration.

    Args:
        invoice_id: The unique invoice identifier.
        options: Optional processing options.

    Returns:
        The processed invoice result.

    Raises:
        InvoiceNotFoundError: If invoice doesn't exist.
    """
    ...
```

## Git Workflow

### Branch Naming

- `feature/description` - New features
- `fix/description` - Bug fixes
- `docs/description` - Documentation
- `refactor/description` - Code refactoring
- `test/description` - Test additions

### Commit Messages

Follow conventional commits:

```
feat: add invoice validation endpoint
fix: correct calculation in audit service
docs: update API documentation
test: add unit tests for parser
refactor: simplify search service
```

### Pull Request Process

1. **Create branch** from `main`
2. **Make changes** with tests
3. **Run checks locally**:
   ```bash
   make test
   make lint
   make type-check
   ```
4. **Push and create PR**
5. **Address review feedback**
6. **Squash merge** when approved

### PR Checklist

- [ ] Tests pass (`make test`)
- [ ] Code formatted (`make format`)
- [ ] Types checked (`make type-check`)
- [ ] Documentation updated
- [ ] Commit messages follow convention

## Testing

### Running Tests

```bash
# All tests
make test

# With coverage
make test-cov

# Single file
pytest tests/api/test_invoices.py -v

# Single test
pytest tests/api/test_invoices.py::test_upload_invoice -v

# With debugger
pytest tests/api/test_invoices.py --pdb
```

### Writing Tests

```python
import pytest
from fastapi.testclient import TestClient

def test_health_check(client: TestClient):
    """Test basic health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "healthy"

@pytest.mark.asyncio
async def test_async_operation(async_client):
    """Test async endpoint."""
    response = await async_client.get("/api/v1/documents")
    assert response.status_code == 200
```

### Test Fixtures

Available fixtures in `tests/conftest.py`:

- `client` - Sync test client
- `async_client` - Async test client
- `api_prefix` - API v1 prefix
- `sample_invoice_data` - Test invoice data
- `sample_search_query` - Test search data

## Architecture Guidelines

### Layer Responsibilities

| Layer | Purpose | Dependencies |
|-------|---------|--------------|
| API | HTTP handling | Application |
| Application | Use cases | Core |
| Core | Business logic | None (interfaces) |
| Infrastructure | Implementations | Core interfaces |

### Adding New Features

1. **Define entity** in `src/core/entities/`
2. **Create interface** in `src/core/interfaces/`
3. **Implement** in `src/infrastructure/`
4. **Add service** in `src/core/services/`
5. **Create use case** in `src/application/use_cases/`
6. **Add endpoint** in `src/api/routes/`
7. **Write tests** in `tests/`

### Example: Adding a New Entity

```python
# src/core/entities/vendor.py
from pydantic import BaseModel
from datetime import datetime

class Vendor(BaseModel):
    id: str
    name: str
    address: str
    created_at: datetime
```

## Documentation

### Docstrings

Use Google style docstrings:

```python
def process(data: dict, options: Options) -> Result:
    """Process data with given options.

    Args:
        data: Input data dictionary.
        options: Processing options.

    Returns:
        Processed result object.

    Raises:
        ValidationError: If data is invalid.
        ProcessingError: If processing fails.
    """
```

### API Documentation

FastAPI auto-generates docs at `/docs`. Add descriptions to routes:

```python
@router.post(
    "/invoices",
    response_model=InvoiceResponse,
    summary="Upload invoice",
    description="Upload and process a new invoice file.",
)
async def upload_invoice(...):
    ...
```

## Getting Help

- **Questions**: Ask in team Slack channel
- **Bugs**: Create GitHub issue
- **Features**: Discuss in team meeting first

## Code of Conduct

- Be respectful and inclusive
- Provide constructive feedback
- Help others learn and grow
- Focus on the code, not the person

---

Thank you for contributing! 🎉
