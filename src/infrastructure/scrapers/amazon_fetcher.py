"""
Amazon product page fetcher.

Extracts product title, brand, description, and country-of-origin
from Amazon.ae (and other Amazon domains) product pages.
"""

import json
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from src.config import get_logger
from src.core.entities.material import OriginConfidence
from src.core.exceptions import CatalogError
from src.core.interfaces.product_fetcher import IProductPageFetcher, ProductPageData

logger = get_logger(__name__)

# Amazon domains we recognize
_AMAZON_DOMAINS = {
    "amazon.ae",
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.sa",
    "www.amazon.ae",
    "www.amazon.com",
    "www.amazon.co.uk",
    "www.amazon.de",
    "www.amazon.fr",
    "www.amazon.sa",
}

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Country name patterns for origin detection
_ORIGIN_PATTERNS = [
    re.compile(r"country\s+of\s+origin\s*[:\-–]\s*(.+?)(?:\n|$|<)", re.IGNORECASE),
    re.compile(r"made\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE),
    re.compile(r"manufactured\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE),
    re.compile(r"origin\s*[:\-–]\s*(.+?)(?:\n|$|<)", re.IGNORECASE),
]


class AmazonProductFetcher(IProductPageFetcher):
    """Fetches and parses product data from Amazon product pages."""

    def __init__(self, timeout: float = 30.0):
        self._timeout = timeout

    def supports_url(self, url: str) -> bool:
        """Check if URL is an Amazon product page."""
        try:
            parsed = urlparse(url)
            return parsed.hostname in _AMAZON_DOMAINS if parsed.hostname else False
        except Exception:
            return False

    async def fetch(self, url: str) -> ProductPageData:
        """Fetch and parse an Amazon product page."""
        html = await self._fetch_html(url)
        return self._parse_html(html, url)

    async def _fetch_html(self, url: str) -> str:
        """Fetch raw HTML from URL."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout,
                follow_redirects=True,
                headers={"User-Agent": _USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
            ) as client:
                response = await client.get(url)
                response.raise_for_status()
                return response.text
        except httpx.HTTPStatusError as e:
            raise CatalogError(
                f"Failed to fetch URL (HTTP {e.response.status_code}): {url}",
                code="FETCH_FAILED",
            )
        except httpx.RequestError as e:
            raise CatalogError(
                f"Failed to fetch URL: {url} — {e}",
                code="FETCH_FAILED",
            )

    def _parse_html(self, html: str, url: str) -> ProductPageData:
        """Parse product data from Amazon HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD first (structured data)
        json_ld = self._extract_json_ld(soup)

        # Extract fields
        title = self._extract_title(soup, json_ld)
        if not title:
            raise CatalogError(
                f"Could not extract product title from: {url}",
                code="PARSE_FAILED",
            )

        brand = self._extract_brand(soup, json_ld)
        description = self._extract_description(soup, json_ld)
        category = self._extract_category(soup, json_ld)

        # Extract origin info
        origin_country, origin_confidence, evidence_text = self._extract_origin(soup)

        # Generate suggested synonyms
        synonyms = self._generate_synonyms(title, brand)

        return ProductPageData(
            title=title,
            brand=brand,
            description=description,
            origin_country=origin_country,
            origin_confidence=origin_confidence,
            evidence_text=evidence_text,
            source_url=url,
            category=category,
            suggested_synonyms=synonyms,
            raw_attributes=self._extract_detail_table(soup),
        )

    def _extract_json_ld(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract JSON-LD product structured data."""
        for script in soup.find_all("script", type="application/ld+json"):
            try:
                data = json.loads(script.string or "")
                if isinstance(data, dict) and data.get("@type") == "Product":
                    return {
                        "name": str(data.get("name", "")),
                        "brand": str(data.get("brand", {}).get("name", ""))
                        if isinstance(data.get("brand"), dict)
                        else str(data.get("brand", "")),
                        "description": str(data.get("description", "")),
                        "category": str(data.get("category", "")),
                    }
                # Sometimes wrapped in a list
                if isinstance(data, list):
                    for item in data:
                        if isinstance(item, dict) and item.get("@type") == "Product":
                            return {
                                "name": str(item.get("name", "")),
                                "brand": str(item.get("brand", {}).get("name", ""))
                                if isinstance(item.get("brand"), dict)
                                else str(item.get("brand", "")),
                                "description": str(item.get("description", "")),
                                "category": str(item.get("category", "")),
                            }
            except (json.JSONDecodeError, TypeError, AttributeError):
                continue
        return {}

    def _extract_title(self, soup: BeautifulSoup, json_ld: dict[str, str]) -> str | None:
        """Extract product title."""
        # JSON-LD first
        if json_ld.get("name"):
            return json_ld["name"].strip()

        # Amazon product title element
        title_el = soup.find(id="productTitle")
        if title_el:
            return title_el.get_text(strip=True)

        # Fallback to <title> tag
        title_tag = soup.find("title")
        if title_tag:
            text = title_tag.get_text(strip=True)
            # Remove " - Amazon.ae" suffix
            text = re.sub(r"\s*[-|:]\s*Amazon\.\w+.*$", "", text)
            return text if text else None

        return None

    def _extract_brand(self, soup: BeautifulSoup, json_ld: dict[str, str]) -> str | None:
        """Extract brand name."""
        if json_ld.get("brand"):
            return json_ld["brand"].strip() or None

        # Amazon brand row
        brand_el = soup.find(id="bylineInfo")
        if brand_el:
            text = brand_el.get_text(strip=True)
            # "Visit the BRAND Store" or "Brand: BRAND"
            text = re.sub(r"^(Visit the |Brand:\s*)", "", text)
            text = re.sub(r"\s*Store\s*$", "", text)
            return text.strip() or None

        return None

    def _extract_description(
        self, soup: BeautifulSoup, json_ld: dict[str, str]
    ) -> str | None:
        """Extract product description."""
        if json_ld.get("description"):
            return json_ld["description"].strip()[:1000] or None

        # Amazon feature bullets
        feature_div = soup.find(id="feature-bullets")
        if feature_div:
            bullets = feature_div.find_all("span", class_="a-list-item")
            texts = [b.get_text(strip=True) for b in bullets if b.get_text(strip=True)]
            if texts:
                return "; ".join(texts[:10])[:1000]

        # Product description div
        desc_div = soup.find(id="productDescription")
        if desc_div:
            text = desc_div.get_text(strip=True)
            return text[:1000] if text else None

        return None

    def _extract_category(self, soup: BeautifulSoup, json_ld: dict[str, str]) -> str | None:
        """Extract product category."""
        if json_ld.get("category"):
            return json_ld["category"].strip() or None

        # Amazon breadcrumbs
        breadcrumbs = soup.find(id="wayfinding-breadcrumbs_feature_div")
        if breadcrumbs:
            links = breadcrumbs.find_all("a")
            if links:
                # Return the deepest category
                return links[-1].get_text(strip=True) or None

        return None

    def _extract_origin(
        self, soup: BeautifulSoup
    ) -> tuple[str | None, OriginConfidence, str | None]:
        """Extract country of origin from the product page."""
        # Search the product detail table
        detail_table = self._extract_detail_table(soup)
        for key, value in detail_table.items():
            if "country" in key.lower() and "origin" in key.lower():
                country = value.strip()
                if country:
                    return (
                        country,
                        OriginConfidence.CONFIRMED,
                        f"Product detail table: {key} = {value}",
                    )

        # Search full page text for origin patterns
        page_text = soup.get_text(separator="\n")
        for pattern in _ORIGIN_PATTERNS:
            match = pattern.search(page_text)
            if match:
                country = match.group(1).strip()
                # Clean up common noise
                country = re.sub(r"[<\n\r].*", "", country).strip()
                if country and len(country) < 50:
                    return (
                        country,
                        OriginConfidence.LIKELY,
                        f"Pattern match: '{match.group(0).strip()}'",
                    )

        return None, OriginConfidence.UNKNOWN, None

    def _extract_detail_table(self, soup: BeautifulSoup) -> dict[str, str]:
        """Extract key-value pairs from the Amazon product detail table."""
        result: dict[str, str] = {}

        # Product information table
        for table_id in [
            "productDetails_techSpec_section_1",
            "productDetails_detailBullets_sections1",
        ]:
            table = soup.find(id=table_id)
            if table and isinstance(table, Tag):
                for row in table.find_all("tr"):
                    cells = row.find_all(["th", "td"])
                    if len(cells) >= 2:
                        key = cells[0].get_text(strip=True)
                        val = cells[1].get_text(strip=True)
                        if key and val:
                            result[key] = val

        # Detail bullets format (alternate Amazon layout)
        detail_bullets = soup.find(id="detailBullets_feature_div")
        if detail_bullets and isinstance(detail_bullets, Tag):
            for item in detail_bullets.find_all("li"):
                spans = item.find_all("span", class_="a-text-bold")
                if spans:
                    key = spans[0].get_text(strip=True).rstrip(" :\u200f\u200e")
                    # Get the sibling text
                    val_span = spans[0].find_next_sibling("span")
                    if val_span:
                        val = val_span.get_text(strip=True)
                        if key and val:
                            result[key] = val

        return result

    def _generate_synonyms(self, title: str, brand: str | None) -> list[str]:
        """Generate synonym suggestions from title and brand."""
        synonyms: list[str] = []

        # If brand appears in title, create a version without brand
        if brand and brand.lower() in title.lower():
            no_brand = re.sub(re.escape(brand), "", title, flags=re.IGNORECASE).strip()
            no_brand = re.sub(r"\s+", " ", no_brand).strip(" ,/-")
            if no_brand and len(no_brand) > 3:
                synonyms.append(no_brand)

        # Add brand as separate synonym if meaningful
        if brand and len(brand) > 2 and brand.lower() != title.lower():
            synonyms.append(brand)

        return synonyms
