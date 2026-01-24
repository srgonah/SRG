"""API v1 router - aggregates all endpoint routers."""

from fastapi import APIRouter

from .endpoints import chat, documents, health, invoices, search, sessions

api_router = APIRouter()

# Include all endpoint routers
api_router.include_router(health.router, prefix="/health", tags=["health"])
api_router.include_router(invoices.router, prefix="/invoices", tags=["invoices"])
api_router.include_router(documents.router, prefix="/documents", tags=["documents"])
api_router.include_router(search.router, prefix="/search", tags=["search"])
api_router.include_router(chat.router, prefix="/chat", tags=["chat"])
api_router.include_router(sessions.router, prefix="/sessions", tags=["sessions"])
