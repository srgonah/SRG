"""
Price history and statistics endpoints.
"""

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import get_price_store
from src.application.dto.responses import (
    PriceHistoryEntryResponse,
    PriceHistoryResponse,
    PriceStatsListResponse,
    PriceStatsResponse,
)
from src.infrastructure.storage.sqlite.price_history_store import SQLitePriceHistoryStore

router = APIRouter(prefix="/api/prices", tags=["prices"])


@router.get("/history", response_model=PriceHistoryResponse)
async def get_price_history(
    item: str | None = Query(default=None, description="Item name filter"),
    seller: str | None = Query(default=None, description="Seller name filter"),
    date_from: str | None = Query(default=None, description="Start date (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(default=100, ge=1, le=1000),
    store: SQLitePriceHistoryStore = Depends(get_price_store),
) -> PriceHistoryResponse:
    """Query price history with optional filters."""
    entries = await store.get_price_history(
        item_name=item,
        seller=seller,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )
    return PriceHistoryResponse(
        entries=[
            PriceHistoryEntryResponse(
                item_name=e["item_name"],
                hs_code=e.get("hs_code"),
                seller_name=e.get("seller_name"),
                invoice_date=e.get("invoice_date"),
                quantity=e.get("quantity", 0),
                unit_price=e.get("unit_price", 0),
                currency=e.get("currency", "USD"),
            )
            for e in entries
        ],
        total=len(entries),
    )


@router.get("/stats", response_model=PriceStatsListResponse)
async def get_price_stats(
    item: str | None = Query(default=None, description="Item name filter"),
    seller: str | None = Query(default=None, description="Seller name filter"),
    store: SQLitePriceHistoryStore = Depends(get_price_store),
) -> PriceStatsListResponse:
    """Get price statistics per item/seller combination."""
    stats = await store.get_price_stats(
        item_name=item,
        seller=seller,
    )
    return PriceStatsListResponse(
        stats=[
            PriceStatsResponse(
                item_name=s["item_name"],
                hs_code=s.get("hs_code"),
                seller_name=s.get("seller_name"),
                currency=s.get("currency", "USD"),
                occurrence_count=s.get("occurrence_count", 0),
                min_price=s.get("min_price", 0),
                max_price=s.get("max_price", 0),
                avg_price=s.get("avg_price", 0),
                price_trend=s.get("price_trend"),
                first_seen=s.get("first_seen"),
                last_seen=s.get("last_seen"),
            )
            for s in stats
        ],
        total=len(stats),
    )
