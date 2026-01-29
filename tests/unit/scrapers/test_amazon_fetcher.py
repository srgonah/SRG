"""Unit tests for AmazonProductFetcher.

Tests cover:
- URL validation (supports_url) across all domains
- HTML parsing for all extracted fields
- Retry logic with exponential backoff
- Error classification (network / blocked / parse)
- ASIN extraction from various URL formats
- Extended field extraction (weight, dimensions, price, rating)
"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.core.entities.material import OriginConfidence
from src.core.exceptions import FetchBlockedError, FetchNetworkError, FetchParseError
from src.infrastructure.scrapers.amazon_fetcher import (
    AmazonProductFetcher,
    _AMAZON_BARE_DOMAINS,
    _AMAZON_DOMAINS,
)


@pytest.fixture
def fetcher():
    """Create an AmazonProductFetcher with zero backoff for fast tests."""
    return AmazonProductFetcher(timeout=5.0, max_retries=3, backoff_delays=[0, 0, 0])


def _build_html(
    *,
    title: str = "Test Product",
    brand: str | None = None,
    json_ld: dict | None = None,
    detail_rows: dict[str, str] | None = None,
    feature_bullets: list[str] | None = None,
    breadcrumbs: list[str] | None = None,
    asin_input: str | None = None,
    price_whole: str | None = None,
    price_fraction: str | None = None,
    price_symbol: str | None = None,
    rating_text: str | None = None,
    rating_icon_class: str | None = None,
    rating_icon_title: str | None = None,
    num_ratings_text: str | None = None,
) -> str:
    """Build minimal Amazon-like HTML for testing."""
    parts = ["<html><head>"]

    # JSON-LD
    if json_ld:
        parts.append(
            f'<script type="application/ld+json">{json.dumps(json_ld)}</script>'
        )

    parts.append("</head><body>")

    # Product title
    parts.append(f'<span id="productTitle">{title}</span>')

    # Brand
    if brand:
        parts.append(f'<a id="bylineInfo">Brand: {brand}</a>')

    # Feature bullets
    if feature_bullets:
        parts.append('<div id="feature-bullets"><ul>')
        for bullet in feature_bullets:
            parts.append(f'<li><span class="a-list-item">{bullet}</span></li>')
        parts.append("</ul></div>")

    # Detail table
    if detail_rows:
        parts.append('<table id="productDetails_techSpec_section_1">')
        for key, val in detail_rows.items():
            parts.append(f"<tr><th>{key}</th><td>{val}</td></tr>")
        parts.append("</table>")

    # Breadcrumbs
    if breadcrumbs:
        parts.append('<div id="wayfinding-breadcrumbs_feature_div">')
        for bc in breadcrumbs:
            parts.append(f'<a href="#">{bc}</a>')
        parts.append("</div>")

    # ASIN hidden input
    if asin_input:
        parts.append(f'<input id="ASIN" type="hidden" value="{asin_input}" />')

    # Price elements
    if price_whole:
        parts.append('<div class="a-price">')
        if price_symbol:
            parts.append(f'<span class="a-price-symbol">{price_symbol}</span>')
        parts.append(f'<span class="a-price-whole">{price_whole}</span>')
        if price_fraction:
            parts.append(f'<span class="a-price-fraction">{price_fraction}</span>')
        parts.append("</div>")

    # Rating elements
    if rating_text:
        parts.append(
            f'<span data-hook="rating-out-of-text">{rating_text}</span>'
        )
    if rating_icon_class and rating_icon_title:
        parts.append(
            f'<i class="{rating_icon_class}" title="{rating_icon_title}"></i>'
        )

    # Number of ratings
    if num_ratings_text:
        parts.append(f'<span id="acrCustomerReviewText">{num_ratings_text}</span>')

    parts.append("</body></html>")
    return "".join(parts)


# ==========================================================================
# URL validation tests
# ==========================================================================


class TestSupportsUrl:
    """Tests for supports_url method."""

    def test_amazon_ae(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("https://www.amazon.ae/dp/B001") is True

    def test_amazon_com(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("https://www.amazon.com/dp/B002") is True

    def test_amazon_co_uk(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("https://www.amazon.co.uk/dp/B003") is True

    def test_amazon_sa(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("https://www.amazon.sa/dp/B004") is True

    def test_non_amazon(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("https://www.aliexpress.com/item/123") is False

    def test_invalid_url(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("not-a-url") is False

    def test_empty_string(self, fetcher: AmazonProductFetcher):
        assert fetcher.supports_url("") is False


class TestExpandedDomains:
    """Tests for all expanded Amazon domains (Task 3.3)."""

    @pytest.mark.parametrize(
        "domain",
        [
            "amazon.it",
            "amazon.es",
            "amazon.in",
            "amazon.co.jp",
            "amazon.com.br",
            "amazon.nl",
            "amazon.pl",
            "amazon.se",
            "amazon.com.au",
        ],
    )
    def test_expanded_domain_in_bare_set(self, domain: str):
        """Each expanded domain is in _AMAZON_BARE_DOMAINS."""
        assert domain in _AMAZON_BARE_DOMAINS

    @pytest.mark.parametrize(
        "domain",
        [
            "amazon.it",
            "amazon.es",
            "amazon.in",
            "amazon.co.jp",
            "amazon.com.br",
            "amazon.nl",
            "amazon.pl",
            "amazon.se",
            "amazon.com.au",
        ],
    )
    def test_expanded_domain_with_www(self, domain: str):
        """Each expanded domain with www. prefix is in _AMAZON_DOMAINS."""
        assert f"www.{domain}" in _AMAZON_DOMAINS

    @pytest.mark.parametrize(
        "url",
        [
            "https://www.amazon.it/dp/B001234567",
            "https://www.amazon.es/dp/B001234567",
            "https://www.amazon.in/dp/B001234567",
            "https://www.amazon.co.jp/dp/B001234567",
            "https://www.amazon.com.br/dp/B001234567",
            "https://www.amazon.nl/dp/B001234567",
            "https://www.amazon.pl/dp/B001234567",
            "https://www.amazon.se/dp/B001234567",
            "https://www.amazon.com.au/dp/B001234567",
            "https://amazon.it/dp/B001234567",
            "https://amazon.com.au/dp/B001234567",
        ],
    )
    def test_supports_url_for_expanded_domains(
        self, fetcher: AmazonProductFetcher, url: str
    ):
        """supports_url returns True for all expanded domain URLs."""
        assert fetcher.supports_url(url) is True

    def test_all_original_domains_still_supported(self, fetcher: AmazonProductFetcher):
        """Original domains remain supported after expansion."""
        original = [
            "https://www.amazon.ae/dp/B001",
            "https://www.amazon.com/dp/B001",
            "https://www.amazon.co.uk/dp/B001",
            "https://www.amazon.de/dp/B001",
            "https://www.amazon.fr/dp/B001",
            "https://www.amazon.sa/dp/B001",
        ]
        for url in original:
            assert fetcher.supports_url(url) is True


# ==========================================================================
# HTML parsing tests - core fields
# ==========================================================================


class TestParseHtmlTitle:
    """Tests for title extraction."""

    def test_title_from_product_title_element(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="BOSCH Impact Drill 500W")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.title == "BOSCH Impact Drill 500W"

    def test_title_from_json_ld(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            title="",
            json_ld={"@type": "Product", "name": "JSON-LD Product Name"},
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.title == "JSON-LD Product Name"

    def test_missing_title_raises_parse_error(self, fetcher: AmazonProductFetcher):
        html = "<html><head></head><body></body></html>"
        with pytest.raises(FetchParseError, match="Could not extract product title"):
            fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")


class TestParseHtmlBrand:
    """Tests for brand extraction."""

    def test_brand_from_byline(self, fetcher: AmazonProductFetcher):
        html = _build_html(brand="DeWalt")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.brand == "DeWalt"

    def test_brand_from_json_ld(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            json_ld={
                "@type": "Product",
                "name": "Test Product",
                "brand": {"@type": "Brand", "name": "BOSCH"},
            }
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.brand == "BOSCH"

    def test_no_brand_returns_none(self, fetcher: AmazonProductFetcher):
        html = _build_html()
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.brand is None


class TestParseHtmlOrigin:
    """Tests for country-of-origin extraction."""

    def test_origin_from_detail_table(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            detail_rows={"Country of Origin": "Germany", "Weight": "2.5 kg"}
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.origin_country == "Germany"
        assert data.origin_confidence == OriginConfidence.CONFIRMED
        assert "Country of Origin" in (data.evidence_text or "")

    def test_origin_unknown_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html(detail_rows={"Weight": "1 kg"})
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.origin_country is None
        assert data.origin_confidence == OriginConfidence.UNKNOWN

    def test_origin_from_regex_pattern(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            feature_bullets=["High quality drill", "Made in Japan", "500W motor"]
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.origin_country == "Japan"
        assert data.origin_confidence == OriginConfidence.LIKELY


class TestParseHtmlDescription:
    """Tests for description extraction."""

    def test_description_from_feature_bullets(self, fetcher: AmazonProductFetcher):
        html = _build_html(feature_bullets=["Powerful motor", "Lightweight design"])
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert "Powerful motor" in (data.description or "")
        assert "Lightweight design" in (data.description or "")

    def test_description_from_json_ld(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            json_ld={
                "@type": "Product",
                "name": "Test",
                "description": "A great product description.",
            }
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.description == "A great product description."


class TestParseHtmlCategory:
    """Tests for category extraction."""

    def test_category_from_breadcrumbs(self, fetcher: AmazonProductFetcher):
        html = _build_html(breadcrumbs=["Tools", "Power Tools", "Drills"])
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.category == "Drills"

    def test_category_from_json_ld(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            json_ld={"@type": "Product", "name": "Test", "category": "Power Tools"}
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.category == "Power Tools"


class TestGenerateSynonyms:
    """Tests for synonym generation logic."""

    def test_brand_removed_from_title(self, fetcher: AmazonProductFetcher):
        synonyms = fetcher._generate_synonyms("BOSCH Impact Drill 500W", "BOSCH")
        assert any("Impact Drill 500W" in s for s in synonyms)

    def test_brand_added_as_synonym(self, fetcher: AmazonProductFetcher):
        synonyms = fetcher._generate_synonyms("BOSCH Impact Drill", "BOSCH")
        assert "BOSCH" in synonyms

    def test_no_brand_no_synonyms(self, fetcher: AmazonProductFetcher):
        synonyms = fetcher._generate_synonyms("Simple Product", None)
        assert synonyms == []

    def test_short_brand_excluded(self, fetcher: AmazonProductFetcher):
        synonyms = fetcher._generate_synonyms("AB Widget", "AB")
        assert "AB" not in synonyms


class TestSourceUrl:
    """Tests for source_url passthrough."""

    def test_source_url_set(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.source_url == "https://www.amazon.ae/dp/B001"


# ==========================================================================
# Extended field extraction tests (Task 3.2)
# ==========================================================================


class TestAsinExtraction:
    """Tests for ASIN extraction from various URL formats."""

    def test_asin_from_dp_url(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        data = fetcher._parse_html(html, "https://www.amazon.com/dp/B09V3KXJPB")
        assert data.asin == "B09V3KXJPB"

    def test_asin_from_dp_url_with_slug(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        url = "https://www.amazon.ae/Some-Product-Name/dp/B08N5WRWNW/ref=sr_1_1"
        data = fetcher._parse_html(html, url)
        assert data.asin == "B08N5WRWNW"

    def test_asin_from_gp_product_url(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        url = "https://www.amazon.com/gp/product/B001234567"
        data = fetcher._parse_html(html, url)
        assert data.asin == "B001234567"

    def test_asin_from_hidden_input(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product", asin_input="B0CUSTOM12")
        # URL without ASIN pattern
        data = fetcher._parse_html(html, "https://www.amazon.ae/some-page")
        assert data.asin == "B0CUSTOM12"

    def test_asin_from_page_text(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            title="Test Product",
            detail_rows={"ASIN": "B0TEXASIN1", "Weight": "1 kg"},
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/some-page")
        assert data.asin == "B0TEXASIN1"

    def test_asin_none_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        data = fetcher._parse_html(html, "https://www.amazon.ae/some-page")
        assert data.asin is None

    def test_asin_uppercase(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        data = fetcher._parse_html(html, "https://www.amazon.com/dp/b09v3kxjpb")
        assert data.asin == "B09V3KXJPB"


class TestWeightExtraction:
    """Tests for weight extraction."""

    def test_weight_from_detail_table(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            detail_rows={"Item Weight": "2.5 kg", "Country of Origin": "China"}
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.weight == "2.5 kg"

    def test_weight_from_product_weight_key(self, fetcher: AmazonProductFetcher):
        html = _build_html(detail_rows={"Product Weight": "500 grams"})
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.weight == "500 grams"

    def test_weight_none_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html(detail_rows={"Color": "Blue"})
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.weight is None


class TestDimensionsExtraction:
    """Tests for dimensions extraction."""

    def test_dimensions_from_detail_table(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            detail_rows={"Product Dimensions": "30 x 20 x 10 cm"}
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.dimensions == "30 x 20 x 10 cm"

    def test_dimensions_from_item_key(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            detail_rows={"Item Dimensions": "25 x 15 x 5 cm"}
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.dimensions == "25 x 15 x 5 cm"

    def test_dimensions_none_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html(detail_rows={"Weight": "1 kg"})
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.dimensions is None


class TestPriceExtraction:
    """Tests for price extraction."""

    def test_price_from_price_spans(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            price_whole="149",
            price_fraction="99",
            price_symbol="AED",
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.price == "AED149.99"

    def test_price_without_symbol(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            price_whole="49",
            price_fraction="00",
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.price == "49.00"

    def test_price_none_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html()
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.price is None


class TestRatingExtraction:
    """Tests for rating extraction."""

    def test_rating_from_data_hook(self, fetcher: AmazonProductFetcher):
        html = _build_html(rating_text="4.5 out of 5")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.rating == 4.5

    def test_rating_from_icon_title(self, fetcher: AmazonProductFetcher):
        html = _build_html(
            rating_icon_class="a-star-4",
            rating_icon_title="4.2 out of 5 stars",
        )
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.rating == 4.2

    def test_rating_none_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html()
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.rating is None


class TestNumRatingsExtraction:
    """Tests for num_ratings extraction."""

    def test_num_ratings_extracted(self, fetcher: AmazonProductFetcher):
        html = _build_html(num_ratings_text="1,234 ratings")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.num_ratings == 1234

    def test_num_ratings_global_format(self, fetcher: AmazonProductFetcher):
        html = _build_html(num_ratings_text="567 global ratings")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.num_ratings == 567

    def test_num_ratings_none_when_absent(self, fetcher: AmazonProductFetcher):
        html = _build_html()
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.num_ratings is None


# ==========================================================================
# Retry logic tests (Task 3.1)
# ==========================================================================


class TestRetryLogic:
    """Tests for retry with exponential backoff."""

    @pytest.mark.asyncio
    async def test_succeeds_on_first_attempt(self, fetcher: AmazonProductFetcher):
        """Fetch succeeds on the first try."""
        html = _build_html(title="Success Product")
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = html
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.return_value = mock_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

        assert "Success Product" in result
        assert mock_client.get.call_count == 1

    @pytest.mark.asyncio
    async def test_retries_on_network_error_then_succeeds(self, fetcher: AmazonProductFetcher):
        """Fails twice with network error, succeeds on third attempt."""
        html = _build_html(title="Retry Product")
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.text = html
        success_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.side_effect = [
            httpx.ConnectError("Connection refused"),
            httpx.ConnectError("Connection refused"),
            success_response,
        ]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

        assert "Retry Product" in result
        assert mock_client.get.call_count == 3

    @pytest.mark.asyncio
    async def test_raises_after_all_retries_exhausted(self):
        """Raises FetchNetworkError when all retries fail."""
        fetcher = AmazonProductFetcher(timeout=5.0, max_retries=2, backoff_delays=[0, 0])

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("Connection refused")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(FetchNetworkError):
                await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_retries_on_blocked_403(self, fetcher: AmazonProductFetcher):
        """403 responses are classified as blocked and retried."""
        blocked_response = MagicMock()
        blocked_response.status_code = 403

        html = _build_html(title="OK Product")
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.text = html
        ok_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.side_effect = [blocked_response, ok_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

        assert "OK Product" in result
        assert mock_client.get.call_count == 2

    @pytest.mark.asyncio
    async def test_raises_blocked_after_all_retries(self):
        """All retries blocked results in FetchBlockedError."""
        fetcher = AmazonProductFetcher(timeout=5.0, max_retries=2, backoff_delays=[0, 0])

        blocked_response = MagicMock()
        blocked_response.status_code = 403

        mock_client = AsyncMock()
        mock_client.get.return_value = blocked_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(FetchBlockedError):
                await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

    @pytest.mark.asyncio
    async def test_retries_on_captcha_page(self, fetcher: AmazonProductFetcher):
        """Captcha page is detected and retried."""
        captcha_html = "<html><body>Robot Check - Type the characters you see</body></html>"
        captcha_response = MagicMock()
        captcha_response.status_code = 200
        captcha_response.text = captcha_html
        captcha_response.raise_for_status = MagicMock()

        ok_html = _build_html(title="Real Product")
        ok_response = MagicMock()
        ok_response.status_code = 200
        ok_response.text = ok_html
        ok_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get.side_effect = [captcha_response, ok_response]
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            result = await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

        assert "Real Product" in result

    @pytest.mark.asyncio
    async def test_timeout_error_classified_as_network(self):
        """Timeout exceptions are classified as FetchNetworkError."""
        fetcher = AmazonProductFetcher(timeout=5.0, max_retries=1, backoff_delays=[0])

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ReadTimeout("Read timed out")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(FetchNetworkError, match="Timeout"):
                await fetcher._fetch_html("https://www.amazon.ae/dp/B001")


# ==========================================================================
# Error classification tests (Task 3.1)
# ==========================================================================


class TestErrorClassification:
    """Tests for error type classification."""

    @pytest.mark.asyncio
    async def test_connection_error_is_fetch_network_error(self):
        """Connection errors result in FetchNetworkError."""
        fetcher = AmazonProductFetcher(max_retries=1, backoff_delays=[0])

        mock_client = AsyncMock()
        mock_client.get.side_effect = httpx.ConnectError("DNS resolution failed")
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(FetchNetworkError):
                await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

    @pytest.mark.asyncio
    async def test_http_500_is_fetch_network_error(self):
        """HTTP 500 (not in blocked set) results in FetchNetworkError."""
        fetcher = AmazonProductFetcher(max_retries=1, backoff_delays=[0])

        exc = httpx.HTTPStatusError(
            "Internal Server Error",
            request=MagicMock(),
            response=MagicMock(status_code=500),
        )

        mock_client = AsyncMock()
        mock_client.get.side_effect = exc
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(FetchNetworkError):
                await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

    @pytest.mark.asyncio
    async def test_http_429_is_fetch_blocked_error(self):
        """HTTP 429 (rate-limited) results in FetchBlockedError."""
        fetcher = AmazonProductFetcher(max_retries=1, backoff_delays=[0])

        blocked_response = MagicMock()
        blocked_response.status_code = 429

        mock_client = AsyncMock()
        mock_client.get.return_value = blocked_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient", return_value=mock_client):
            with pytest.raises(FetchBlockedError):
                await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

    def test_missing_title_is_parse_error(self, fetcher: AmazonProductFetcher):
        """Missing title raises FetchParseError."""
        html = "<html><head></head><body></body></html>"
        with pytest.raises(FetchParseError):
            fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")


# ==========================================================================
# Captcha detection tests
# ==========================================================================


class TestCaptchaDetection:
    """Tests for captcha/robot page detection."""

    def test_captcha_detected(self):
        html = "<html><body>Robot Check - Please solve the captcha</body></html>"
        assert AmazonProductFetcher._is_captcha_page(html) is True

    def test_normal_page_not_flagged(self):
        html = _build_html(title="Normal Product")
        assert AmazonProductFetcher._is_captcha_page(html) is False

    def test_support_email_detected(self):
        html = "<html><body>Contact api-services-support@amazon.com</body></html>"
        assert AmazonProductFetcher._is_captcha_page(html) is True


# ==========================================================================
# User-Agent rotation test
# ==========================================================================


class TestUserAgentRotation:
    """Tests for User-Agent rotation."""

    @pytest.mark.asyncio
    async def test_user_agent_is_set(self, fetcher: AmazonProductFetcher):
        """Verify that a User-Agent header is sent."""
        html = _build_html(title="Test Product")
        captured_headers: dict = {}

        async def capture_get(url, **kwargs):
            resp = MagicMock()
            resp.status_code = 200
            resp.text = html
            resp.raise_for_status = MagicMock()
            return resp

        mock_client = AsyncMock()
        mock_client.get = capture_get
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with patch("src.infrastructure.scrapers.amazon_fetcher.httpx.AsyncClient") as MockClass:
            # Capture the headers passed to AsyncClient constructor
            def capture_init(**kwargs):
                captured_headers.update(kwargs.get("headers", {}))
                return mock_client
            MockClass.side_effect = capture_init

            await fetcher._fetch_html("https://www.amazon.ae/dp/B001")

        assert "User-Agent" in captured_headers
        assert len(captured_headers["User-Agent"]) > 20  # Not empty
