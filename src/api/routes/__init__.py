"""API route modules."""

from src.api.routes.catalog import router as catalog_router
from src.api.routes.chat import router as chat_router
from src.api.routes.company_documents import router as company_documents_router
from src.api.routes.documents import router as documents_router
from src.api.routes.health import router as health_router
from src.api.routes.inventory import router as inventory_router
from src.api.routes.invoices import router as invoices_router
from src.api.routes.prices import router as prices_router
from src.api.routes.reminders import router as reminders_router
from src.api.routes.sales import router as sales_router
from src.api.routes.search import router as search_router
from src.api.routes.sessions import router as sessions_router

__all__ = [
    "health_router",
    "invoices_router",
    "documents_router",
    "search_router",
    "chat_router",
    "sessions_router",
    "catalog_router",
    "prices_router",
    "company_documents_router",
    "reminders_router",
    "inventory_router",
    "sales_router",
]
