"""Unit tests for CatalogMatcher service."""

from unittest.mock import AsyncMock

import pytest

from src.core.entities.material import Material
from src.core.services.catalog_matcher import (
    DUPLICATE_THRESHOLD,
    FUZZY_THRESHOLD,
    CatalogMatcher,
    MatchCandidate,
    _fuzzy_ratio,
    _normalize,
)


def _make_material(
    mat_id: str,
    name: str,
    synonyms: list[str] | None = None,
    **kwargs,
) -> Material:
    """Create a Material entity with defaults."""
    return Material(
        id=mat_id,
        name=name,
        normalized_name=name.strip().lower(),
        synonyms=synonyms or [],
        **kwargs,
    )


def _make_store(materials: list[Material] | None = None):
    """Create a mock IMaterialStore."""
    materials = materials or []
    store = AsyncMock()
    store.find_by_normalized_name = AsyncMock(return_value=None)
    store.find_by_synonym = AsyncMock(return_value=None)
    store.list_materials = AsyncMock(return_value=materials)
    return store


@pytest.mark.asyncio
class TestExactNameMatching:
    """Tests for exact normalized name matching."""

    async def test_exact_match_returns_score_1(self):
        """Exact normalized name match returns score 1.0."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("PVC Cable 10mm")

        assert len(results) >= 1
        assert results[0].material_id == "m1"
        assert results[0].score == 1.0
        assert results[0].match_type == "exact_name"

    async def test_exact_match_case_insensitive(self):
        """Exact match works regardless of case."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("pvc cable 10mm")

        assert len(results) >= 1
        assert results[0].score == 1.0
        assert results[0].match_type == "exact_name"

    async def test_exact_match_with_whitespace_normalization(self):
        """Exact match normalizes whitespace."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("  PVC  Cable   10mm  ")

        assert len(results) >= 1
        assert results[0].score == 1.0


@pytest.mark.asyncio
class TestSynonymMatching:
    """Tests for synonym-based matching."""

    async def test_synonym_match_returns_score_09(self):
        """Synonym match returns score 0.9."""
        mat = _make_material("m1", "PVC Cable 10mm", synonyms=["polyvinyl cable"])
        store = _make_store([mat])
        store.find_by_synonym.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("polyvinyl cable")

        assert len(results) >= 1
        # The synonym match should be in the results with score 0.9
        synonym_results = [r for r in results if r.match_type == "synonym"]
        assert len(synonym_results) >= 1
        assert synonym_results[0].score == 0.9

    async def test_synonym_not_duplicated_with_exact(self):
        """If exact match and synonym resolve to the same material, no duplicate."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat
        store.find_by_synonym.return_value = mat  # same material

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("PVC Cable 10mm")

        # Should only appear once (as exact_name)
        ids = [r.material_id for r in results]
        assert ids.count("m1") == 1


@pytest.mark.asyncio
class TestFuzzyMatching:
    """Tests for fuzzy Levenshtein matching."""

    async def test_fuzzy_match_returns_correct_score(self):
        """Fuzzy match uses SequenceMatcher ratio."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("PVC Cable 12mm")

        assert len(results) >= 1
        fuzzy_results = [r for r in results if r.match_type == "fuzzy"]
        assert len(fuzzy_results) >= 1
        # Score should be between threshold and 1.0
        assert FUZZY_THRESHOLD <= fuzzy_results[0].score < 1.0

    async def test_items_below_threshold_excluded(self):
        """Items with similarity below 0.6 are excluded."""
        mat = _make_material("m1", "Completely Different Product XYZ")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Steel Rod 12mm")

        # The ratio between these names should be well below 0.6
        fuzzy_results = [r for r in results if r.material_id == "m1"]
        assert len(fuzzy_results) == 0

    async def test_fuzzy_score_range(self):
        """Fuzzy score is between 0.0 and 1.0."""
        mat = _make_material("m1", "Steel Rod 12mm")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Steel Rod 14mm")

        for r in results:
            assert 0.0 <= r.score <= 1.0

    async def test_fuzzy_matches_synonyms_too(self):
        """Fuzzy matching also considers material synonyms."""
        mat = _make_material("m1", "Cement Type I", synonyms=["Portland Cement"])
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Portland Cemen")  # slight typo

        # Should find a fuzzy match via the synonym
        matching = [r for r in results if r.material_id == "m1"]
        assert len(matching) >= 1


@pytest.mark.asyncio
class TestTopKLimiting:
    """Tests for top-K result limiting."""

    async def test_top_k_limits_results(self):
        """Only top_k candidates are returned."""
        materials = [
            _make_material(f"m{i}", f"Cable Type {i}")
            for i in range(10)
        ]
        store = _make_store(materials)

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Cable Type", top_k=3)

        assert len(results) <= 3

    async def test_results_sorted_by_score_descending(self):
        """Results are sorted by score descending."""
        materials = [
            _make_material("m1", "Steel Rod 12mm"),
            _make_material("m2", "Steel Rod 14mm"),
            _make_material("m3", "Steel Wire 12mm"),
        ]
        store = _make_store(materials)

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Steel Rod 12mm")

        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
class TestEmptyCatalog:
    """Tests for empty catalog scenarios."""

    async def test_empty_catalog_returns_no_matches(self):
        """No materials in catalog returns empty list."""
        store = _make_store([])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Some Item")

        assert results == []

    async def test_empty_query_returns_no_matches(self):
        """Empty query string returns empty list."""
        store = _make_store([_make_material("m1", "Widget")])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("")

        assert results == []

    async def test_whitespace_only_query_returns_no_matches(self):
        """Whitespace-only query returns empty list."""
        store = _make_store([_make_material("m1", "Widget")])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("   ")

        assert results == []


@pytest.mark.asyncio
class TestUnicodeNames:
    """Tests for Unicode material names."""

    async def test_arabic_names(self):
        """Arabic material names are handled correctly."""
        mat = _make_material("m1", "كابل كهربائي")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("كابل كهربائي")

        assert len(results) >= 1
        assert results[0].material_id == "m1"
        assert results[0].score == 1.0

    async def test_chinese_names(self):
        """Chinese material names are handled correctly."""
        mat = _make_material("m1", "电缆线")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("电缆线")

        assert len(results) >= 1
        assert results[0].material_id == "m1"
        assert results[0].score == 1.0

    async def test_mixed_unicode_fuzzy(self):
        """Fuzzy matching works with Unicode characters."""
        mat = _make_material("m1", "PVC كابل 10mm")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("PVC كابل 12mm")

        # Should find a fuzzy match
        matching = [r for r in results if r.material_id == "m1"]
        assert len(matching) >= 1
        assert matching[0].score >= FUZZY_THRESHOLD


@pytest.mark.asyncio
class TestAbbreviationsAndCaseInsensitivity:
    """Tests for abbreviation handling and case insensitivity."""

    async def test_case_insensitive_fuzzy(self):
        """Fuzzy matching is case insensitive."""
        mat = _make_material("m1", "POLYVINYL CHLORIDE CABLE")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("polyvinyl chloride cable")

        matching = [r for r in results if r.material_id == "m1"]
        assert len(matching) >= 1

    async def test_abbreviation_fuzzy_match(self):
        """Common abbreviations can be fuzzy-matched."""
        mat = _make_material("m1", "Stainless Steel")
        store = _make_store([mat])

        # "Stainless Stel" is a close misspelling
        matcher = CatalogMatcher(material_store=store)
        results = await matcher.find_matches("Stainless Stel")

        matching = [r for r in results if r.material_id == "m1"]
        assert len(matching) >= 1
        assert matching[0].score >= FUZZY_THRESHOLD


@pytest.mark.asyncio
class TestDuplicateDetection:
    """Tests for the check_duplicate method."""

    async def test_exact_duplicate_detected(self):
        """Exact name match is detected as duplicate."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        result = await matcher.check_duplicate("PVC Cable 10mm")

        assert result is not None
        assert result.material_id == "m1"
        assert result.score == 1.0

    async def test_near_duplicate_detected(self):
        """Near-duplicate (>90% similarity) is detected."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        # Very similar name
        result = await matcher.check_duplicate("PVC Cable 10mn")

        assert result is not None
        assert result.material_id == "m1"
        assert result.score >= DUPLICATE_THRESHOLD

    async def test_no_duplicate_for_different_name(self):
        """No duplicate detected for sufficiently different name."""
        mat = _make_material("m1", "Steel Rod 12mm")
        store = _make_store([mat])

        matcher = CatalogMatcher(material_store=store)
        result = await matcher.check_duplicate("Cement Portland Type I")

        assert result is None

    async def test_exclude_id_skips_self(self):
        """exclude_id prevents matching the material being updated."""
        mat = _make_material("m1", "PVC Cable 10mm")
        store = _make_store([mat])
        store.find_by_normalized_name.return_value = mat

        matcher = CatalogMatcher(material_store=store)
        result = await matcher.check_duplicate("PVC Cable 10mm", exclude_id="m1")

        assert result is None

    async def test_empty_name_returns_none(self):
        """Empty name returns None (no duplicate)."""
        store = _make_store([])

        matcher = CatalogMatcher(material_store=store)
        result = await matcher.check_duplicate("")

        assert result is None


class TestHelpers:
    """Tests for helper functions."""

    def test_normalize_strips_and_lowercases(self):
        """_normalize strips whitespace and lowercases."""
        assert _normalize("  HELLO  ") == "hello"

    def test_normalize_collapses_whitespace(self):
        """_normalize collapses multiple whitespace."""
        assert _normalize("a  b   c") == "a b c"

    def test_fuzzy_ratio_identical(self):
        """Identical strings return ratio 1.0."""
        assert _fuzzy_ratio("hello", "hello") == 1.0

    def test_fuzzy_ratio_different(self):
        """Completely different strings return low ratio."""
        ratio = _fuzzy_ratio("abc", "xyz")
        assert ratio < 0.5

    def test_fuzzy_ratio_similar(self):
        """Similar strings return a high ratio."""
        ratio = _fuzzy_ratio("cable 10mm", "cable 12mm")
        assert ratio > 0.7
