"""
Amazon import endpoints.

Imports materials from Amazon.ae search results using SearchAPI.io.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from src.api.dependencies import get_mat_store
from src.application.dto.requests import AmazonImportRequest
from src.application.dto.responses import (
    AmazonCategoriesResponse,
    AmazonImportItemResponse,
    AmazonImportResponse,
    ErrorResponse,
)
from src.core.services.amazon_import_service import AmazonImportService
from src.infrastructure.scrapers.amazon_search_api import (
    AmazonSearchAPIClient,
    get_amazon_categories,
    get_category_code,
)
from src.infrastructure.storage.sqlite import SQLiteMaterialStore

router = APIRouter(prefix="/api/materials/import", tags=["amazon-import"])


def _get_import_service(
    store: SQLiteMaterialStore = Depends(get_mat_store),
) -> AmazonImportService:
    """Factory for AmazonImportService."""
    return AmazonImportService(store)


@router.get(
    "/amazon/categories",
    response_model=AmazonCategoriesResponse,
)
async def get_categories() -> AmazonCategoriesResponse:
    """Get available Amazon categories and subcategories."""
    return AmazonCategoriesResponse(categories=get_amazon_categories())


@router.post(
    "/amazon",
    response_model=AmazonImportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        503: {"model": ErrorResponse, "description": "SearchAPI unavailable"},
    },
)
async def import_from_amazon(
    request: AmazonImportRequest,
    service: AmazonImportService = Depends(_get_import_service),
) -> AmazonImportResponse:
    """
    Import materials from Amazon.ae search results.

    Searches Amazon.ae using SearchAPI.io and imports new materials
    into the catalog. Existing materials are detected by normalized_name
    and synonyms and skipped (deduplication).

    Origin confidence is set to 'unknown' - we do not guess country of origin.
    """
    # Get category code for Amazon search
    category_code = get_category_code(request.category, request.subcategory)

    # Build search query
    search_query = request.query or request.category
    if request.subcategory and request.subcategory != "all":
        search_query = f"{request.subcategory} {search_query}"

    # Search Amazon
    client = AmazonSearchAPIClient()
    search_results = await client.search(
        query=search_query,
        category=category_code,
        limit=request.limit,
        amazon_domain="amazon.ae",
    )

    if not search_results:
        # Return empty result if no search results
        return AmazonImportResponse(
            items_found=0,
            items_saved=0,
            items_skipped=0,
            items_error=0,
            items=[],
        )

    # Import items
    result = await service.import_items(
        search_results=search_results,
        category=request.category,
        unit=request.unit,
    )

    # Convert to response
    return AmazonImportResponse(
        items_found=result.items_found,
        items_saved=result.items_saved,
        items_skipped=result.items_skipped,
        items_error=result.items_error,
        items=[
            AmazonImportItemResponse(
                asin=item.asin,
                title=item.title,
                brand=item.brand,
                price=item.price,
                price_value=item.price_value,
                currency=item.currency,
                product_url=item.product_url,
                status=item.status,
                material_id=item.material_id,
                error_message=item.error_message,
                existing_material_id=item.existing_material_id,
            )
            for item in result.items
        ],
    )


@router.post(
    "/amazon/preview",
    response_model=AmazonImportResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
    },
)
async def preview_amazon_import(
    request: AmazonImportRequest,
    store: SQLiteMaterialStore = Depends(get_mat_store),
) -> AmazonImportResponse:
    """
    Preview Amazon search results without saving.

    Searches Amazon.ae and returns results with deduplication status,
    but does not save any materials to the catalog.
    """
    # Get category code for Amazon search
    category_code = get_category_code(request.category, request.subcategory)

    # Build search query
    search_query = request.query or request.category
    if request.subcategory and request.subcategory != "all":
        search_query = f"{request.subcategory} {search_query}"

    # Search Amazon
    client = AmazonSearchAPIClient()
    search_results = await client.search(
        query=search_query,
        category=category_code,
        limit=request.limit,
        amazon_domain="amazon.ae",
    )

    # Check duplicates without saving
    items: list[AmazonImportItemResponse] = []
    items_skipped = 0

    for item in search_results:
        normalized_name = item.title.strip().lower()

        # Check for existing material
        existing = await store.find_by_normalized_name(normalized_name)
        if existing:
            items.append(
                AmazonImportItemResponse(
                    asin=item.asin,
                    title=item.title,
                    brand=item.brand,
                    price=item.price,
                    price_value=item.price_value,
                    currency=item.currency,
                    product_url=item.product_url,
                    status="skipped_duplicate",
                    existing_material_id=existing.id,
                )
            )
            items_skipped += 1
            continue

        # Check by synonym
        existing_syn = await store.find_by_synonym(item.title)
        if existing_syn:
            items.append(
                AmazonImportItemResponse(
                    asin=item.asin,
                    title=item.title,
                    brand=item.brand,
                    price=item.price,
                    price_value=item.price_value,
                    currency=item.currency,
                    product_url=item.product_url,
                    status="skipped_duplicate",
                    existing_material_id=existing_syn.id,
                )
            )
            items_skipped += 1
            continue

        # Would be saved
        items.append(
            AmazonImportItemResponse(
                asin=item.asin,
                title=item.title,
                brand=item.brand,
                price=item.price,
                price_value=item.price_value,
                currency=item.currency,
                product_url=item.product_url,
                status="pending",
            )
        )

    return AmazonImportResponse(
        items_found=len(search_results),
        items_saved=0,  # Preview mode - nothing saved
        items_skipped=items_skipped,
        items_error=0,
        items=items,
    )
