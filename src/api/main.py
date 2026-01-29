"""
FastAPI application factory.

Creates and configures the main application instance.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from src.api.middleware import ErrorHandlerMiddleware, LoggingMiddleware
from src.api.middleware.error_handler import setup_exception_handlers
from src.api.routes import (
    amazon_import_router,
    catalog_router,
    chat_router,
    company_documents_router,
    creators_router,
    documents_router,
    health_router,
    inventory_router,
    invoices_router,
    prices_router,
    reminders_router,
    sales_router,
    search_router,
    sessions_router,
    templates_router,
)
from src.config import get_logger, get_settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """
    Application lifespan handler.

    Initializes resources on startup and cleans up on shutdown.
    """
    settings = get_settings()

    logger.info(
        "application_starting",
        host=settings.api.host,
        port=settings.api.port,
        debug=settings.api.debug,
    )

    # Initialize database
    try:
        from src.infrastructure.storage.sqlite import get_connection_pool
        from src.infrastructure.storage.sqlite.migrations.migrator import run_migrations

        # Run migrations
        await run_migrations()
        logger.info("database_initialized")

        # Initialize connection pool
        await get_connection_pool()
        logger.info("connection_pool_ready")

    except Exception as e:
        logger.error("database_init_failed", error=str(e))
        raise

    # Initialize vector store
    try:
        from src.infrastructure.storage.vector import get_faiss_store

        store = get_faiss_store()
        count = store.count()
        logger.info("vector_store_ready", vectors=count)

    except Exception as e:
        logger.warning("vector_store_init_failed", error=str(e))

    # Warm up LLM provider (optional)
    if settings.llm.warmup_on_start:
        try:
            from src.infrastructure.llm import get_llm_provider

            llm = get_llm_provider()
            health_status = await llm.check_health()
            logger.info("llm_provider_ready", healthy=health_status.available)

        except Exception as e:
            logger.warning("llm_warmup_failed", error=str(e))

    logger.info("application_started")

    yield

    # Shutdown
    logger.info("application_stopping")

    # Close connection pool
    try:
        from src.infrastructure.storage.sqlite import close_connection_pool

        await close_connection_pool()
        logger.info("connection_pool_closed")

    except Exception as e:
        logger.warning("connection_pool_close_failed", error=str(e))

    # Save vector index
    try:
        from src.infrastructure.storage.vector import get_faiss_store

        store = get_faiss_store()
        store.save()
        logger.info("vector_index_saved")

    except Exception as e:
        logger.warning("vector_index_save_failed", error=str(e))

    logger.info("application_stopped")


def create_app() -> FastAPI:
    """
    Create and configure FastAPI application.

    Returns:
        Configured FastAPI instance
    """
    settings = get_settings()

    app = FastAPI(
        title="SRG Invoice Processing API",
        description="Invoice parsing, auditing, and RAG-powered chat",
        version="1.0.0",
        docs_url="/docs" if settings.api.debug else None,
        redoc_url="/redoc" if settings.api.debug else None,
        lifespan=lifespan,
    )

    # Add middleware
    app.add_middleware(LoggingMiddleware)
    app.add_middleware(ErrorHandlerMiddleware)

    # CORS
    if settings.api.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.api.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # Setup exception handlers
    setup_exception_handlers(app)

    # Register routers
    app.include_router(health_router)
    app.include_router(invoices_router)
    app.include_router(documents_router)
    app.include_router(search_router)
    app.include_router(chat_router)
    app.include_router(sessions_router)
    app.include_router(catalog_router)
    app.include_router(prices_router)
    app.include_router(company_documents_router)
    app.include_router(reminders_router)
    app.include_router(inventory_router)
    app.include_router(sales_router)
    app.include_router(amazon_import_router)
    app.include_router(templates_router)
    app.include_router(creators_router)

    # Mount static files for web UI
    # Priority: webui/dist (React SPA build) > static/ (minimal fallback)
    project_root = Path(__file__).parent.parent.parent

    # Vite build assets (JS/CSS bundles with content hashes)
    dist_assets = project_root / "webui" / "dist" / "assets"
    if dist_assets.exists():
        app.mount("/assets", StaticFiles(directory=str(dist_assets)), name="spa-assets")

    # Vite public files (e.g. vite.svg) served at root level
    dist_dir = project_root / "webui" / "dist"
    if dist_dir.exists():
        app.mount("/spa-static", StaticFiles(directory=str(dist_dir)), name="spa-root")

    # Legacy fallback static files
    static_dir = project_root / "static"
    if static_dir.exists():
        app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    return app


# Create app instance
app = create_app()


# Root endpoint - serve web UI
@app.get("/", response_model=None)
async def root() -> FileResponse | dict[str, str]:
    """Serve web UI or return API info."""
    project_root = Path(__file__).parent.parent.parent

    # Prefer React SPA build
    spa_index = project_root / "webui" / "dist" / "index.html"
    if spa_index.exists():
        return FileResponse(spa_index)

    # Fall back to minimal static page
    static_index = project_root / "static" / "index.html"
    if static_index.exists():
        return FileResponse(static_index)

    return {
        "name": "SRG Invoice Processing API",
        "version": "1.0.0",
        "docs": "/docs",
    }


# Root health endpoint (for k8s/docker health checks)
@app.get("/health")
async def root_health() -> dict[str, str]:
    """Simple health check at root level."""
    return {
        "status": "healthy",
        "version": "1.0.0",
    }


# SPA catch-all: serve index.html for non-API paths so React Router works
# Registered last — API routes, /docs, /health, and /static mount all take priority.
@app.get("/{path:path}", response_model=None)
async def spa_catch_all(path: str) -> Response | dict[str, str]:
    """Serve SPA index.html for client-side routes."""

    # API paths that don't match a real route should 404, not serve the SPA
    if path.startswith("api/"):
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    project_root = Path(__file__).parent.parent.parent

    # Prefer React SPA build
    spa_index = project_root / "webui" / "dist" / "index.html"
    if spa_index.exists():
        return FileResponse(spa_index)

    # Fall back to minimal static page
    static_index = project_root / "static" / "index.html"
    if static_index.exists():
        return FileResponse(static_index)

    return {"detail": "Not Found"}


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
    )
