"""
Materials catalog endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import (
    get_add_to_catalog_use_case,
    get_ingest_material_use_case,
    get_mat_store,
    get_price_store,
)
from src.application.dto.requests import AddToCatalogRequest, IngestMaterialRequest
from src.application.dto.responses import (
    AddToCatalogResponse,
    IngestMaterialResponse,
    MaterialListResponse,
    MaterialResponse,
    MaterialSynonymResponse,
)
from src.application.use_cases.add_to_catalog import AddToCatalogUseCase
from src.application.use_cases.ingest_material import IngestMaterialUseCase
from src.core.exceptions import CatalogError, InvoiceNotFoundError
from src.infrastructure.storage.sqlite.material_store import SQLiteMaterialStore
from src.infrastructure.storage.sqlite.price_history_store import SQLitePriceHistoryStore

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
