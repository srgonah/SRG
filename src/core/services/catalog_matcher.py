"""
Catalog matching service.

Finds matching materials for a given item name using a prioritized
strategy: exact name, synonym, then fuzzy (Levenshtein) matching.
Uses only stdlib (difflib.SequenceMatcher) for fuzzy comparison.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher

from src.config import get_logger
from src.core.interfaces.material_store import IMaterialStore

logger = get_logger(__name__)

# Minimum fuzzy similarity ratio to consider a match
FUZZY_THRESHOLD = 0.6

# Similarity threshold for duplicate detection
DUPLICATE_THRESHOLD = 0.9


@dataclass
class MatchCandidate:
    """A material that matches a query with a confidence score."""

    material_id: str
    material_name: str
    score: float  # 0.0 to 1.0
    match_type: str  # "exact_name", "synonym", "fuzzy"


def _normalize(name: str) -> str:
    """Normalize a name for comparison: strip, lowercase, collapse whitespace."""
    result = name.strip().lower()
    result = re.sub(r"\s+", " ", result)
    return result


def _fuzzy_ratio(a: str, b: str) -> float:
    """Compute normalized Levenshtein-like similarity ratio using SequenceMatcher."""
    return SequenceMatcher(None, a, b).ratio()


class CatalogMatcher:
    """
    Service for finding matching materials in the catalog.

    Matching strategy (priority order):
    1. Exact normalized name  -> score 1.0, match_type "exact_name"
    2. Synonym match          -> score 0.9, match_type "synonym"
    3. Fuzzy match            -> score = ratio, match_type "fuzzy", min 0.6

    Pure service -- no infrastructure imports. The material store is
    injected via constructor.
    """

    def __init__(self, material_store: IMaterialStore) -> None:
        self._material_store = material_store

    async def find_matches(
        self,
        query: str,
        top_k: int = 5,
    ) -> list[MatchCandidate]:
        """
        Find top-K matching materials for a given item name.

        Args:
            query: The item name to search for.
            top_k: Maximum number of candidates to return.

        Returns:
            List of MatchCandidate sorted by score descending.
        """
        normalized_query = _normalize(query)
        if not normalized_query:
            return []

        candidates: list[MatchCandidate] = []
        seen_ids: set[str] = set()

        # 1. Exact normalized name match
        exact = await self._material_store.find_by_normalized_name(normalized_query)
        if exact is not None and exact.id is not None:
            candidates.append(
                MatchCandidate(
                    material_id=exact.id,
                    material_name=exact.name,
                    score=1.0,
                    match_type="exact_name",
                )
            )
            seen_ids.add(exact.id)

        # 2. Synonym match
        synonym_match = await self._material_store.find_by_synonym(normalized_query)
        if (
            synonym_match is not None
            and synonym_match.id is not None
            and synonym_match.id not in seen_ids
        ):
            candidates.append(
                MatchCandidate(
                    material_id=synonym_match.id,
                    material_name=synonym_match.name,
                    score=0.9,
                    match_type="synonym",
                )
            )
            seen_ids.add(synonym_match.id)

        # 3. Fuzzy match against all materials
        # Fetch a broad set of materials to compare against.
        all_materials = await self._material_store.list_materials(limit=500)

        for material in all_materials:
            if material.id is None or material.id in seen_ids:
                continue

            # Compare against normalized name
            ratio = _fuzzy_ratio(normalized_query, _normalize(material.name))

            # Also compare against each synonym and keep the best score
            for syn in material.synonyms:
                syn_ratio = _fuzzy_ratio(normalized_query, _normalize(syn))
                if syn_ratio > ratio:
                    ratio = syn_ratio

            if ratio >= FUZZY_THRESHOLD:
                candidates.append(
                    MatchCandidate(
                        material_id=material.id,
                        material_name=material.name,
                        score=round(ratio, 4),
                        match_type="fuzzy",
                    )
                )
                seen_ids.add(material.id)

        # Sort by score descending, then limit
        candidates.sort(key=lambda c: c.score, reverse=True)
        return candidates[:top_k]

    async def check_duplicate(
        self,
        name: str,
        exclude_id: str | None = None,
    ) -> MatchCandidate | None:
        """
        Check if a material with >90% name similarity already exists.

        Args:
            name: The material name to check.
            exclude_id: Optional material ID to exclude (e.g. the material
                being updated).

        Returns:
            A MatchCandidate if a near-duplicate is found, else None.
        """
        normalized = _normalize(name)
        if not normalized:
            return None

        # Check exact first
        exact = await self._material_store.find_by_normalized_name(normalized)
        if exact is not None and exact.id is not None and exact.id != exclude_id:
            return MatchCandidate(
                material_id=exact.id,
                material_name=exact.name,
                score=1.0,
                match_type="exact_name",
            )

        # Scan all materials for near-duplicates
        all_materials = await self._material_store.list_materials(limit=500)

        best: MatchCandidate | None = None
        best_score = 0.0

        for material in all_materials:
            if material.id is None or material.id == exclude_id:
                continue

            ratio = _fuzzy_ratio(normalized, _normalize(material.name))
            if ratio >= DUPLICATE_THRESHOLD and ratio > best_score:
                best_score = ratio
                best = MatchCandidate(
                    material_id=material.id,
                    material_name=material.name,
                    score=round(ratio, 4),
                    match_type="fuzzy" if ratio < 1.0 else "exact_name",
                )

        return best
