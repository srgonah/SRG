"""
SQLite implementation of material catalog storage.

Handles materials, synonyms, and FTS5 search.
"""

import uuid
from datetime import UTC, datetime

import aiosqlite

from src.config import get_logger
from src.core.entities.material import Material, MaterialSynonym, OriginConfidence
from src.core.interfaces.material_store import IMaterialStore
from src.infrastructure.storage.sqlite.connection import get_connection, get_transaction

logger = get_logger(__name__)


def _generate_id() -> str:
    """Generate a new UUID text ID."""
    return str(uuid.uuid4())


class SQLiteMaterialStore(IMaterialStore):
    """SQLite implementation of material catalog storage."""

    async def create_material(self, material: Material) -> Material:
        """Create a new material record."""
        if not material.id:
            material.id = _generate_id()
        material.updated_at = datetime.now(UTC)
        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO materials (
                    id, name, normalized_name, hs_code, category, unit,
                    description, brand, source_url, origin_country,
                    origin_confidence, evidence_text, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    material.id,
                    material.name,
                    material.normalized_name,
                    material.hs_code,
                    material.category,
                    material.unit,
                    material.description,
                    material.brand,
                    material.source_url,
                    material.origin_country,
                    material.origin_confidence.value,
                    material.evidence_text,
                    material.created_at.isoformat(),
                    material.updated_at.isoformat(),
                ),
            )
            logger.info("material_created", material_id=material.id, name=material.name)
            return material

    async def get_material(self, material_id: str) -> Material | None:
        """Get material by ID with synonyms."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM materials WHERE id = ?", (material_id,)
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            material = self._row_to_material(row)

            # Load synonyms
            syn_cursor = await conn.execute(
                "SELECT synonym FROM material_synonyms WHERE material_id = ?",
                (material_id,),
            )
            syn_rows = await syn_cursor.fetchall()
            material.synonyms = [r["synonym"] for r in syn_rows]

            return material

    async def list_materials(
        self,
        limit: int = 100,
        offset: int = 0,
        category: str | None = None,
    ) -> list[Material]:
        """List materials with pagination and optional category filter."""
        async with get_connection() as conn:
            if category:
                cursor = await conn.execute(
                    """
                    SELECT * FROM materials
                    WHERE category = ?
                    ORDER BY name
                    LIMIT ? OFFSET ?
                    """,
                    (category, limit, offset),
                )
            else:
                cursor = await conn.execute(
                    """
                    SELECT * FROM materials
                    ORDER BY name
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            rows = await cursor.fetchall()
            return [self._row_to_material(row) for row in rows]

    async def search_by_name(self, query: str, limit: int = 20) -> list[Material]:
        """Search materials using FTS5 full-text search."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT m.* FROM materials m
                JOIN materials_fts fts ON m.rowid = fts.rowid
                WHERE materials_fts MATCH ?
                LIMIT ?
                """,
                (query, limit),
            )
            rows = await cursor.fetchall()
            return [self._row_to_material(row) for row in rows]

    async def find_by_synonym(self, synonym: str) -> Material | None:
        """Find a material by one of its synonyms."""
        normalized = synonym.strip().lower()
        async with get_connection() as conn:
            cursor = await conn.execute(
                """
                SELECT m.* FROM materials m
                JOIN material_synonyms ms ON m.id = ms.material_id
                WHERE LOWER(ms.synonym) = ?
                LIMIT 1
                """,
                (normalized,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            material = self._row_to_material(row)

            # Load all synonyms
            syn_cursor = await conn.execute(
                "SELECT synonym FROM material_synonyms WHERE material_id = ?",
                (material.id,),
            )
            syn_rows = await syn_cursor.fetchall()
            material.synonyms = [r["synonym"] for r in syn_rows]

            return material

    async def find_by_normalized_name(self, normalized_name: str) -> Material | None:
        """Find a material by its normalized name."""
        async with get_connection() as conn:
            cursor = await conn.execute(
                "SELECT * FROM materials WHERE normalized_name = ?",
                (normalized_name,),
            )
            row = await cursor.fetchone()
            if row is None:
                return None

            material = self._row_to_material(row)

            # Load synonyms
            syn_cursor = await conn.execute(
                "SELECT synonym FROM material_synonyms WHERE material_id = ?",
                (material.id,),
            )
            syn_rows = await syn_cursor.fetchall()
            material.synonyms = [r["synonym"] for r in syn_rows]

            return material

    async def add_synonym(
        self, material_id: str, synonym: str, language: str = "en"
    ) -> MaterialSynonym:
        """Add a synonym to a material."""
        syn_id = _generate_id()
        async with get_transaction() as conn:
            await conn.execute(
                """
                INSERT INTO material_synonyms (id, material_id, synonym, language)
                VALUES (?, ?, ?, ?)
                """,
                (syn_id, material_id, synonym, language),
            )
            syn = MaterialSynonym(
                id=syn_id,
                material_id=material_id,
                synonym=synonym,
                language=language,
            )
            logger.info(
                "synonym_added",
                material_id=material_id,
                synonym=synonym,
            )
            return syn

    async def remove_synonym(self, synonym_id: str) -> bool:
        """Remove a synonym by ID."""
        async with get_transaction() as conn:
            cursor = await conn.execute(
                "DELETE FROM material_synonyms WHERE id = ?", (synonym_id,)
            )
            return cursor.rowcount > 0

    async def update_material(self, material: Material) -> Material:
        """Update an existing material."""
        material.updated_at = datetime.now(UTC)
        async with get_transaction() as conn:
            await conn.execute(
                """
                UPDATE materials SET
                    name = ?, normalized_name = ?, hs_code = ?,
                    category = ?, unit = ?, description = ?,
                    brand = ?, source_url = ?, origin_country = ?,
                    origin_confidence = ?, evidence_text = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    material.name,
                    material.normalized_name,
                    material.hs_code,
                    material.category,
                    material.unit,
                    material.description,
                    material.brand,
                    material.source_url,
                    material.origin_country,
                    material.origin_confidence.value,
                    material.evidence_text,
                    material.updated_at.isoformat(),
                    material.id,
                ),
            )
            logger.info("material_updated", material_id=material.id)
            return material

    def _row_to_material(self, row: aiosqlite.Row) -> Material:
        """Convert database row to Material entity."""
        # Handle origin_confidence safely (column may not exist in older schemas)
        raw_confidence = None
        try:
            raw_confidence = row["origin_confidence"]
        except (IndexError, KeyError):
            pass
        confidence = OriginConfidence(raw_confidence) if raw_confidence else OriginConfidence.UNKNOWN

        return Material(
            id=row["id"],
            name=row["name"],
            normalized_name=row["normalized_name"],
            hs_code=row["hs_code"],
            category=row["category"],
            unit=row["unit"],
            description=row["description"],
            brand=row["brand"] if "brand" in row.keys() else None,
            source_url=row["source_url"] if "source_url" in row.keys() else None,
            origin_country=row["origin_country"] if "origin_country" in row.keys() else None,
            origin_confidence=confidence,
            evidence_text=row["evidence_text"] if "evidence_text" in row.keys() else None,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )
