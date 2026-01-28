"""
Abstract interface for price history storage.

Defines the contract for querying price history and statistics.
"""

from abc import ABC, abstractmethod
from typing import Any


class IPriceHistoryStore(ABC):
    """
    Abstract interface for price history querying.

    Reads from existing v002 price history tables.
    """

    @abstractmethod
    async def get_price_history(
        self,
        item_name: str | None = None,
        seller: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get price history entries with optional filters."""
        pass

    @abstractmethod
    async def get_price_stats(
        self,
        item_name: str | None = None,
        seller: str | None = None,
    ) -> list[dict[str, Any]]:
        """Get price statistics from the stats view."""
        pass

    @abstractmethod
    async def link_material(
        self, material_id: str, item_name_normalized: str
    ) -> int:
        """Link price history rows to a material. Returns rows updated."""
        pass
