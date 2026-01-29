"""
PDF Template management endpoints.

Upload, manage, and configure PDF templates for document generation.
"""

import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from src.application.dto.responses import (
    ErrorResponse,
    TemplateListResponse,
    TemplatePositionResponse,
    TemplatePositionsResponse,
    TemplateResponse,
)
from src.config import get_logger, get_settings
from src.core.entities.template import (
    PdfTemplate,
    Position,
    TemplatePositions,
    TemplateType,
)
from src.infrastructure.storage.sqlite.template_store import SQLiteTemplateStore

_logger = get_logger(__name__)

router = APIRouter(prefix="/api/templates", tags=["templates"])

# Template assets directory
TEMPLATES_DIR = Path(get_settings().storage.data_dir) / "templates"
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)


def get_template_store() -> SQLiteTemplateStore:
    """Get template store instance."""
    return SQLiteTemplateStore()


def _template_to_response(template: PdfTemplate) -> TemplateResponse:
    """Convert template entity to response DTO."""
    positions = None
    if template.positions:
        positions = TemplatePositionsResponse(
            company_name=_pos_to_response(template.positions.company_name),
            company_address=_pos_to_response(template.positions.company_address),
            logo=_pos_to_response(template.positions.logo),
            document_title=_pos_to_response(template.positions.document_title),
            document_number=_pos_to_response(template.positions.document_number),
            document_date=_pos_to_response(template.positions.document_date),
            seller_info=_pos_to_response(template.positions.seller_info),
            buyer_info=_pos_to_response(template.positions.buyer_info),
            bank_details=_pos_to_response(template.positions.bank_details),
            items_table=_pos_to_response(template.positions.items_table),
            totals=_pos_to_response(template.positions.totals),
            signature=_pos_to_response(template.positions.signature),
            stamp=_pos_to_response(template.positions.stamp),
            footer=_pos_to_response(template.positions.footer),
        )

    return TemplateResponse(
        id=template.id or 0,
        name=template.name,
        description=template.description,
        template_type=template.template_type.value,
        background_path=template.background_path,
        signature_path=template.signature_path,
        stamp_path=template.stamp_path,
        logo_path=template.logo_path,
        positions=positions,
        page_size=template.page_size,
        orientation=template.orientation,
        margin_top=template.margin_top,
        margin_bottom=template.margin_bottom,
        margin_left=template.margin_left,
        margin_right=template.margin_right,
        primary_color=template.primary_color,
        secondary_color=template.secondary_color,
        header_font_size=template.header_font_size,
        body_font_size=template.body_font_size,
        is_default=template.is_default,
        is_active=template.is_active,
        created_at=template.created_at,
        updated_at=template.updated_at,
    )


def _pos_to_response(pos: Position | None) -> TemplatePositionResponse | None:
    """Convert position to response."""
    if not pos:
        return None
    return TemplatePositionResponse(
        x=pos.x,
        y=pos.y,
        width=pos.width,
        height=pos.height,
        font_size=pos.font_size,
        alignment=pos.alignment,
    )


@router.post(
    "",
    response_model=TemplateResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        422: {"model": ErrorResponse, "description": "Validation error"},
    },
)
async def create_template(
    name: str = Form(...),
    template_type: str = Form(default="proforma"),
    description: str = Form(default=""),
    positions_json: str = Form(default="{}"),
    page_size: str = Form(default="A4"),
    orientation: str = Form(default="portrait"),
    margin_top: float = Form(default=10.0),
    margin_bottom: float = Form(default=10.0),
    margin_left: float = Form(default=10.0),
    margin_right: float = Form(default=10.0),
    primary_color: str = Form(default="#000000"),
    secondary_color: str = Form(default="#666666"),
    is_default: bool = Form(default=False),
    background: UploadFile | None = File(default=None),
    signature: UploadFile | None = File(default=None),
    stamp: UploadFile | None = File(default=None),
    logo: UploadFile | None = File(default=None),
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> TemplateResponse:
    """
    Create a new PDF template with optional assets.

    Upload background image, signature, stamp, and logo files along with
    position configuration for dynamic elements.
    """
    # Validate template type
    try:
        tpl_type = TemplateType(template_type)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid template type: {template_type}",
        )

    # Parse positions JSON
    try:
        positions_data = json.loads(positions_json)
        positions = TemplatePositions.from_dict(positions_data)
    except json.JSONDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid positions JSON",
        )

    # Create template directory
    template_dir = TEMPLATES_DIR / f"template_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    template_dir.mkdir(parents=True, exist_ok=True)

    # Save uploaded files
    background_path = await _save_upload(background, template_dir, "background")
    signature_path = await _save_upload(signature, template_dir, "signature")
    stamp_path = await _save_upload(stamp, template_dir, "stamp")
    logo_path = await _save_upload(logo, template_dir, "logo")

    # Create template entity
    template = PdfTemplate(
        name=name,
        description=description,
        template_type=tpl_type,
        background_path=background_path,
        signature_path=signature_path,
        stamp_path=stamp_path,
        logo_path=logo_path,
        positions=positions,
        page_size=page_size,
        orientation=orientation,
        margin_top=margin_top,
        margin_bottom=margin_bottom,
        margin_left=margin_left,
        margin_right=margin_right,
        primary_color=primary_color,
        secondary_color=secondary_color,
        is_default=is_default,
        is_active=True,
    )

    # Save to database
    created = await store.create_template(template)

    _logger.info("template_created_via_api", template_id=created.id, name=name)

    return _template_to_response(created)


async def _save_upload(
    upload: UploadFile | None, target_dir: Path, prefix: str
) -> str | None:
    """Save uploaded file and return path."""
    if not upload or not upload.filename:
        return None

    # Get file extension
    ext = Path(upload.filename).suffix.lower()
    if ext not in [".png", ".jpg", ".jpeg", ".gif", ".webp"]:
        return None

    # Save file
    filename = f"{prefix}{ext}"
    filepath = target_dir / filename

    content = await upload.read()
    with open(filepath, "wb") as f:
        f.write(content)

    return str(filepath)


@router.get(
    "",
    response_model=TemplateListResponse,
)
async def list_templates(
    template_type: str | None = Query(default=None, description="Filter by type"),
    active_only: bool = Query(default=True, description="Only show active templates"),
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> TemplateListResponse:
    """List all PDF templates with optional filtering."""
    tpl_type = None
    if template_type:
        try:
            tpl_type = TemplateType(template_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid template type: {template_type}",
            )

    templates = await store.list_templates(
        template_type=tpl_type,
        active_only=active_only,
        limit=limit,
        offset=offset,
    )

    total = await store.count_templates(template_type=tpl_type)

    return TemplateListResponse(
        templates=[_template_to_response(t) for t in templates],
        total=total,
    )


@router.get(
    "/{template_id}",
    response_model=TemplateResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Template not found"},
    },
)
async def get_template(
    template_id: int,
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> TemplateResponse:
    """Get a specific template by ID."""
    template = await store.get_template(template_id)

    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    return _template_to_response(template)


@router.delete(
    "/{template_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        404: {"model": ErrorResponse, "description": "Template not found"},
    },
)
async def delete_template(
    template_id: int,
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> None:
    """Delete a template."""
    # Get template to find asset directory
    template = await store.get_template(template_id)
    if not template:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    # Delete from database
    deleted = await store.delete_template(template_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Template not found: {template_id}",
        )

    # Optionally clean up asset files
    if template.background_path:
        asset_dir = Path(template.background_path).parent
        if asset_dir.exists() and asset_dir.name.startswith("template_"):
            try:
                shutil.rmtree(asset_dir)
            except Exception as e:
                _logger.warning("failed_to_delete_template_assets", error=str(e))

    _logger.info("template_deleted", template_id=template_id)
