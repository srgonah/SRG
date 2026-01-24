"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.v1.router import api_router
from .config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup/shutdown events."""
    # Startup
    print(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")

    # Initialize database connection pool
    from src.infrastructure.storage.sqlite import get_connection_pool

    await get_connection_pool()
    print("Database connection pool initialized")

    # Initialize vector store
    from src.infrastructure.storage.vector import get_faiss_store

    store = get_faiss_store()
    print(f"FAISS store initialized with {store.count()} vectors")

    yield

    # Shutdown
    print("Shutting down application")

    # Close database connections
    from src.infrastructure.storage.sqlite import close_connection_pool

    await close_connection_pool()

    # Save FAISS index
    store = get_faiss_store()
    store.save()
    print("FAISS index saved")


def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Invoice processing and RAG-powered chat API",
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        lifespan=lifespan,
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


app = create_app()


@app.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint."""
    return {"status": "healthy", "version": settings.VERSION}


def run():
    """Run the application with uvicorn."""
    import uvicorn

    uvicorn.run(
        "src.srg.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.RELOAD,
        workers=settings.WORKERS if not settings.RELOAD else 1,
    )


if __name__ == "__main__":
    run()
