"""
Materials catalog endpoints.
"""

import csv
import io

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse

from src.api.dependencies import (
    get_add_to_catalog_use_case,
    get_catalog_matcher,
    get_ingest_material_use_case,
    get_mat_store,
    get_price_store,
)
from src.application.dto.requests import (
    AddToCatalogRequest,
    BatchIngestMaterialRequest,
    IngestMaterialRequest,
    PreviewIngestRequest,
)
from src.application.dto.responses import (
    AddToCatalogResponse,
    BatchIngestItemResult,
    BatchIngestMaterialResponse,
    IngestMaterialResponse,
    MatchCandidateResponse,
    MaterialListResponse,
    MaterialResponse,
    MaterialSynonymResponse,
    PreviewIngestResponse,
)
from src.application.use_cases.add_to_catalog import AddToCatalogUseCase
from src.application.use_cases.ingest_material import IngestMaterialUseCase
from src.config import get_logger
from src.core.exceptions import CatalogError, InvoiceNotFoundError, SRGError
from src.core.services.catalog_matcher import CatalogMatcher
from src.infrastructure.storage.sqlite.material_store import SQLiteMaterialStore
from src.infrastructure.storage.sqlite.price_history_store import SQLitePriceHistoryStore

_logger = get_logger(__name__)

router = APIRouter(prefix="/api/catalog", tags=["catalog"])


@router.post(
    "/",
    response_model=AddToCatalogResponse,
    status_code=status.HTTP_201_CREATED,
)
async def add_to_catalog(
    request: AddToCatalogRequest,
    use_case: AddToCatalogUseCase = Depends(get_add_to_catalog_use_case),
) -> AddToCatalogResponse:
    """Add invoice items to the materials catalog."""
    try:
        result = await use_case.execute(request)
        return use_case.to_response(result)
    except InvoiceNotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=e.message,
        )


@router.get("/", response_model=MaterialListResponse)
async def list_materials(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    category: str | None = Query(default=None),
    q: str | None = Query(default=None, description="Search query"),
    store: SQLiteMaterialStore = Depends(get_mat_store),
) -> MaterialListResponse:
    """List materials with optional filtering and search."""
    if q:
        materials = await store.search_by_name(q, limit=limit)
    else:
        materials = await store.list_materials(
            limit=limit, offset=offset, category=category
        )
    return MaterialListResponse(
        materials=[
            MaterialResponse(
                id=m.id or "",
                name=m.name,
                normalized_name=m.normalized_name,
                hs_code=m.hs_code,
                category=m.category,
                unit=m.unit,
                description=m.description,
                brand=m.brand,
                source_url=m.source_url,
                origin_country=m.origin_country,
                origin_confidence=m.origin_confidence.value,
                synonyms=[],
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in materials
        ],
        total=len(materials),
    )


@router.get("/export", response_model=None)
async def export_catalog(
    format: str = Query(default="json", pattern="^(json|csv)$", description="Export format: json or csv"),
    store: SQLiteMaterialStore = Depends(get_mat_store),
) -> MaterialListResponse | StreamingResponse:
    """Export the entire materials catalog as JSON or CSV."""
    materials = await store.list_materials(limit=100000, offset=0)

    if format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["name", "category", "brand", "hs_code", "origin_country", "unit"])
        for m in materials:
            writer.writerow([
                m.name,
                m.category or "",
                m.brand or "",
                m.hs_code or "",
                m.origin_country or "",
                m.unit or "",
            ])
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={
                "Content-Disposition": 'attachment; filename="catalog_export.csv"',
            },
        )

    # Default: JSON
    return MaterialListResponse(
        materials=[
            MaterialResponse(
                id=m.id or "",
                name=m.name,
                normalized_name=m.normalized_name,
                hs_code=m.hs_code,
                category=m.category,
                unit=m.unit,
                description=m.description,
                brand=m.brand,
                source_url=m.source_url,
                origin_country=m.origin_country,
                origin_confidence=m.origin_confidence.value,
                synonyms=[],
                created_at=m.created_at,
                updated_at=m.updated_at,
            )
            for m in materials
        ],
        total=len(materials),
    )


@router.get("/{material_id}", response_model=MaterialResponse)
async def get_material(
    material_id: str,
    store: SQLiteMaterialStore = Depends(get_mat_store),
    price_store: SQLitePriceHistoryStore = Depends(get_price_store),
) -> MaterialResponse:
    """Get material detail with synonyms."""
    material = await store.get_material(material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material not found: {material_id}",
        )

    return MaterialResponse(
        id=material.id or "",
        name=material.name,
        normalized_name=material.normalized_name,
        hs_code=material.hs_code,
        category=material.category,
        unit=material.unit,
        description=material.description,
        brand=material.brand,
        source_url=material.source_url,
        origin_country=material.origin_country,
        origin_confidence=material.origin_confidence.value,
        synonyms=[
            MaterialSynonymResponse(id="", synonym=s, language="en")
            for s in material.synonyms
        ],
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


@router.get(
    "/{material_id}/matches",
    response_model=list[MatchCandidateResponse],
)
async def find_matches(
    material_id: str,
    query: str = Query(..., description="Item name to match against the catalog"),
    top_k: int = Query(default=5, ge=1, le=50, description="Max candidates to return"),
    store: SQLiteMaterialStore = Depends(get_mat_store),
    matcher: CatalogMatcher = Depends(get_catalog_matcher),
) -> list[MatchCandidateResponse]:
    """Find top matching materials for a given item name query."""
    # Validate that the material exists
    material = await store.get_material(material_id)
    if material is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Material not found: {material_id}",
        )

    candidates = await matcher.find_matches(query, top_k=top_k)
    return [
        MatchCandidateResponse(
            material_id=c.material_id,
            material_name=c.material_name,
            score=c.score,
            match_type=c.match_type,
        )
        for c in candidates
    ]


@router.post(
    "/ingest",
    response_model=IngestMaterialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def ingest_material(
    request: IngestMaterialRequest,
    use_case: IngestMaterialUseCase = Depends(get_ingest_material_use_case),
) -> IngestMaterialResponse:
    """Ingest a material from an external product URL (e.g. Amazon)."""
    try:
        result = await use_case.execute(request)
        return use_case.to_response(result)
    except CatalogError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.message,
        )


@router.post(
    "/ingest/batch",
    response_model=BatchIngestMaterialResponse,
    status_code=status.HTTP_200_OK,
)
async def batch_ingest_materials(
    request: BatchIngestMaterialRequest,
    use_case: IngestMaterialUseCase = Depends(get_ingest_material_use_case),
) -> BatchIngestMaterialResponse:
    """Ingest materials from multiple product URLs (max 20).

    Processes URLs sequentially to avoid rate-limiting. Returns per-URL
    status so partial failures do not block the entire batch.
    """
    results: list[BatchIngestItemResult] = []
    succeeded = 0
    failed = 0

    for url in request.urls:
        try:
            single_request = IngestMaterialRequest(
                url=url,
                category=request.category,
                unit=request.unit,
            )
            result = await use_case.execute(single_request)
            results.append(
                BatchIngestItemResult(
                    url=url,
                    status="success",
                    material_id=result.material.id,
                )
            )
            succeeded += 1
        except SRGError as e:
            _logger.warning("batch_ingest_item_error", url=url, error=e.message)
            results.append(
                BatchIngestItemResult(
                    url=url,
                    status="error",
                    error=e.message,
                )
            )
            failed += 1
        except Exception as e:
            _logger.error("batch_ingest_item_unexpected_error", url=url, error=str(e))
            results.append(
                BatchIngestItemResult(
                    url=url,
                    status="error",
                    error=str(e),
                )
            )
            failed += 1

    return BatchIngestMaterialResponse(
        results=results,
        total=len(request.urls),
        succeeded=succeeded,
        failed=failed,
    )


@router.post(
    "/ingest/preview",
    response_model=PreviewIngestResponse,
    status_code=status.HTTP_200_OK,
)
async def preview_ingest(
    request: PreviewIngestRequest,
    use_case: IngestMaterialUseCase = Depends(get_ingest_material_use_case),
) -> PreviewIngestResponse:
    """Preview parsed product data from a URL without saving to the database.

    Fetches and parses the URL using the appropriate product fetcher,
    then returns the extracted data. No material is created or updated.
    """
    try:
        service = use_case._get_service()
        fetcher = service._find_fetcher(request.url)
        if fetcher is None:
            raise CatalogError(
                f"No fetcher supports the URL: {request.url}",
                code="UNSUPPORTED_URL",
            )

        page_data = await fetcher.fetch(request.url)

        return PreviewIngestResponse(
            title=page_data.title,
            brand=page_data.brand,
            description=page_data.description,
            category=page_data.category,
            origin_country=page_data.origin_country,
            origin_confidence=page_data.origin_confidence.value,
            evidence_text=page_data.evidence_text,
            source_url=page_data.source_url,
            suggested_synonyms=page_data.suggested_synonyms,
            raw_attributes=page_data.raw_attributes,
            asin=page_data.asin,
            weight=page_data.weight,
            dimensions=page_data.dimensions,
            price=page_data.price,
            rating=page_data.rating,
            num_ratings=page_data.num_ratings,
        )
    except CatalogError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.message,
        )
