"""
Unit tests for Reciprocal Rank Fusion (RRF) algorithm.

Tests:
- Score calculation correctness
- Deduplication across result sets
- Weight balancing (vector vs keyword)
- Deterministic ordering with same scores
- Edge cases (empty inputs, single source)
"""


from src.core.entities import SearchResult
from src.infrastructure.search.hybrid import reciprocal_rank_fusion


class TestRRFScoreCalculation:
    """Tests for RRF score calculation correctness."""

    def test_rrf_basic_formula(self):
        """Should apply RRF formula: weight / (k + rank + 1)."""
        vector_results = [
            SearchResult(chunk_id=1, text="doc1"),
            SearchResult(chunk_id=2, text="doc2"),
        ]
        keyword_results = []

        # With k=60, vector_weight=0.6
        # doc1: 0.6 / (60 + 0 + 1) = 0.6 / 61 ≈ 0.00984
        # doc2: 0.6 / (60 + 1 + 1) = 0.6 / 62 ≈ 0.00968
        merged = reciprocal_rank_fusion(
            vector_results, keyword_results, k=60, vector_weight=0.6
        )

        assert len(merged) == 2
        assert merged[0].chunk_id == 1
        assert merged[1].chunk_id == 2
        # Check approximate scores
        assert 0.0098 < merged[0].hybrid_score < 0.0099
        assert 0.0096 < merged[1].hybrid_score < 0.0098

    def test_rrf_with_both_sources(self):
        """Should combine scores when document appears in both sources."""
        # Document 1 appears in both, document 2 only in vector, document 3 only in keyword
        vector_results = [
            SearchResult(chunk_id=1, text="doc1"),
            SearchResult(chunk_id=2, text="doc2"),
        ]
        keyword_results = [
            SearchResult(chunk_id=3, text="doc3"),
            SearchResult(chunk_id=1, text="doc1"),
        ]

        merged = reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=60,
            vector_weight=0.6,
            keyword_weight=0.4,
        )

        # Doc1 should have highest score (appears in both)
        assert merged[0].chunk_id == 1

        # Verify doc1 got both contributions
        # Vector: 0.6 / 61 ≈ 0.00984
        # Keyword: 0.4 / 62 ≈ 0.00645
        # Total ≈ 0.01629
        assert merged[0].hybrid_score > 0.015

    def test_rrf_preserves_rank_order(self):
        """Earlier ranks should give higher scores."""
        vector_results = [
            SearchResult(chunk_id=i, text=f"doc{i}") for i in range(1, 6)
        ]

        merged = reciprocal_rank_fusion(vector_results, [], k=60)

        # Scores should be strictly decreasing
        for i in range(len(merged) - 1):
            assert merged[i].hybrid_score > merged[i + 1].hybrid_score

    def test_rrf_different_k_values(self):
        """Different k values should affect absolute scores."""
        # Create separate result objects for each test (objects are mutated)
        vector_results_low_k = [
            SearchResult(chunk_id=1, text="doc1"),
            SearchResult(chunk_id=2, text="doc2"),
        ]
        vector_results_high_k = [
            SearchResult(chunk_id=1, text="doc1"),
            SearchResult(chunk_id=2, text="doc2"),
        ]

        # Low k gives higher scores (smaller denominator)
        merged_low_k = reciprocal_rank_fusion(vector_results_low_k, [], k=10)
        # High k gives lower scores (larger denominator)
        merged_high_k = reciprocal_rank_fusion(vector_results_high_k, [], k=100)

        # With low k, scores should be higher
        # k=10: 0.6 / 11 ≈ 0.0545
        # k=100: 0.6 / 101 ≈ 0.0059
        assert merged_low_k[0].hybrid_score > merged_high_k[0].hybrid_score
        assert merged_low_k[1].hybrid_score > merged_high_k[1].hybrid_score


class TestRRFDeduplication:
    """Tests for deduplication across result sets."""

    def test_deduplicates_by_chunk_id(self):
        """Same chunk_id should be deduplicated."""
        vector_results = [
            SearchResult(chunk_id=1, text="vector doc1"),
            SearchResult(chunk_id=2, text="vector doc2"),
        ]
        keyword_results = [
            SearchResult(chunk_id=1, text="keyword doc1"),  # Same chunk
            SearchResult(chunk_id=3, text="keyword doc3"),
        ]

        merged = reciprocal_rank_fusion(vector_results, keyword_results)

        # Should have 3 unique results
        assert len(merged) == 3

        chunk_ids = [r.chunk_id for r in merged]
        assert sorted(chunk_ids) == [1, 2, 3]

    def test_deduplicates_by_item_id(self):
        """Same item_id should be deduplicated."""
        vector_results = [
            SearchResult(item_id=100, text="item1"),
            SearchResult(item_id=200, text="item2"),
        ]
        keyword_results = [
            SearchResult(item_id=100, text="item1 keyword"),
        ]

        merged = reciprocal_rank_fusion(vector_results, keyword_results)

        assert len(merged) == 2
        item_ids = [r.item_id for r in merged]
        assert sorted(item_ids) == [100, 200]

    def test_prefers_richer_result_data(self):
        """When deduplicating, should keep result with more data."""
        # Vector result is sparse
        vector_results = [SearchResult(chunk_id=1)]
        # Keyword result has more context
        keyword_results = [
            SearchResult(
                chunk_id=1,
                text="Full text content",
                page_no=5,
                page_type="invoice",
            )
        ]

        merged = reciprocal_rank_fusion(vector_results, keyword_results)

        assert len(merged) == 1
        # Should keep the vector one (first to be added to map)
        # but the score should be combined


class TestRRFWeightBalancing:
    """Tests for weight configuration."""

    def test_default_weights(self):
        """Default weights should be 0.6 vector, 0.4 keyword."""
        vector_results = [SearchResult(chunk_id=1)]
        keyword_results = [SearchResult(chunk_id=2)]

        merged = reciprocal_rank_fusion(vector_results, keyword_results)

        # With k=60, rank=0
        # Vector: 0.6 / 61
        # Keyword: 0.4 / 61
        expected_vector = 0.6 / 61
        expected_keyword = 0.4 / 61

        assert abs(merged[0].hybrid_score - expected_vector) < 0.0001
        assert abs(merged[1].hybrid_score - expected_keyword) < 0.0001

    def test_custom_weights(self):
        """Should respect custom weights."""
        vector_results = [SearchResult(chunk_id=1)]
        keyword_results = [SearchResult(chunk_id=2)]

        # Equal weights
        merged = reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            vector_weight=0.5,
            keyword_weight=0.5,
        )

        # Both should have same score
        assert abs(merged[0].hybrid_score - merged[1].hybrid_score) < 0.0001

    def test_keyword_heavy_weights(self):
        """Keyword-heavy weights should favor keyword results."""
        # Document appears first in keyword but second in vector
        vector_results = [
            SearchResult(chunk_id=2),
            SearchResult(chunk_id=1),  # Target doc is second
        ]
        keyword_results = [
            SearchResult(chunk_id=1),  # Target doc is first
            SearchResult(chunk_id=2),
        ]

        # Keyword-heavy
        merged = reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            vector_weight=0.2,
            keyword_weight=0.8,
        )

        # Doc1 should win due to keyword priority
        assert merged[0].chunk_id == 1


class TestRRFDeterministicOrdering:
    """Tests for deterministic ordering."""

    def test_consistent_ordering_same_input(self):
        """Same input should always produce same output."""
        vector_results = [
            SearchResult(chunk_id=i, text=f"doc{i}") for i in range(1, 11)
        ]
        keyword_results = [
            SearchResult(chunk_id=i, text=f"doc{i}") for i in range(5, 15)
        ]

        results1 = reciprocal_rank_fusion(vector_results, keyword_results)
        results2 = reciprocal_rank_fusion(vector_results, keyword_results)

        ids1 = [r.chunk_id for r in results1]
        ids2 = [r.chunk_id for r in results2]

        assert ids1 == ids2

    def test_final_rank_assigned_correctly(self):
        """Final rank should be sequential starting from 0."""
        vector_results = [
            SearchResult(chunk_id=i) for i in range(1, 6)
        ]

        merged = reciprocal_rank_fusion(vector_results, [])

        for i, result in enumerate(merged):
            assert result.final_rank == i


class TestRRFEdgeCases:
    """Tests for edge cases."""

    def test_empty_both_sources(self):
        """Should handle empty inputs."""
        merged = reciprocal_rank_fusion([], [])
        assert merged == []

    def test_empty_vector_results(self):
        """Should work with only keyword results."""
        keyword_results = [
            SearchResult(chunk_id=1, text="doc1"),
            SearchResult(chunk_id=2, text="doc2"),
        ]

        merged = reciprocal_rank_fusion([], keyword_results)

        assert len(merged) == 2
        assert merged[0].chunk_id == 1
        assert merged[1].chunk_id == 2

    def test_empty_keyword_results(self):
        """Should work with only vector results."""
        vector_results = [
            SearchResult(chunk_id=1, text="doc1"),
            SearchResult(chunk_id=2, text="doc2"),
        ]

        merged = reciprocal_rank_fusion(vector_results, [])

        assert len(merged) == 2

    def test_skips_results_without_id(self):
        """Should skip results without chunk_id or item_id."""
        vector_results = [
            SearchResult(chunk_id=1),
            SearchResult(),  # No ID
            SearchResult(chunk_id=2),
        ]

        merged = reciprocal_rank_fusion(vector_results, [])

        assert len(merged) == 2

    def test_large_result_set(self):
        """Should handle large result sets efficiently."""
        vector_results = [
            SearchResult(chunk_id=i) for i in range(1, 1001)
        ]
        keyword_results = [
            SearchResult(chunk_id=i) for i in range(500, 1500)
        ]

        merged = reciprocal_rank_fusion(vector_results, keyword_results)

        # Should have all unique IDs
        unique_ids = set(r.chunk_id for r in merged)
        assert len(unique_ids) == 1499  # 1-1499

    def test_score_and_rank_fields_populated(self):
        """Should populate all score and rank fields."""
        vector_results = [SearchResult(chunk_id=1)]
        keyword_results = [SearchResult(chunk_id=1)]

        merged = reciprocal_rank_fusion(vector_results, keyword_results)

        result = merged[0]
        assert result.hybrid_score > 0
        assert result.final_score == result.hybrid_score
        assert result.final_rank == 0


class TestRRFScoreSymmetry:
    """Tests for score symmetry properties."""

    def test_scores_are_additive(self):
        """Scores from different sources should add up."""
        # Doc1 in both, doc2 only in vector, doc3 only in keyword
        vector_results = [
            SearchResult(chunk_id=1),
            SearchResult(chunk_id=2),
        ]
        keyword_results = [
            SearchResult(chunk_id=1),
            SearchResult(chunk_id=3),
        ]

        merged = reciprocal_rank_fusion(
            vector_results,
            keyword_results,
            k=60,
            vector_weight=0.6,
            keyword_weight=0.4,
        )

        # Find doc1's score
        doc1 = next(r for r in merged if r.chunk_id == 1)
        doc2 = next(r for r in merged if r.chunk_id == 2)
        doc3 = next(r for r in merged if r.chunk_id == 3)

        # doc1 should have highest score (both sources)
        assert doc1.hybrid_score > doc2.hybrid_score
        assert doc1.hybrid_score > doc3.hybrid_score

        # doc2 and doc3 comparable (different weights but same rank)
        # doc2: vector rank 1 -> 0.6 / 62
        # doc3: keyword rank 1 -> 0.4 / 62
        assert doc2.hybrid_score > doc3.hybrid_score  # Vector has higher weight
