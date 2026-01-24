"""Invoice management endpoints."""

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from src.application.dto.requests import AuditInvoiceRequest, UploadInvoiceRequest
from src.application.use_cases import AuditInvoiceUseCase, UploadInvoiceUseCase
from src.srg.api.deps import (
    InvoiceStoreDep,
)
from src.srg.schemas.invoice import (
    AuditResultResponse,
    InvoiceListResponse,
    InvoiceResponse,
)

router = APIRouter()


@router.post(
    "/upload",
    response_model=dict,
    status_code=status.HTTP_201_CREATED,
)
async def upload_invoice(
    file: UploadFile = File(...),
    vendor_hint: str | None = None,
    auto_audit: bool = True,
):
    """Upload and process an invoice."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    valid_extensions = (".pdf", ".png", ".jpg", ".jpeg")
    if not file.filename.lower().endswith(valid_extensions):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type. Use: {', '.join(valid_extensions)}",
        )

    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    use_case = UploadInvoiceUseCase()
    request = UploadInvoiceRequest(
        vendor_hint=vendor_hint,
        auto_audit=auto_audit,
    )

    result = await use_case.execute(content, file.filename, request)
    return use_case.to_response(result)


@router.get("", response_model=InvoiceListResponse)
async def list_invoices(
    store: InvoiceStoreDep,
    limit: int = 20,
    offset: int = 0,
):
    """List all invoices with pagination."""
    invoices = await store.list_invoices(limit=limit, offset=offset)
    total = await store.count_invoices()

    return InvoiceListResponse(
        invoices=[InvoiceResponse.model_validate(inv) for inv in invoices],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: str, store: InvoiceStoreDep):
    """Get invoice by ID."""
    invoice = await store.get_invoice(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_id}")

    return InvoiceResponse.model_validate(invoice)


@router.post("/{invoice_id}/audit", response_model=AuditResultResponse)
async def audit_invoice(
    invoice_id: str,
    use_llm: bool = True,
):
    """Audit an existing invoice."""
    use_case = AuditInvoiceUseCase()
    request = AuditInvoiceRequest(invoice_id=invoice_id, use_llm=use_llm)

    try:
        result = await use_case.execute(request)
        return use_case.to_response(result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{invoice_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_invoice(invoice_id: str, store: InvoiceStoreDep):
    """Delete an invoice."""
    result = await store.delete_invoice(invoice_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Invoice not found: {invoice_id}")
