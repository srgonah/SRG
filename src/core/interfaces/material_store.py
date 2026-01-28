"""
Abstract interface for material catalog storage.

Defines the contract for material CRUD, synonym management,
and full-text search operations.
"""

from abc import ABC, abstractmethod

from src.core.entities.material import Material, MaterialSynonym


class IMaterialStore(ABC):
    """
    Abstract interface for material catalog storage.

    Handles materials, synonyms, and FTS search.
    """

    @abstractmethod
    async def create_material(self, material: Material) -> Material:
        """Create a new material record."""

    @abstractmethod
    async def get_material(self, material_id: str) -> Material | None:
        """Get material by ID with synonyms."""

    @abstractmethod
    async def list_materials(
        self,
        limit: int = 100,
        offset: int = 0,
        category: str | None = None,
    ) -> list[Material]:
        """List materials with pagination and optional category filter."""

    @abstractmethod
    async def search_by_name(self, query: str, limit: int = 20) -> list[Material]:
        """Search materials using FTS5 full-text search."""

    @abstractmethod
    async def find_by_synonym(self, synonym: str) -> Material | None:
        """Find a material by one of its synonyms."""

    @abstractmethod
    async def find_by_normalized_name(self, normalized_name: str) -> Material | None:
        """Find a material by its normalized name."""

    @abstractmethod
    async def add_synonym(
        self, material_id: str, synonym: str, language: str = "en"
    ) -> MaterialSynonym:
        """Add a synonym to a material."""

    @abstractmethod
    async def remove_synonym(self, synonym_id: str) -> bool:
        """Remove a synonym by ID."""

    @abstractmethod
    async def update_material(self, material: Material) -> Material:
        """Update an existing material."""
