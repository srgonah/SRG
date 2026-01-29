"""
Document Creator endpoints.

Generate PDF documents from scratch using templates with wizard-collected data.
"""

import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from src.application.dto.requests import CreateProformaRequest, CreateSalesDocumentRequest
from src.application.dto.responses import (
    CreatorResultResponse,
    ErrorResponse,
    GeneratedDocumentResponse,
)
from src.config import get_logger, get_settings
from src.core.entities.template import PdfTemplate, TemplateType
from src.infrastructure.pdf.template_renderer import TemplateRenderer
from src.infrastructure.storage.sqlite.template_store import SQLiteTemplateStore

_logger = get_logger(__name__)

router = APIRouter(prefix="/api/creators", tags=["creators"])

# Output directory for generated documents
OUTPUT_DIR = Path(get_settings().storage.data_dir) / "generated"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def get_template_store() -> SQLiteTemplateStore:
    """Get template store instance."""
    return SQLiteTemplateStore()


def _calculate_totals(items: list, tax_rate: float, discount_amount: float) -> dict:
    """Calculate document totals from items."""
    subtotal = sum(item.quantity * item.unit_price for item in items)
    tax_amount = subtotal * (tax_rate / 100)
    total_amount = subtotal + tax_amount - discount_amount
    return {
        "subtotal": round(subtotal, 2),
        "tax_amount": round(tax_amount, 2),
        "discount_amount": round(discount_amount, 2),
        "total_amount": round(total_amount, 2),
    }


async def _save_generated_document(
    pdf_bytes: bytes,
    doc_type: str,
    doc_number: str,
    template_id: int | None,
    context: dict,
) -> GeneratedDocumentResponse:
    """Save generated PDF to file system and database."""
    # Generate filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_number = doc_number.replace("/", "-").replace("\\", "-")
    filename = f"{doc_type}_{safe_number}_{timestamp}.pdf"
    filepath = OUTPUT_DIR / filename

    # Save PDF file
    with open(filepath, "wb") as f:
        f.write(pdf_bytes)

    file_size = len(pdf_bytes)

    # Store in database
    from src.infrastructure.storage.sqlite.connection import get_transaction

    async with get_transaction() as conn:
        cursor = await conn.execute(
            """
            INSERT INTO generated_documents (
                document_type, template_id, source_type, source_id,
                file_name, file_path, file_size, context_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc_type,
                template_id,
                None,  # source_type (not linked to existing entity)
                None,  # source_id
                filename,
                str(filepath),
                file_size,
                json.dumps(context),
                datetime.now().isoformat(),
            ),
        )
        doc_id = cursor.lastrowid

    _logger.info(
        "document_generated",
        doc_id=doc_id,
        doc_type=doc_type,
        file_name=filename,
        file_size=file_size,
    )

    return GeneratedDocumentResponse(
        id=doc_id,
        document_type=doc_type,
        file_name=filename,
        file_path=str(filepath),
        file_size=file_size,
        doc_id=None,  # Not indexed in documents table
        created_at=datetime.now(),
    )


@router.post(
    "/proforma",
    response_model=CreatorResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Template not found"},
    },
)
async def create_proforma(
    request: CreateProformaRequest,
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> CreatorResultResponse:
    """
    Create a proforma invoice PDF from wizard data.

    Uses the specified template or the default proforma template.
    Calculates totals from line items and generates a professional PDF.
    """
    # Get template
    template: PdfTemplate | None = None
    if request.template_id:
        template = await store.get_template(request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found: {request.template_id}",
            )
    else:
        template = await store.get_default_template(TemplateType.PROFORMA)

    # Calculate totals
    totals = _calculate_totals(request.items, request.tax_rate, request.discount_amount)

    # Build document data
    doc_data = {
        "document_type": "proforma",
        "document_number": request.document_number,
        "document_date": request.document_date,
        "valid_until": request.valid_until,
        "seller": {
            "name": request.seller.name,
            "address": request.seller.address,
            "phone": request.seller.phone,
            "email": request.seller.email,
            "tax_id": request.seller.tax_id,
        },
        "buyer": {
            "name": request.buyer.name,
            "address": request.buyer.address,
            "phone": request.buyer.phone,
            "email": request.buyer.email,
            "tax_id": request.buyer.tax_id,
        },
        "bank_details": None,
        "items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total": round(item.quantity * item.unit_price, 2),
                "hs_code": item.hs_code,
            }
            for item in request.items
        ],
        "currency": request.currency,
        "subtotal": totals["subtotal"],
        "tax_amount": totals["tax_amount"],
        "discount_amount": totals["discount_amount"],
        "total_amount": totals["total_amount"],
        "notes": request.notes,
        "terms": request.terms,
    }

    if request.bank_details:
        doc_data["bank_details"] = {
            "bank_name": request.bank_details.bank_name,
            "account_name": request.bank_details.account_name,
            "account_number": request.bank_details.account_number,
            "iban": request.bank_details.iban,
            "swift_code": request.bank_details.swift_code,
            "branch": request.bank_details.branch,
        }

    # Generate PDF
    renderer = TemplateRenderer(template)
    pdf_bytes = renderer.render(doc_data)

    # Save if requested
    document = None
    if request.save_as_document:
        document = await _save_generated_document(
            pdf_bytes=pdf_bytes,
            doc_type="proforma",
            doc_number=request.document_number,
            template_id=template.id if template else None,
            context=doc_data,
        )

    return CreatorResultResponse(
        success=True,
        document=document,
        pdf_bytes=pdf_bytes if not request.save_as_document else None,
        subtotal=totals["subtotal"],
        tax_amount=totals["tax_amount"],
        discount_amount=totals["discount_amount"],
        total_amount=totals["total_amount"],
    )


@router.post(
    "/proforma/preview",
    responses={
        404: {"model": ErrorResponse, "description": "Template not found"},
    },
)
async def preview_proforma(
    request: CreateProformaRequest,
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> Response:
    """
    Preview a proforma invoice PDF without saving.

    Returns the raw PDF bytes for inline display.
    """
    # Get template
    template: PdfTemplate | None = None
    if request.template_id:
        template = await store.get_template(request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found: {request.template_id}",
            )
    else:
        template = await store.get_default_template(TemplateType.PROFORMA)

    # Calculate totals
    totals = _calculate_totals(request.items, request.tax_rate, request.discount_amount)

    # Build document data
    doc_data = {
        "document_type": "proforma",
        "document_number": request.document_number,
        "document_date": request.document_date,
        "valid_until": request.valid_until,
        "seller": {
            "name": request.seller.name,
            "address": request.seller.address,
            "phone": request.seller.phone,
            "email": request.seller.email,
            "tax_id": request.seller.tax_id,
        },
        "buyer": {
            "name": request.buyer.name,
            "address": request.buyer.address,
            "phone": request.buyer.phone,
            "email": request.buyer.email,
            "tax_id": request.buyer.tax_id,
        },
        "bank_details": None,
        "items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total": round(item.quantity * item.unit_price, 2),
                "hs_code": item.hs_code,
            }
            for item in request.items
        ],
        "currency": request.currency,
        "subtotal": totals["subtotal"],
        "tax_amount": totals["tax_amount"],
        "discount_amount": totals["discount_amount"],
        "total_amount": totals["total_amount"],
        "notes": request.notes,
        "terms": request.terms,
    }

    if request.bank_details:
        doc_data["bank_details"] = {
            "bank_name": request.bank_details.bank_name,
            "account_name": request.bank_details.account_name,
            "account_number": request.bank_details.account_number,
            "iban": request.bank_details.iban,
            "swift_code": request.bank_details.swift_code,
            "branch": request.bank_details.branch,
        }

    # Generate PDF
    renderer = TemplateRenderer(template)
    pdf_bytes = renderer.render(doc_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="preview_{request.document_number}.pdf"',
        },
    )


@router.post(
    "/sales",
    response_model=CreatorResultResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        404: {"model": ErrorResponse, "description": "Template not found"},
    },
)
async def create_sales_document(
    request: CreateSalesDocumentRequest,
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> CreatorResultResponse:
    """
    Create a sales invoice PDF from wizard data.

    Uses the specified template or the default sales template.
    """
    # Get template
    template: PdfTemplate | None = None
    if request.template_id:
        template = await store.get_template(request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found: {request.template_id}",
            )
    else:
        template = await store.get_default_template(TemplateType.SALES)

    # Calculate totals
    totals = _calculate_totals(request.items, request.tax_rate, request.discount_amount)

    # Build document data
    doc_data = {
        "document_type": "sales_invoice",
        "document_number": request.invoice_number,
        "document_date": request.invoice_date,
        "seller": {
            "name": request.seller.name,
            "address": request.seller.address,
            "phone": request.seller.phone,
            "email": request.seller.email,
            "tax_id": request.seller.tax_id,
        },
        "buyer": {
            "name": request.buyer.name,
            "address": request.buyer.address,
            "phone": request.buyer.phone,
            "email": request.buyer.email,
            "tax_id": request.buyer.tax_id,
        },
        "bank_details": None,
        "items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total": round(item.quantity * item.unit_price, 2),
                "hs_code": item.hs_code,
            }
            for item in request.items
        ],
        "currency": request.currency,
        "subtotal": totals["subtotal"],
        "tax_amount": totals["tax_amount"],
        "discount_amount": totals["discount_amount"],
        "total_amount": totals["total_amount"],
        "notes": request.notes,
        "payment_terms": request.payment_terms,
    }

    if request.bank_details:
        doc_data["bank_details"] = {
            "bank_name": request.bank_details.bank_name,
            "account_name": request.bank_details.account_name,
            "account_number": request.bank_details.account_number,
            "iban": request.bank_details.iban,
            "swift_code": request.bank_details.swift_code,
            "branch": request.bank_details.branch,
        }

    # Generate PDF
    renderer = TemplateRenderer(template)
    pdf_bytes = renderer.render(doc_data)

    # Save if requested
    document = None
    if request.save_as_document:
        document = await _save_generated_document(
            pdf_bytes=pdf_bytes,
            doc_type="sales_invoice",
            doc_number=request.invoice_number,
            template_id=template.id if template else None,
            context=doc_data,
        )

    return CreatorResultResponse(
        success=True,
        document=document,
        pdf_bytes=pdf_bytes if not request.save_as_document else None,
        subtotal=totals["subtotal"],
        tax_amount=totals["tax_amount"],
        discount_amount=totals["discount_amount"],
        total_amount=totals["total_amount"],
    )


@router.post(
    "/sales/preview",
    responses={
        404: {"model": ErrorResponse, "description": "Template not found"},
    },
)
async def preview_sales_document(
    request: CreateSalesDocumentRequest,
    store: SQLiteTemplateStore = Depends(get_template_store),
) -> Response:
    """
    Preview a sales invoice PDF without saving.

    Returns the raw PDF bytes for inline display.
    """
    # Get template
    template: PdfTemplate | None = None
    if request.template_id:
        template = await store.get_template(request.template_id)
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Template not found: {request.template_id}",
            )
    else:
        template = await store.get_default_template(TemplateType.SALES)

    # Calculate totals
    totals = _calculate_totals(request.items, request.tax_rate, request.discount_amount)

    # Build document data
    doc_data = {
        "document_type": "sales_invoice",
        "document_number": request.invoice_number,
        "document_date": request.invoice_date,
        "seller": {
            "name": request.seller.name,
            "address": request.seller.address,
            "phone": request.seller.phone,
            "email": request.seller.email,
            "tax_id": request.seller.tax_id,
        },
        "buyer": {
            "name": request.buyer.name,
            "address": request.buyer.address,
            "phone": request.buyer.phone,
            "email": request.buyer.email,
            "tax_id": request.buyer.tax_id,
        },
        "bank_details": None,
        "items": [
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total": round(item.quantity * item.unit_price, 2),
                "hs_code": item.hs_code,
            }
            for item in request.items
        ],
        "currency": request.currency,
        "subtotal": totals["subtotal"],
        "tax_amount": totals["tax_amount"],
        "discount_amount": totals["discount_amount"],
        "total_amount": totals["total_amount"],
        "notes": request.notes,
        "payment_terms": request.payment_terms,
    }

    if request.bank_details:
        doc_data["bank_details"] = {
            "bank_name": request.bank_details.bank_name,
            "account_name": request.bank_details.account_name,
            "account_number": request.bank_details.account_number,
            "iban": request.bank_details.iban,
            "swift_code": request.bank_details.swift_code,
            "branch": request.bank_details.branch,
        }

    # Generate PDF
    renderer = TemplateRenderer(template)
    pdf_bytes = renderer.render(doc_data)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="preview_{request.invoice_number}.pdf"',
        },
    )


@router.get(
    "/documents",
    response_model=list[GeneratedDocumentResponse],
)
async def list_generated_documents(
    document_type: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[GeneratedDocumentResponse]:
    """List generated documents with optional filtering."""
    from src.infrastructure.storage.sqlite.connection import get_connection

    async with get_connection() as conn:
        if document_type:
            cursor = await conn.execute(
                """
                SELECT * FROM generated_documents
                WHERE document_type = ?
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (document_type, limit, offset),
            )
        else:
            cursor = await conn.execute(
                """
                SELECT * FROM generated_documents
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset),
            )

        rows = await cursor.fetchall()

        return [
            GeneratedDocumentResponse(
                id=row["id"],
                document_type=row["document_type"],
                file_name=row["file_name"],
                file_path=row["file_path"],
                file_size=row["file_size"],
                doc_id=row["doc_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        ]


@router.get(
    "/documents/{doc_id}/download",
    responses={
        404: {"model": ErrorResponse, "description": "Document not found"},
    },
)
async def download_generated_document(doc_id: int) -> Response:
    """Download a generated document."""
    from src.infrastructure.storage.sqlite.connection import get_connection

    async with get_connection() as conn:
        cursor = await conn.execute(
            "SELECT * FROM generated_documents WHERE id = ?",
            (doc_id,),
        )
        row = await cursor.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document not found: {doc_id}",
            )

        filepath = Path(row["file_path"])
        if not filepath.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document file not found: {filepath}",
            )

        with open(filepath, "rb") as f:
            pdf_bytes = f.read()

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="{row["file_name"]}"',
            },
        )
