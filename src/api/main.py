"""
FastAPI application factory.

Creates and configures the main application instance.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.middleware import ErrorHandlerMiddleware, LoggingMiddleware
from src.api.middleware.error_handler import setup_exception_handlers
from src.api.routes import (
    chat_router,
    documents_router,
    health_router,
    invoices_router,
    search_router,
    sessions_router,
)
from src.config import get_logger, get_settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
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
            is_healthy = await llm.health_check()
            logger.info("llm_provider_ready", healthy=is_healthy)

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

    return app


# Create app instance
app = create_app()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "SRG Invoice Processing API",
        "version": "1.0.0",
        "docs": "/docs",
    }


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()

    uvicorn.run(
        "src.api.main:app",
        host=settings.api.host,
        port=settings.api.port,
        reload=settings.api.debug,
    )
