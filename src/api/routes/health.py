"""
Health check endpoints.
"""

import time

from fastapi import APIRouter

from src.api.dependencies import get_llm
from src.application.dto.responses import HealthResponse, ProviderHealthResponse

router = APIRouter(prefix="/api/health", tags=["health"])

# Track startup time
_start_time = time.time()


@router.get("", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Basic health check.

    Returns service status and uptime.
    """
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        uptime_seconds=time.time() - _start_time,
    )


@router.get("/llm", response_model=HealthResponse)
async def llm_health() -> HealthResponse:
    """
    LLM provider health check.

    Tests LLM connectivity and response time.
    """
    llm_status = ProviderHealthResponse(
        name="unknown",
        available=False,
    )

    try:
        llm = get_llm()
        start = time.time()

        # Simple health check
        health_result = await llm.check_health()
        latency = (time.time() - start) * 1000

        llm_status = ProviderHealthResponse(
            name=llm.__class__.__name__,
            available=health_result.available,
            latency_ms=latency,
        )

    except Exception as e:
        llm_status = ProviderHealthResponse(
            name="unknown",
            available=False,
            error=str(e),
        )

    return HealthResponse(
        status="healthy" if llm_status.available else "degraded",
        version="1.0.0",
        uptime_seconds=time.time() - _start_time,
        llm=llm_status,
    )


@router.get("/db", response_model=HealthResponse)
async def db_health() -> HealthResponse:
    """
    Database health check.

    Tests SQLite connectivity and response time.
    """
    from src.infrastructure.storage.sqlite import get_connection_pool

    db_status = ProviderHealthResponse(
        name="sqlite",
        available=False,
    )

    try:
        pool = await get_connection_pool()
        start = time.time()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        latency = (time.time() - start) * 1000

        db_status = ProviderHealthResponse(
            name="sqlite",
            available=True,
            latency_ms=latency,
        )

    except Exception as e:
        db_status = ProviderHealthResponse(
            name="sqlite",
            available=False,
            error=str(e),
        )

    return HealthResponse(
        status="healthy" if db_status.available else "unhealthy",
        version="1.0.0",
        uptime_seconds=time.time() - _start_time,
        database=db_status,
    )


@router.get("/search", response_model=HealthResponse)
async def search_health() -> HealthResponse:
    """
    Search system health check.

    Tests vector store and FTS availability.
    """
    from src.infrastructure.storage.vector import get_faiss_store

    vec_status = ProviderHealthResponse(
        name="faiss",
        available=False,
    )

    try:
        store = get_faiss_store()
        start = time.time()
        count = store.count()
        latency = (time.time() - start) * 1000

        vec_status = ProviderHealthResponse(
            name=f"faiss ({count} vectors)",
            available=True,
            latency_ms=latency,
        )

    except Exception as e:
        vec_status = ProviderHealthResponse(
            name="faiss",
            available=False,
            error=str(e),
        )

    return HealthResponse(
        status="healthy" if vec_status.available else "degraded",
        version="1.0.0",
        uptime_seconds=time.time() - _start_time,
        vector_store=vec_status,
    )


@router.get("/full", response_model=HealthResponse)
async def full_health_check() -> HealthResponse:
    """
    Full system health check.

    Tests all components: LLM, embedding, database, vector store.
    """
    from src.infrastructure.embeddings import get_embedding_provider
    from src.infrastructure.storage.sqlite import get_connection_pool
    from src.infrastructure.storage.vector import get_faiss_store

    status_str = "healthy"

    # LLM check
    llm_status = ProviderHealthResponse(name="llm", available=False)
    try:
        llm = get_llm()
        start = time.time()
        health_result = await llm.check_health()
        llm_status = ProviderHealthResponse(
            name=llm.__class__.__name__,
            available=health_result.available,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        llm_status.error = str(e)
        status_str = "degraded"

    # Embedding check
    embed_status = ProviderHealthResponse(name="embedding", available=False)
    try:
        embedder = get_embedding_provider()
        start = time.time()
        _ = embedder.embed_single("test")
        embed_status = ProviderHealthResponse(
            name=embedder.__class__.__name__,
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        embed_status.error = str(e)
        status_str = "degraded"

    # Database check
    db_status = ProviderHealthResponse(name="sqlite", available=False)
    try:
        pool = await get_connection_pool()
        start = time.time()
        async with pool.acquire() as conn:
            await conn.execute("SELECT 1")
        db_status = ProviderHealthResponse(
            name="sqlite",
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        db_status.error = str(e)
        status_str = "unhealthy"

    # Vector store check
    vec_status = ProviderHealthResponse(name="faiss", available=False)
    try:
        store = get_faiss_store()
        start = time.time()
        _count = store.count()  # noqa: F841
        vec_status = ProviderHealthResponse(
            name="faiss",
            available=True,
            latency_ms=(time.time() - start) * 1000,
        )
    except Exception as e:
        vec_status.error = str(e)
        status_str = "degraded"

    return HealthResponse(
        status=status_str,
        version="1.0.0",
        uptime_seconds=time.time() - _start_time,
        llm=llm_status,
        embedding=embed_status,
        database=db_status,
        vector_store=vec_status,
    )


@router.get("/detailed", response_model=HealthResponse)
async def detailed_health_check() -> HealthResponse:
    """
    Detailed system health check (alias for /full).

    Tests all components and returns provider-level status.
    """
    return await full_health_check()
