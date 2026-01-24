"""API route modules."""

from src.api.routes.chat import router as chat_router
from src.api.routes.documents import router as documents_router
from src.api.routes.health import router as health_router
from src.api.routes.invoices import router as invoices_router
from src.api.routes.search import router as search_router
from src.api.routes.sessions import router as sessions_router

__all__ = [
    "health_router",
    "invoices_router",
    "documents_router",
    "search_router",
    "chat_router",
    "sessions_router",
]
