"""
Unit tests for FTS5 query expansion and search.

Tests:
- Query expansion for HS codes
- Handling of dotted/hyphenated codes
- FTS searcher behavior (mocked DB)
- Score normalization
"""

from unittest.mock import AsyncMock, patch

import pytest

from src.core.entities import SearchResult
from src.infrastructure.search.fts import (
    FTSSearcher,
    _expand_query,
)


class TestQueryExpansion:
    """Tests for FTS query expansion."""

    def test_expand_simple_query(self):
        """Simple queries should be preserved."""
        query = "electronic component"
        expanded = _expand_query(query)

        assert "electronic" in expanded
        assert "component" in expanded

    def test_expand_dotted_hs_code(self):
        """Should expand dotted HS codes."""
        query = "85.36.20.00"
        expanded = _expand_query(query)

        # Should include original
        assert "85.36.20.00" in expanded
        # Should include stripped version
        assert "85362000" in expanded
        # Should include parts
        assert "85" in expanded
        assert "36" in expanded
        assert "20" in expanded
        assert "00" in expanded

    def test_expand_hyphenated_code(self):
        """Should expand hyphenated codes."""
        query = "85-36-20-00"
        expanded = _expand_query(query)

        # Should include stripped
        assert "85362000" in expanded
        # Should include parts
        assert "85" in expanded

    def test_expand_mixed_query(self):
        """Should handle mixed text and codes."""
        query = "circuit breaker 85.36.20.00"
        expanded = _expand_query(query)

        # Text preserved
        assert "circuit breaker" in expanded
        # Code expanded
        assert "85362000" in expanded

    def test_expand_preserves_alphanumeric(self):
        """Should preserve alphanumeric tokens."""
        query = "ABC123 product XYZ-456"
        expanded = _expand_query(query)

        assert "abc123" in expanded.lower()
        assert "product" in expanded.lower()
        assert "xyz456" in expanded.lower() or "xyz-456" in expanded.lower()

    def test_expand_empty_query(self):
        """Should handle empty query."""
        expanded = _expand_query("")
        assert expanded == ""

    def test_expand_special_characters(self):
        """Should handle queries with special characters."""
        query = "test@email.com #tag"
        expanded = _expand_query(query)

        # Should extract tokens
        assert "test" in expanded.lower() or "email" in expanded.lower()

    def test_expand_multiple_dots(self):
        """Should handle codes with multiple dots."""
        query = "8536.20.00.00"
        expanded = _expand_query(query)

        assert "8536200000" in expanded


class TestFTSSearcherChunks:
    """Tests for FTSSearcher.search_chunks with mocked database."""

    @pytest.fixture
    def searcher(self):
        return FTSSearcher()

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_search_chunks_returns_results(self, mock_get_conn, searcher):
        """Should return SearchResult list from database."""
        # Mock database response
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "doc_id": 10,
                "chunk_text": "Electronic circuit breaker",
                "metadata_json": "{}",
                "page_no": 1,
                "page_type": "invoice",
                "score": -5.5,  # BM25 returns negative
            },
            {
                "id": 2,
                "doc_id": 10,
                "chunk_text": "Plastic housing",
                "metadata_json": "{}",
                "page_no": 2,
                "page_type": "invoice",
                "score": -3.2,
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        results = await searcher.search_chunks("circuit", limit=10)

        assert len(results) == 2
        assert isinstance(results[0], SearchResult)
        assert results[0].chunk_id == 1
        assert results[0].text == "Electronic circuit breaker"
        assert results[0].fts_score == 5.5  # Absolute value
        assert results[0].final_rank == 0
        assert results[0].page_no == 1

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_search_chunks_expands_query(self, mock_get_conn, searcher):
        """Should expand HS codes in query."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        await searcher.search_chunks("85.36.20.00", limit=10)

        # Verify the query was expanded
        call_args = mock_conn.execute.call_args
        fts_query = call_args[0][1][0]  # First positional arg tuple
        assert "85362000" in fts_query

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_search_chunks_handles_db_error(self, mock_get_conn, searcher):
        """Should return empty list on database error."""
        mock_conn = AsyncMock()
        mock_conn.execute.side_effect = Exception("Database error")
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        results = await searcher.search_chunks("test query", limit=10)

        assert results == []

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_search_chunks_respects_limit(self, mock_get_conn, searcher):
        """Should pass limit to database query."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = []

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        await searcher.search_chunks("test", limit=25)

        call_args = mock_conn.execute.call_args
        limit_arg = call_args[0][1][1]  # Second element in args tuple
        assert limit_arg == 25


class TestFTSSearcherItems:
    """Tests for FTSSearcher.search_items with mocked database."""

    @pytest.fixture
    def searcher(self):
        return FTSSearcher()

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_search_items_returns_results(self, mock_get_conn, searcher):
        """Should return item search results."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 100,
                "item_name": "Circuit Breaker 16A",
                "hs_code": "85362000",
                "quantity": 100.0,
                "unit_price": 50.0,
                "total_price": 5000.0,
                "invoice_no": "INV-001",
                "invoice_date": "2024-01-15",
                "seller_name": "Test Supplier",
                "score": -8.5,
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        results = await searcher.search_items("circuit breaker", limit=10)

        assert len(results) == 1
        assert results[0].item_id == 100
        assert results[0].item_name == "Circuit Breaker 16A"
        assert results[0].hs_code == "85362000"
        assert results[0].quantity == 100.0
        assert results[0].fts_score == 8.5
        assert results[0].invoice_no == "INV-001"

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_search_items_handles_null_values(self, mock_get_conn, searcher):
        """Should handle NULL values from database."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 100,
                "item_name": "Product",
                "hs_code": None,
                "quantity": None,
                "unit_price": None,
                "total_price": None,
                "invoice_no": None,
                "invoice_date": None,
                "seller_name": None,
                "score": -1.0,
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        results = await searcher.search_items("product", limit=10)

        assert len(results) == 1
        assert results[0].hs_code is None
        assert results[0].quantity is None


class TestFTSScoreNormalization:
    """Tests for FTS score handling."""

    @pytest.fixture
    def searcher(self):
        return FTSSearcher()

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_normalizes_negative_bm25_scores(self, mock_get_conn, searcher):
        """Should convert negative BM25 scores to positive."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            {
                "id": 1,
                "doc_id": 1,
                "chunk_text": "test",
                "metadata_json": "{}",
                "page_no": 1,
                "page_type": None,
                "score": -10.5,
            },
            {
                "id": 2,
                "doc_id": 1,
                "chunk_text": "test2",
                "metadata_json": "{}",
                "page_no": 2,
                "page_type": None,
                "score": -5.2,
            },
        ]

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        results = await searcher.search_chunks("test", limit=10)

        # Scores should be positive (absolute value)
        assert results[0].fts_score == 10.5
        assert results[1].fts_score == 5.2
        # Higher absolute BM25 = better match
        assert results[0].fts_score > results[1].fts_score

    @pytest.mark.asyncio
    @patch("src.infrastructure.search.fts.get_connection")
    async def test_assigns_sequential_ranks(self, mock_get_conn, searcher):
        """Should assign sequential final_rank values."""
        mock_cursor = AsyncMock()
        mock_cursor.fetchall.return_value = [
            {"id": i, "doc_id": 1, "chunk_text": f"doc{i}", "metadata_json": "{}", "page_no": 1, "page_type": None, "score": -i}
            for i in range(1, 6)
        ]

        mock_conn = AsyncMock()
        mock_conn.execute.return_value = mock_cursor
        mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
        mock_conn.__aexit__ = AsyncMock(return_value=None)
        mock_get_conn.return_value = mock_conn

        results = await searcher.search_chunks("doc", limit=10)

        for i, result in enumerate(results):
            assert result.final_rank == i


class TestFTSQueryEdgeCases:
    """Tests for edge cases in FTS queries."""

    def test_expand_query_with_unicode(self):
        """Should handle Unicode in queries."""
        query = "منتج اختبار"  # Arabic
        expanded = _expand_query(query)
        # Should not crash
        assert query in expanded

    def test_expand_query_very_long(self):
        """Should handle very long queries."""
        query = " ".join(["word"] * 100)
        expanded = _expand_query(query)
        assert "word" in expanded

    def test_expand_query_numeric_only(self):
        """Should handle numeric-only queries."""
        query = "12345678"
        expanded = _expand_query(query)
        assert "12345678" in expanded

    def test_expand_query_with_quotes(self):
        """Should handle queries with quotes."""
        query = '"exact phrase" search'
        expanded = _expand_query(query)
        # Quotes are special characters, so tokens extracted
        assert "exact" in expanded.lower() or "phrase" in expanded.lower()


class TestFTSSingleton:
    """Tests for FTS searcher singleton."""

    def test_get_fts_searcher_returns_same_instance(self):
        """Should return the same instance."""
        from src.infrastructure.search.fts import get_fts_searcher

        searcher1 = get_fts_searcher()
        searcher2 = get_fts_searcher()

        assert searcher1 is searcher2

    def test_fts_searcher_is_ftssearcher_type(self):
        """Should return FTSSearcher instance."""
        from src.infrastructure.search.fts import get_fts_searcher

        searcher = get_fts_searcher()
        assert isinstance(searcher, FTSSearcher)
