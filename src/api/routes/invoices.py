"""
Invoice management endpoints.
"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from src.api.dependencies import (
    get_audit_invoice_use_case,
    get_inv_store,
    get_upload_invoice_use_case,
)
from src.application.dto.requests import AuditInvoiceRequest, UploadInvoiceRequest
from src.application.dto.responses import (
    AuditResultResponse,
    ErrorResponse,
    InvoiceResponse,
)
from src.application.use_cases import AuditInvoiceUseCase, UploadInvoiceUseCase

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
):
    """
    Upload and process an invoice.

    Extracts text, parses invoice data, and optionally audits.
    """
    # Validate file type
    if not file.filename.lower().endswith((".pdf", ".png", ".jpg", ".jpeg")):
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
    result = await use_case.execute(content, file.filename, request)

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
):
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
    store=Depends(get_inv_store),
):
    """Get invoice by ID."""
    invoice = await store.get_invoice(invoice_id)

    if not invoice:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Invoice not found: {invoice_id}",
        )

    return InvoiceResponse(
        id=invoice.id,
        document_id=invoice.document_id,
        invoice_number=invoice.invoice_number,
        vendor_name=invoice.vendor_name,
        vendor_address=invoice.vendor_address,
        invoice_date=invoice.invoice_date,
        due_date=invoice.due_date,
        subtotal=invoice.subtotal,
        tax_amount=invoice.tax_amount,
        total_amount=invoice.total_amount,
        currency=invoice.currency,
        line_items=[
            {
                "description": item.description,
                "quantity": item.quantity,
                "unit": item.unit,
                "unit_price": item.unit_price,
                "total_price": item.total_price,
                "reference": item.reference,
            }
            for item in invoice.line_items
        ],
        calculated_total=invoice.calculated_total,
        source_file=invoice.source_file,
        parsed_at=invoice.parsed_at,
        confidence=invoice.confidence,
    )


@router.get(
    "",
    response_model=list[InvoiceResponse],
)
async def list_invoices(
    limit: int = 20,
    offset: int = 0,
    store=Depends(get_inv_store),
):
    """List all invoices with pagination."""
    invoices = await store.list_invoices(limit=limit, offset=offset)

    return [
        InvoiceResponse(
            id=inv.id,
            document_id=inv.document_id,
            invoice_number=inv.invoice_number,
            vendor_name=inv.vendor_name,
            invoice_date=inv.invoice_date,
            total_amount=inv.total_amount,
            currency=inv.currency,
            line_items=[],  # Don't include items in list view
            calculated_total=inv.calculated_total,
            source_file=inv.source_file,
            parsed_at=inv.parsed_at,
            confidence=inv.confidence,
        )
        for inv in invoices
    ]


@router.delete(
    "/{invoice_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_invoice(
    invoice_id: str,
    store=Depends(get_inv_store),
):
    """Delete an invoice."""
    result = await store.delete_invoice(invoice_id)

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
    store=Depends(get_inv_store),
):
    """Get audit history for an invoice."""
    audits = await store.get_audit_results(invoice_id, limit=limit)

    return [
        AuditResultResponse(
            id=ar.id,
            invoice_id=ar.invoice_id,
            passed=ar.passed,
            confidence=ar.confidence,
            findings=[
                {
                    "category": f.category,
                    "severity": f.severity,
                    "message": f.message,
                    "field": f.field,
                    "expected": f.expected,
                    "actual": f.actual,
                }
                for f in ar.findings
            ],
            audited_at=ar.audited_at,
            error_count=sum(1 for f in ar.findings if f.severity == "error"),
            warning_count=sum(1 for f in ar.findings if f.severity == "warning"),
        )
        for ar in audits
    ]
