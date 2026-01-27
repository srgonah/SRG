"""
Invoice management endpoints.
"""

from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.dependencies import (
    get_audit_invoice_use_case,
    get_inv_store,
    get_upload_invoice_use_case,
)
from src.application.dto.requests import AuditInvoiceRequest, UploadInvoiceRequest
from src.application.dto.responses import (
    AuditFindingResponse,
    AuditResultResponse,
    ErrorResponse,
    InvoiceResponse,
    LineItemResponse,
)
from src.application.use_cases import AuditInvoiceUseCase, UploadInvoiceUseCase
from src.infrastructure.storage.sqlite import SQLiteInvoiceStore

router = APIRouter(prefix="/api/invoices", tags=["invoices"])


@router.post(
    "/upload",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
    responses={
        422: {"model": ErrorResponse, "description": "Processing error"},
    },
)
async def upload_invoice(
    file: UploadFile = File(...),
    vendor_hint: str | None = None,
    template_id: str | None = None,
    auto_audit: bool = True,
    use_case: UploadInvoiceUseCase = Depends(get_upload_invoice_use_case),
) -> dict[str, Any]:
    """
    Upload and process an invoice.

    Extracts text, parses invoice data, and optionally audits.
    """
    # Validate file type
    filename = file.filename or ""
    if not filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file type. Use PDF or image files.",
        )

    # Read file content
    content = await file.read()

    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty file",
        )

    # Build request
    request = UploadInvoiceRequest(
        vendor_hint=vendor_hint,
        template_id=template_id,
        auto_audit=auto_audit,
    )

    # Execute
    result = await use_case.execute(content, filename, request)

    return use_case.to_response(result)


@router.post(
    "/{invoice_id}/audit",
    response_model=AuditResultResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Invoice not found"},
    },
)
async def audit_invoice(
    invoice_id: str,
    use_llm: bool = True,
    use_case: AuditInvoiceUseCase = Depends(get_audit_invoice_use_case),
) -> AuditResultResponse:
    """
    Audit an existing invoice.

    Performs rule-based and optional LLM analysis.
    """
    request = AuditInvoiceRequest(
        invoice_id=invoice_id,
        use_llm=use_llm,
    )

    try:
        result = await use_case.execute(request)
        return use_case.to_response(result)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )


@router.get(
    "/{invoice_id}",
    response_model=InvoiceResponse,
    responses={
        404: {"model": ErrorResponse, "description": "Invoice not found"},
    },
)
async def get_invoice(
    invoice_id: str,
    store: SQLiteInvoiceStore = Depends(get_inv_store),
) -> InvoiceResponse:
    """Get invoice by ID."""
    try:
        invoice = await store.get_invoice(int(invoice_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice not found: {invoice_id}",
        )

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice not found: {invoice_id}",
        )

    return InvoiceResponse(
        id=str(invoice.id) if invoice.id else "0",
        document_id=str(invoice.doc_id) if invoice.doc_id else None,
        invoice_number=invoice.invoice_no,
        vendor_name=invoice.seller_name,
        vendor_address=None,  # Not in entity
        buyer_name=invoice.buyer_name,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        line_items=[
            LineItemResponse(
                description=item.description or item.item_name,
                quantity=item.quantity,
                unit=item.unit,
                unit_price=item.unit_price,
                total_price=item.total_price,
                hs_code=item.hs_code,
                reference=None,  # Not in entity
            )
            for item in invoice.items
        ],
        calculated_total=invoice.calculated_total,
        source_file=None,  # Not in entity
        parsed_at=invoice.created_at,
        confidence=invoice.confidence,
    )


@router.get(
    "",
    response_model=dict,
)
async def list_invoices(
    limit: int = 20,
    offset: int = 0,
    store: SQLiteInvoiceStore = Depends(get_inv_store),
) -> dict[str, Any]:
    """List all invoices with pagination."""
    invoices = await store.list_invoices(limit=limit, offset=offset)
    total = await store.count_invoices() if hasattr(store, 'count_invoices') else len(invoices)

    return {
        "invoices": [
            InvoiceResponse(
                id=str(inv.id) if inv.id else "0",
                document_id=str(inv.doc_id) if inv.doc_id else None,
                invoice_number=inv.invoice_no,
                vendor_name=inv.seller_name,
                invoice_date=inv.invoice_date,
                total_amount=inv.total_amount,
                currency=inv.currency,
                line_items=[],  # Don't include items in list view
                calculated_total=inv.calculated_total,
                source_file=None,  # Not in entity
                parsed_at=inv.created_at,
                confidence=inv.confidence,
            ).model_dump()
            for inv in invoices
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_invoice(
    invoice_id: str,
    store: SQLiteInvoiceStore = Depends(get_inv_store),
) -> None:
    """Delete an invoice."""
    try:
        result = await store.delete_invoice(int(invoice_id))
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice not found: {invoice_id}",
        )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice not found: {invoice_id}",
        )


@router.get(
    "/{invoice_id}/audits",
    response_model=list[AuditResultResponse],
)
async def get_invoice_audits(
    invoice_id: str,
    limit: int = 10,
    store: SQLiteInvoiceStore = Depends(get_inv_store),
) -> list[AuditResultResponse]:
    """Get audit history for an invoice."""
    audits = await store.list_audit_results(invoice_id=int(invoice_id), limit=limit)

    return [
        AuditResultResponse(
            id=str(ar.id) if ar.id else "0",
            invoice_id=str(ar.invoice_id),
            passed=ar.passed,
            confidence=ar.confidence,
            findings=[
                AuditFindingResponse(
                    code=issue.code,
                    category=issue.category,
                    severity=issue.severity.value if hasattr(issue.severity, 'value') else str(issue.severity),
                    message=issue.message,
                    field=issue.field,
                    expected=issue.expected,
                    actual=issue.actual,
                )
                for issue in ar.issues
            ],
            audited_at=ar.audited_at or ar.created_at,
            error_count=ar.errors_count,
            warning_count=ar.warnings_count,
        )
        for ar in audits
    ]
