"""Abstract interface for local sales storage."""

from abc import ABC, abstractmethod

from src.core.entities.local_sale import LocalSalesInvoice


class ISalesStore(ABC):
    """Interface for local sales invoice persistence."""

    @abstractmethod
    async def create_invoice(self, invoice: LocalSalesInvoice) -> LocalSalesInvoice:
        """Create a sales invoice with all its items."""
        pass

    @abstractmethod
    async def get_invoice(self, invoice_id: int) -> LocalSalesInvoice | None:
        """Get sales invoice by ID with items."""
        pass

    @abstractmethod
    async def list_invoices(
        self, limit: int = 100, offset: int = 0
    ) -> list[LocalSalesInvoice]:
        """List sales invoices with pagination."""
        pass
