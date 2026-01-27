"""
Unit tests for hybrid search flow with mocked dependencies.

Tests:
- Full pipeline: vector + keyword + RRF + optional rerank
- Component integration
- Error handling and fallbacks
- Search type routing
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.entities import SearchResult
from src.infrastructure.search.hybrid import HybridSearcher, reciprocal_rank_fusion


class TestHybridSearcherChunks:
    """Tests for HybridSearcher.search_chunks with mocked components."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        settings = MagicMock()
        settings.search.faiss_candidates = 60
        settings.search.rrf_k = 60
        settings.search.reranker_enabled = True
        settings.search.reranker_model = "BAAI/bge-reranker-v2-m3"
        settings.search.reranker_top_k = 10
        return settings

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_reranker")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_full_hybrid_flow(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_get_reranker,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should execute full hybrid pipeline: vector + keyword + RRF."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False  # Disable reranker for this test

        # Mock vector store
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [
            (1, 0.95),
            (2, 0.85),
            (3, 0.75),
        ]
        mock_get_vector_store.return_value = mock_vector_store

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        # Mock FTS
        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock(
            return_value=[
                SearchResult(chunk_id=2, text="doc2", fts_score=10.0),
                SearchResult(chunk_id=4, text="doc4", fts_score=8.0),
                SearchResult(chunk_id=1, text="doc1", fts_score=6.0),
            ]
        )
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        results = await searcher.search_chunks(
            "test query",
            top_k=5,
            use_hybrid=True,
            use_reranker=False,
        )

        # Should have results from both sources
        assert len(results) > 0

        # Doc1 and Doc2 appear in both -> should have higher scores
        chunk_ids = [r.chunk_id for r in results[:3]]
        assert 1 in chunk_ids or 2 in chunk_ids

        # Verify RRF scores are set
        for result in results:
            assert result.hybrid_score > 0

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_vector_only_mode(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should return only vector results when hybrid disabled."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        # Mock vector store
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [
            (1, 0.95),
            (2, 0.85),
        ]
        mock_get_vector_store.return_value = mock_vector_store

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        # FTS should not be called
        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock()
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        results = await searcher.search_chunks(
            "test query",
            top_k=5,
            use_hybrid=False,
            use_reranker=False,
        )

        assert len(results) == 2
        # FTS should not have been called
        mock_fts.search_chunks.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_reranker")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_with_reranker(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_get_reranker,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should apply reranker when enabled."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = True

        # Mock vector store
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [(1, 0.9), (2, 0.8), (3, 0.7)]
        mock_get_vector_store.return_value = mock_vector_store

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        # Mock FTS
        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock(
            return_value=[
                SearchResult(chunk_id=1, text="doc1", fts_score=10.0),
                SearchResult(chunk_id=2, text="doc2", fts_score=8.0),
            ]
        )
        mock_get_fts.return_value = mock_fts

        # Mock reranker - reorder results
        mock_reranker = MagicMock()
        mock_reranker.rerank = AsyncMock(
            return_value=[
                (2, 0.95),  # doc3 reranked to first
                (0, 0.85),  # doc1 reranked to second
                (1, 0.75),  # doc2 reranked to third
            ]
        )
        mock_get_reranker.return_value = mock_reranker

        searcher = HybridSearcher()
        results = await searcher.search_chunks(
            "test query",
            top_k=3,
            use_hybrid=True,
            use_reranker=True,
        )

        # Reranker should have been called
        mock_reranker.rerank.assert_called_once()

        # Results should have reranker_score
        for result in results:
            assert result.reranker_score is not None


class TestHybridSearcherItems:
    """Tests for HybridSearcher.search_items."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.search.faiss_candidates = 60
        settings.search.rrf_k = 60
        settings.search.reranker_enabled = False
        return settings

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_search_items_hybrid(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should search items using hybrid approach."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        # Mock vector store
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [
            (100, 0.9),
            (101, 0.8),
        ]
        mock_get_vector_store.return_value = mock_vector_store

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        # Mock FTS
        mock_fts = MagicMock()
        mock_fts.search_items = AsyncMock(
            return_value=[
                SearchResult(
                    item_id=100,
                    item_name="Circuit Breaker",
                    hs_code="85362000",
                    fts_score=10.0,
                ),
                SearchResult(
                    item_id=102,
                    item_name="Plastic Part",
                    hs_code="39231000",
                    fts_score=8.0,
                ),
            ]
        )
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        results = await searcher.search_items(
            "circuit breaker",
            top_k=10,
            use_hybrid=True,
        )

        # Item 100 appears in both -> should be first
        assert results[0].item_id == 100
        assert results[0].hybrid_score > 0


class TestHybridSearcherErrorHandling:
    """Tests for error handling in hybrid search."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.search.faiss_candidates = 60
        settings.search.rrf_k = 60
        settings.search.reranker_enabled = False
        return settings

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_fallback_on_vector_error(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should fall back to keyword results if vector search fails."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        # Mock vector store to fail
        mock_vector_store = AsyncMock()
        mock_vector_store.search.side_effect = Exception("Vector store error")
        mock_get_vector_store.return_value = mock_vector_store

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_single.side_effect = Exception("Embedder error")
        mock_get_embedder.return_value = mock_embedder

        # Mock FTS to succeed
        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock(
            return_value=[
                SearchResult(chunk_id=1, text="fallback result", fts_score=5.0),
            ]
        )
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        results = await searcher.search_chunks("test", top_k=5, use_hybrid=True)

        # Should still return keyword results
        assert len(results) == 1
        assert results[0].chunk_id == 1

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_fallback_on_keyword_error(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should fall back to vector results if keyword search fails."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        # Mock vector store to succeed
        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [(1, 0.9)]
        mock_get_vector_store.return_value = mock_vector_store

        # Mock embedder
        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        # Mock FTS to fail
        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock(side_effect=Exception("FTS error"))
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        results = await searcher.search_chunks("test", top_k=5, use_hybrid=True)

        # Should still return vector results (via RRF with empty keyword)
        assert len(results) == 1


class TestHybridSearcherRouting:
    """Tests for search routing via the universal search method."""

    @pytest.fixture
    def mock_settings(self):
        settings = MagicMock()
        settings.search.faiss_candidates = 60
        settings.search.rrf_k = 60
        settings.search.reranker_enabled = False
        return settings

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_routes_to_items_search(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should route 'items' search type to search_items."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = []
        mock_get_vector_store.return_value = mock_vector_store

        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        mock_fts = MagicMock()
        mock_fts.search_items = AsyncMock(return_value=[])
        mock_fts.search_chunks = AsyncMock(return_value=[])
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        await searcher.search("test", top_k=10, search_type="items")

        # Should have called search_items, not search_chunks
        mock_fts.search_items.assert_called_once()
        mock_fts.search_chunks.assert_not_called()

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_routes_to_hybrid_search(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should route 'hybrid' search type to search_chunks with hybrid."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = []
        mock_get_vector_store.return_value = mock_vector_store

        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock(return_value=[])
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        await searcher.search("test", top_k=10, search_type="hybrid")

        # Should have called both vector and keyword
        mock_vector_store.search.assert_called()
        mock_fts.search_chunks.assert_called()

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.hybrid.is_reranker_enabled")
    @patch("src.infrastructure.search.hybrid.get_fts_searcher")
    @patch("src.infrastructure.search.hybrid.get_embedding_provider")
    @patch("src.infrastructure.search.hybrid.get_vector_store")
    @patch("src.infrastructure.search.hybrid.get_settings")
    async def test_routes_to_vector_only_search(
        self,
        mock_get_settings,
        mock_get_vector_store,
        mock_get_embedder,
        mock_get_fts,
        mock_is_reranker_enabled,
        mock_settings,
    ):
        """Should route 'vector' search type to vector-only search."""
        mock_get_settings.return_value = mock_settings
        mock_is_reranker_enabled.return_value = False

        mock_vector_store = AsyncMock()
        mock_vector_store.search.return_value = [(1, 0.9)]
        mock_get_vector_store.return_value = mock_vector_store

        mock_embedder = MagicMock()
        mock_embedder.embed_single.return_value = [0.1] * 1024
        mock_get_embedder.return_value = mock_embedder

        mock_fts = MagicMock()
        mock_fts.search_chunks = AsyncMock(return_value=[])
        mock_get_fts.return_value = mock_fts

        searcher = HybridSearcher()
        await searcher.search("test", top_k=10, search_type="vector")

        # FTS should NOT be called for vector-only
        mock_fts.search_chunks.assert_not_called()


class TestHybridSearcherDeterminism:
    """Tests for deterministic ordering in hybrid search."""

    def test_rrf_deterministic_with_same_input(self):
        """RRF should produce deterministic results."""
        vector_results = [
            SearchResult(chunk_id=i, faiss_score=1.0 - i * 0.1)
            for i in range(1, 11)
        ]
        keyword_results = [
            SearchResult(chunk_id=i + 5, fts_score=10 - i)
            for i in range(1, 11)
        ]

        # Run multiple times
        results1 = reciprocal_rank_fusion(vector_results, keyword_results)
        results2 = reciprocal_rank_fusion(vector_results, keyword_results)
        results3 = reciprocal_rank_fusion(vector_results, keyword_results)

        ids1 = [r.chunk_id for r in results1]
        ids2 = [r.chunk_id for r in results2]
        ids3 = [r.chunk_id for r in results3]

        assert ids1 == ids2 == ids3


class TestHybridSearcherSingleton:
    """Tests for hybrid searcher singleton."""

    def test_get_hybrid_searcher_returns_same_instance(self):
        """Should return same instance."""
        from src.infrastructure.search.hybrid import get_hybrid_searcher

        searcher1 = get_hybrid_searcher()
        searcher2 = get_hybrid_searcher()

        assert searcher1 is searcher2

    def test_hybrid_searcher_type(self):
        """Should return HybridSearcher instance."""
        from src.infrastructure.search.hybrid import get_hybrid_searcher

        searcher = get_hybrid_searcher()
        assert isinstance(searcher, HybridSearcher)
