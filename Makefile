.PHONY: install dev test lint format clean migrate run build docker-build docker-run

# Development setup
install:
	pip install -e ".[dev]"

dev:
	uvicorn src.srg.main:app --reload --host 0.0.0.0 --port 8000

# Testing
test:
	pytest -v

test-cov:
	pytest --cov=src --cov-report=html --cov-report=term

# Code quality
lint:
	ruff check src tests

lint-fix:
	ruff check --fix src tests

format:
	ruff format src tests

type-check:
	mypy src

# Database
migrate:
	python -m src.infrastructure.storage.sqlite.migrations.migrator

# Indexing
reindex:
	python -m src.infrastructure.storage.vector.faiss_store

# Cleanup
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage 2>/dev/null || true

# Production
run:
	uvicorn src.srg.main:app --host 0.0.0.0 --port 8000 --workers 4

build:
	pip install build
	python -m build

# Docker
docker-build:
	docker build -t srg-api:latest .

docker-run:
	docker run -p 8000:8000 --env-file .env srg-api:latest

# Documentation
docs:
	@echo "API docs available at http://localhost:8000/docs"

# Help
help:
	@echo "Available commands:"
	@echo "  make install     - Install dependencies"
	@echo "  make dev         - Run development server"
	@echo "  make test        - Run tests"
	@echo "  make test-cov    - Run tests with coverage"
	@echo "  make lint        - Check code style"
	@echo "  make lint-fix    - Fix code style issues"
	@echo "  make format      - Format code"
	@echo "  make type-check  - Run type checking"
	@echo "  make migrate     - Run database migrations"
	@echo "  make reindex     - Rebuild FAISS index"
	@echo "  make clean       - Clean build artifacts"
	@echo "  make run         - Run production server"
	@echo "  make build       - Build package"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run  - Run Docker container"
