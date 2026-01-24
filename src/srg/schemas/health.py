"""Health check schemas."""

from pydantic import BaseModel


class ProviderHealth(BaseModel):
    """Health status for a provider component."""

    name: str
    available: bool
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime_seconds: float
    providers: dict[str, ProviderHealth] | None = None
