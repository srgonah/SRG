"""
Amazon Search API client using SearchAPI.io.

Searches Amazon.ae for products by category and returns structured results.
"""

import os
from typing import Any

import httpx

from src.config import get_logger
from src.core.entities.material import OriginConfidence

logger = get_logger(__name__)

# SearchAPI.io endpoint
SEARCHAPI_BASE_URL = "https://www.searchapi.io/api/v1/search"

# Amazon.ae category mappings
AMAZON_CATEGORIES: dict[str, dict[str, str]] = {
    "Electronics": {
        "all": "aps",
        "Computers": "computers",
        "Mobile Phones": "mobile",
        "Cameras": "photo",
        "Audio": "electronics",
    },
    "Home & Kitchen": {
        "all": "aps",
        "Kitchen": "kitchen",
        "Furniture": "furniture",
        "Home Decor": "garden",
    },
    "Fashion": {
        "all": "aps",
        "Men": "fashion-mens",
        "Women": "fashion-womens",
        "Kids": "fashion-boys",
    },
    "Beauty": {
        "all": "aps",
        "Skincare": "beauty",
        "Makeup": "beauty",
        "Fragrance": "beauty",
    },
    "Sports": {
        "all": "aps",
        "Fitness": "sporting",
        "Outdoor": "sporting",
    },
    "Automotive": {
        "all": "aps",
        "Parts": "automotive",
        "Accessories": "automotive",
    },
    "Industrial": {
        "all": "aps",
        "Tools": "tools",
        "Safety": "industrial",
    },
}


class AmazonSearchResult:
    """Represents a single Amazon search result."""

    def __init__(
        self,
        asin: str,
        title: str,
        brand: str | None,
        price: str | None,
        price_value: float | None,
        currency: str | None,
        rating: float | None,
        reviews_count: int | None,
        image_url: str | None,
        product_url: str,
        is_prime: bool = False,
    ):
        self.asin = asin
        self.title = title
        self.brand = brand
        self.price = price
        self.price_value = price_value
        self.currency = currency
        self.rating = rating
        self.reviews_count = reviews_count
        self.image_url = image_url
        self.product_url = product_url
        self.is_prime = is_prime


class AmazonSearchAPIClient:
    """Client for SearchAPI.io Amazon Search API."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("SEARCHAPI_KEY", "")
        if not self.api_key:
            logger.warning("SEARCHAPI_KEY not configured")

    async def search(
        self,
        query: str,
        category: str = "aps",
        limit: int = 20,
        amazon_domain: str = "amazon.ae",
    ) -> list[AmazonSearchResult]:
        """
        Search Amazon using SearchAPI.io.

        Args:
            query: Search query string
            category: Amazon department/category code
            limit: Maximum results to return (1-50)
            amazon_domain: Amazon domain to search (default: amazon.ae)

        Returns:
            List of AmazonSearchResult objects
        """
        if not self.api_key:
            logger.error("search_failed", reason="SEARCHAPI_KEY not configured")
            return []

        params = {
            "engine": "amazon",
            "q": query,
            "amazon_domain": amazon_domain,
            "api_key": self.api_key,
        }

        # Add category if not "all products"
        if category and category != "aps":
            params["category_id"] = category

        logger.info(
            "amazon_search_request",
            query=query,
            category=category,
            domain=amazon_domain,
            limit=limit,
        )

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(SEARCHAPI_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()

            results = self._parse_results(data, limit)
            logger.info(
                "amazon_search_success",
                query=query,
                results_count=len(results),
            )
            return results

        except httpx.HTTPStatusError as e:
            logger.error(
                "amazon_search_http_error",
                status=e.response.status_code,
                detail=str(e),
            )
            return []
        except httpx.RequestError as e:
            logger.error("amazon_search_network_error", error=str(e))
            return []
        except Exception as e:
            logger.error("amazon_search_error", error=str(e))
            return []

    def _parse_results(
        self, data: dict[str, Any], limit: int
    ) -> list[AmazonSearchResult]:
        """Parse SearchAPI.io response into AmazonSearchResult objects."""
        results: list[AmazonSearchResult] = []

        # SearchAPI returns organic_results array
        organic = data.get("organic_results", [])

        for item in organic[:limit]:
            asin = item.get("asin", "")
            if not asin:
                continue

            # Extract price information
            price_info = item.get("price", {})
            if isinstance(price_info, dict):
                price_str = price_info.get("raw", price_info.get("value"))
                price_val = price_info.get("value")
                currency = price_info.get("currency", "AED")
            elif isinstance(price_info, str):
                price_str = price_info
                price_val = self._extract_price_value(price_info)
                currency = "AED"
            else:
                price_str = None
                price_val = None
                currency = None

            # Build product URL if not provided
            link = item.get("link", "")
            if not link and asin:
                link = f"https://www.amazon.ae/dp/{asin}"

            result = AmazonSearchResult(
                asin=asin,
                title=item.get("title", ""),
                brand=item.get("brand"),
                price=price_str,
                price_value=price_val,
                currency=currency,
                rating=item.get("rating"),
                reviews_count=item.get("reviews_total") or item.get("reviews"),
                image_url=item.get("thumbnail") or item.get("image"),
                product_url=link,
                is_prime=item.get("is_prime", False),
            )
            results.append(result)

        return results

    @staticmethod
    def _extract_price_value(price_str: str) -> float | None:
        """Extract numeric price value from price string."""
        import re

        if not price_str:
            return None
        # Remove currency symbols and extract number
        cleaned = re.sub(r"[^\d.,]", "", price_str)
        cleaned = cleaned.replace(",", "")
        try:
            return float(cleaned)
        except ValueError:
            return None


def get_amazon_categories() -> dict[str, list[str]]:
    """Get available Amazon categories and subcategories."""
    return {
        cat: list(subs.keys())
        for cat, subs in AMAZON_CATEGORIES.items()
    }


def get_category_code(category: str, subcategory: str = "all") -> str:
    """Get the Amazon category code for a category/subcategory pair."""
    if category in AMAZON_CATEGORIES:
        subs = AMAZON_CATEGORIES[category]
        return subs.get(subcategory, subs.get("all", "aps"))
    return "aps"
