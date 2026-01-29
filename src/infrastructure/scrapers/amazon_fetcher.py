"""
Amazon product page fetcher.

Extracts product title, brand, description, country-of-origin,
ASIN, weight, dimensions, price, rating, and number of ratings
from Amazon product pages across all supported domains.

Includes retry logic with exponential backoff, user-agent rotation,
and structured error classification (network / blocked / parse).
"""

import asyncio
import json
import random
import re
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup, Tag

from src.config import get_logger
from src.core.entities.material import OriginConfidence
from src.core.exceptions import (
    FetchBlockedError,
    FetchNetworkError,
    FetchParseError,
)
from src.core.interfaces.product_fetcher import IProductPageFetcher, ProductPageData

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Amazon domains we recognize (bare + www. prefix)
# ---------------------------------------------------------------------------
_AMAZON_BARE_DOMAINS = {
    "amazon.ae",
    "amazon.com",
    "amazon.co.uk",
    "amazon.de",
    "amazon.fr",
    "amazon.sa",
    # Task 3.3 - expanded domains
    "amazon.it",
    "amazon.es",
    "amazon.in",
    "amazon.co.jp",
    "amazon.com.br",
    "amazon.nl",
    "amazon.pl",
    "amazon.se",
    "amazon.com.au",
}

_AMAZON_DOMAINS = _AMAZON_BARE_DOMAINS | {f"www.{d}" for d in _AMAZON_BARE_DOMAINS}

# ---------------------------------------------------------------------------
# User-Agent rotation pool (common desktop browsers)
# ---------------------------------------------------------------------------
_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.2; rv:121.0) "
        "Gecko/20100101 Firefox/121.0"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.2 Safari/605.1.15"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    ),
]

# HTTP status codes that indicate the request was blocked
_BLOCKED_STATUS_CODES = {403, 429, 503}

# Country name patterns for origin detection
_ORIGIN_PATTERNS = [
    re.compile(r"country\s+of\s+origin\s*[:\-\u2013]\s*(.+?)(?:\n|$|<)", re.IGNORECASE),
    re.compile(r"made\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE),
    re.compile(r"manufactured\s+in\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", re.IGNORECASE),
    re.compile(r"origin\s*[:\-\u2013]\s*(.+?)(?:\n|$|<)", re.IGNORECASE),
]

# ASIN pattern (10 alphanumeric chars, starts with B0 or is all digits)
_ASIN_URL_PATTERN = re.compile(r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:[/?]|$)", re.IGNORECASE)
_ASIN_PAGE_PATTERN = re.compile(r"\bASIN\s*[:\-\s]\s*([A-Z0-9]{10})\b", re.IGNORECASE)

# Default retry configuration
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_BACKOFF_DELAYS = [1.0, 2.0, 4.0]


class AmazonProductFetcher(IProductPageFetcher):
    """Fetches and parses product data from Amazon product pages.

    Features:
    - Retry with exponential backoff (3 attempts: 1s, 2s, 4s)
    - User-Agent rotation from a pool of common browsers
    - Structured error classification (network / blocked / parse)
    - Request timeout (default 30s)
    - Extended field extraction (ASIN, weight, dimensions, price, rating)
    """

    def __init__(
        self,
        timeout: float = 30.0,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        backoff_delays: list[float] | None = None,
    ):
        self._timeout = timeout
        self._max_retries = max_retries
        self._backoff_delays = backoff_delays or list(_DEFAULT_BACKOFF_DELAYS)

    def supports_url(self, url: str) -> bool:
        """Check if URL is an Amazon product page."""
        try:
            parsed = urlparse(url)
            return parsed.hostname in _AMAZON_DOMAINS if parsed.hostname else False
        except Exception:
            return False

    async def fetch(self, url: str) -> ProductPageData:
        """Fetch and parse an Amazon product page with retry logic."""
        html = await self._fetch_html(url)
        try:
            return self._parse_html(html, url)
        except FetchParseError:
            raise
        except Exception as exc:
            raise FetchParseError(url, str(exc)) from exc

    async def _fetch_html(self, url: str) -> str:
        """Fetch raw HTML from URL with retry + exponential backoff."""
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            user_agent = random.choice(_USER_AGENTS)  # noqa: S311
            logger.info(
                "fetch_attempt",
                url=url,
                attempt=attempt,
                max_retries=self._max_retries,
            )

            try:
                async with httpx.AsyncClient(
                    timeout=self._timeout,
                    follow_redirects=True,
                    headers={
                        "User-Agent": user_agent,
                        "Accept-Language": "en-US,en;q=0.9",
                        "Accept": (
                            "text/html,application/xhtml+xml,"
                            "application/xml;q=0.9,*/*;q=0.8"
                        ),
                    },
                ) as client:
                    response = await client.get(url)

                    # Check for blocked status codes
                    if response.status_code in _BLOCKED_STATUS_CODES:
                        last_error = FetchBlockedError(url, response.status_code)
                        logger.warning(
                            "fetch_blocked",
                            url=url,
                            status_code=response.status_code,
                            attempt=attempt,
                        )
                    else:
                        response.raise_for_status()

                        # Check for captcha page
                        text = response.text
                        if self._is_captcha_page(text):
                            last_error = FetchBlockedError(url)
                            logger.warning(
                                "fetch_captcha_detected",
                                url=url,
                                attempt=attempt,
                            )
                        else:
                            logger.info(
                                "fetch_success",
                                url=url,
                                attempt=attempt,
                                content_length=len(text),
                            )
                            return text

            except httpx.TimeoutException as exc:
                last_error = FetchNetworkError(url, f"Timeout after {self._timeout}s")
                logger.warning(
                    "fetch_timeout",
                    url=url,
                    attempt=attempt,
                    timeout=self._timeout,
                )
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in _BLOCKED_STATUS_CODES:
                    last_error = FetchBlockedError(url, status)
                else:
                    last_error = FetchNetworkError(url, f"HTTP {status}")
                logger.warning(
                    "fetch_http_error",
                    url=url,
                    attempt=attempt,
                    status_code=status,
                )
            except httpx.RequestError as exc:
                last_error = FetchNetworkError(url, str(exc))
                logger.warning(
                    "fetch_network_error",
                    url=url,
                    attempt=attempt,
                    error=str(exc),
                )

            # Wait before retrying (skip wait after last attempt)
            if attempt < self._max_retries:
                delay_index = min(attempt - 1, len(self._backoff_delays) - 1)
                delay = self._backoff_delays[delay_index]
                logger.info("fetch_retry_wait", delay=delay, attempt=attempt)
                await asyncio.sleep(delay)

        # All retries exhausted
        logger.error(
            "fetch_all_retries_exhausted",
            url=url,
            max_retries=self._max_retries,
        )
        if last_error is not None:
            raise last_error
        raise FetchNetworkError(url, "All retries exhausted")

    @staticmethod
    def _is_captcha_page(html: str) -> bool:
        """Detect if the response is an Amazon captcha/robot-check page."""
        lower = html[:5000].lower()
        captcha_signals = [
            "captcha",
            "robot check",
            "type the characters you see",
            "sorry, we just need to make sure",
            "api-services-support@amazon.com",
        ]
        return any(signal in lower for signal in captcha_signals)

    def _parse_html(self, html: str, url: str) -> ProductPageData:
        """Parse product data from Amazon HTML."""
        soup = BeautifulSoup(html, "html.parser")

        # Try JSON-LD first (structured data)
        json_ld = self._extract_json_ld(soup)

        # Extract core fields
        title = self._extract_title(soup, json_ld)
        if not title:
            raise FetchParseError(url, "Could not extract product title")

        brand = self._extract_brand(soup, json_ld)
        description = self._extract_description(soup, json_ld)
        category = self._extract_category(soup, json_ld)

        # Extract detail table (used by origin + weight/dimensions)
        detail_table = self._extract_detail_table(soup)

        # Extract origin info
        origin_country, origin_confidence, evidence_text = self._extract_origin(
            soup, detail_table
        )

        # Generate suggested synonyms
        synonyms = self._generate_synonyms(title, brand)

        # Extract extended fields
        asin = self._extract_asin(url, soup)
        weight = self._extract_weight(detail_table)
        dimensions = self._extract_dimensions(detail_table)
        price = self._extract_price(soup)
        rating = self._extract_rating(soup)
        num_ratings = self._extract_num_ratings(soup)

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
            raw_attributes=detail_table,
            asin=asin,
            weight=weight,
            dimensions=dimensions,
            price=price,
            rating=rating,
            num_ratings=num_ratings,
        )

    # ------------------------------------------------------------------
    # JSON-LD extraction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Core field extraction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Origin extraction
    # ------------------------------------------------------------------

    def _extract_origin(
        self,
        soup: BeautifulSoup,
        detail_table: dict[str, str],
    ) -> tuple[str | None, OriginConfidence, str | None]:
        """Extract country of origin from the product page."""
        # Search the product detail table
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

    # ------------------------------------------------------------------
    # Detail table extraction
    # ------------------------------------------------------------------

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

    # ------------------------------------------------------------------
    # Extended field extraction (Task 3.2)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_asin(url: str, soup: BeautifulSoup) -> str | None:
        """Extract ASIN from URL path or page content."""
        # Try URL first (/dp/B09XXXXX or /gp/product/B09XXXXX)
        match = _ASIN_URL_PATTERN.search(url)
        if match:
            return match.group(1).upper()

        # Try page text (detail table or hidden input)
        asin_input = soup.find("input", attrs={"id": "ASIN"})
        if asin_input and isinstance(asin_input, Tag):
            val = asin_input.get("value", "")
            if isinstance(val, str) and len(val) == 10:
                return val.upper()

        # Try regex on page text
        page_text = soup.get_text(separator="\n")
        match = _ASIN_PAGE_PATTERN.search(page_text)
        if match:
            return match.group(1).upper()

        return None

    @staticmethod
    def _extract_weight(detail_table: dict[str, str]) -> str | None:
        """Extract product weight from the detail table."""
        weight_keys = ["item weight", "weight", "product weight", "package weight"]
        for key, val in detail_table.items():
            if key.lower().strip() in weight_keys:
                return val.strip()
        return None

    @staticmethod
    def _extract_dimensions(detail_table: dict[str, str]) -> str | None:
        """Extract product dimensions from the detail table."""
        dim_keys = [
            "product dimensions",
            "item dimensions",
            "package dimensions",
            "item dimensions lxwxh",
            "product dimensions lxwxh",
        ]
        for key, val in detail_table.items():
            if key.lower().strip() in dim_keys:
                return val.strip()
        return None

    @staticmethod
    def _extract_price(soup: BeautifulSoup) -> str | None:
        """Extract product price from the page."""
        # Try the main price span (whole + fraction)
        price_whole = soup.find("span", class_="a-price-whole")
        price_fraction = soup.find("span", class_="a-price-fraction")
        if price_whole:
            whole = price_whole.get_text(strip=True).rstrip(".")
            fraction = price_fraction.get_text(strip=True) if price_fraction else "00"
            # Look for currency symbol
            price_symbol = soup.find("span", class_="a-price-symbol")
            symbol = price_symbol.get_text(strip=True) if price_symbol else ""
            return f"{symbol}{whole}.{fraction}".strip()

        # Fallback: try priceblock_ourprice
        price_el = soup.find(id="priceblock_ourprice") or soup.find(
            id="priceblock_dealprice"
        )
        if price_el:
            return price_el.get_text(strip=True)

        # Fallback: core price element
        core_price = soup.find("span", class_="a-offscreen")
        if core_price:
            text = core_price.get_text(strip=True)
            if text and any(c.isdigit() for c in text):
                return text

        return None

    @staticmethod
    def _extract_rating(soup: BeautifulSoup) -> float | None:
        """Extract average customer rating (0-5)."""
        rating_el = soup.find("span", attrs={"data-hook": "rating-out-of-text"})
        if rating_el:
            match = re.search(r"([\d.]+)\s+out\s+of\s+5", rating_el.get_text())
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass

        # Fallback: i.a-icon element title attribute
        icon_el = soup.find("i", class_=re.compile(r"a-star-\d"))
        if icon_el:
            title = icon_el.get("title", "")
            if isinstance(title, str):
                match = re.search(r"([\d.]+)\s+out\s+of\s+5", title)
                if match:
                    try:
                        return float(match.group(1))
                    except ValueError:
                        pass

        return None

    @staticmethod
    def _extract_num_ratings(soup: BeautifulSoup) -> int | None:
        """Extract the number of customer ratings/reviews."""
        ratings_el = soup.find(id="acrCustomerReviewText")
        if ratings_el:
            text = ratings_el.get_text(strip=True)
            # "1,234 ratings" or "1234 global ratings"
            cleaned = text.replace(",", "").replace(".", "")
            match = re.search(r"(\d+)", cleaned)
            if match:
                try:
                    return int(match.group(1))
                except ValueError:
                    pass
        return None

    # ------------------------------------------------------------------
    # Synonym generation
    # ------------------------------------------------------------------

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
