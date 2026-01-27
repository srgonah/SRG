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

    status_str = "healthy"
    providers: dict[str, ProviderHealth] = {}

    # Check LLM
    try:
        llm = get_llm_provider()
        start = time.time()
        health_result = await llm.check_health()
        providers["llm"] = ProviderHealth(
            name=llm.__class__.__name__,
            available=health_result.available,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["llm"] = ProviderHealth(name="llm", available=False, error=str(e))
        status_str = "degraded"

    # Check embedding
    try:
        embedder = get_embedding_provider()
        start = time.time()
        embedder.embed_single("test")
        providers["embedding"] = ProviderHealth(
            name=embedder.__class__.__name__,
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["embedding"] = ProviderHealth(name="embedding", available=False, error=str(e))
        status_str = "degraded"

    # Check database
    try:
        pool = await get_connection_pool()
        start = time.time()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        providers["database"] = ProviderHealth(
            name="sqlite",
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        providers["database"] = ProviderHealth(name="database", available=False, error=str(e))
        status_str = "unhealthy"

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
        status_str = "degraded"

    return HealthResponse(
        status=status_str,
        version=settings.VERSION,
        uptime_seconds=time.time() - _start_time,
        providers=providers,
    )
