"""Unit tests for AmazonProductFetcher HTML parsing logic.

Tests the parsing methods directly with sample HTML, without making HTTP calls.
"""

import json

import pytest

from src.core.entities.material import OriginConfidence
from src.infrastructure.scrapers.amazon_fetcher import AmazonProductFetcher


@pytest.fixture
def fetcher():
    """Create an AmazonProductFetcher instance."""
    return AmazonProductFetcher()


def _build_html(
    *,
    title: str = "Test Product",
    brand: str | None = None,
    json_ld: dict | None = None,
    detail_rows: dict[str, str] | None = None,
    feature_bullets: list[str] | None = None,
    breadcrumbs: list[str] | None = None,
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

    parts.append("</body></html>")
    return "".join(parts)


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
        # The productTitle is empty but JSON-LD has the name
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.title == "JSON-LD Product Name"

    def test_missing_title_raises(self, fetcher: AmazonProductFetcher):
        from src.core.exceptions import CatalogError

        html = "<html><head></head><body></body></html>"
        with pytest.raises(CatalogError, match="Could not extract product title"):
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
        # Brand "AB" has length 2, should be excluded
        assert "AB" not in synonyms


class TestSourceUrl:
    """Tests for source_url passthrough."""

    def test_source_url_set(self, fetcher: AmazonProductFetcher):
        html = _build_html(title="Test Product")
        data = fetcher._parse_html(html, "https://www.amazon.ae/dp/B001")
        assert data.source_url == "https://www.amazon.ae/dp/B001"
