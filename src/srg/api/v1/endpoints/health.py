"""Health check endpoints."""

import time

from fastapi import APIRouter

from src.srg.config import settings
from src.srg.schemas.health import HealthResponse, ProviderHealth

router = APIRouter()

_start_time = time.time()


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Basic health check."""
    return HealthResponse(
        status="healthy",
        version=settings.VERSION,
        uptime_seconds=time.time() - _start_time,
    )


@router.get("/detailed", response_model=HealthResponse)
async def detailed_health() -> HealthResponse:
    """Detailed health check with component status."""
    from src.infrastructure.embeddings import get_embedding_provider
    from src.infrastructure.llm import get_llm_provider
    from src.infrastructure.storage.sqlite import get_connection_pool
    from src.infrastructure.storage.vector import get_faiss_store

    status = "healthy"
    providers: dict[str, ProviderHealth] = {}

    # Check LLM
    try:
        llm = get_llm_provider()
        start = time.time()
        is_healthy = await llm.health_check()
        providers["llm"] = ProviderHealth(
            name=llm.__class__.__name__,
            available=is_healthy,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["llm"] = ProviderHealth(name="llm", available=False, error=str(e))
        status = "degraded"

    # Check embedding
    try:
        embedder = get_embedding_provider()
        start = time.time()
        await embedder.embed("test")
        providers["embedding"] = ProviderHealth(
            name=embedder.__class__.__name__,
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["embedding"] = ProviderHealth(name="embedding", available=False, error=str(e))
        status = "degraded"

    # Check database
    try:
        pool = await get_connection_pool()
        start = time.time()
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
        providers["database"] = ProviderHealth(
            name="sqlite",
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["database"] = ProviderHealth(name="database", available=False, error=str(e))
        status = "unhealthy"

    # Check vector store
    try:
        store = get_faiss_store()
        start = time.time()
        _count = store.count()  # noqa: F841
        providers["vector_store"] = ProviderHealth(
            name="faiss",
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["vector_store"] = ProviderHealth(
            name="vector_store", available=False, error=str(e)
        )
        status = "degraded"

    return HealthResponse(
        status=status,
        version=settings.VERSION,
        uptime_seconds=time.time() - _start_time,
        providers=providers,
    )
