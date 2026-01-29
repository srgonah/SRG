"""Local sales endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response

from src.api.dependencies import (
    get_create_sales_invoice_use_case,
    get_create_sales_pdf_use_case,
    get_sales_inv_store,
)
from src.application.dto.requests import CreateSalesInvoiceRequest
from src.application.dto.responses import (
    ErrorResponse,
    LocalSalesInvoiceResponse,
    LocalSalesItemResponse,
    SalesInvoiceListResponse,
)
from src.application.use_cases.create_sales_invoice import CreateSalesInvoiceUseCase
from src.application.use_cases.create_sales_pdf import CreateSalesPdfUseCase
from src.infrastructure.storage.sqlite import SQLiteSalesStore

router = APIRouter(prefix="/api/sales", tags=["sales"])


def _entity_to_response(invoice: object) -> LocalSalesInvoiceResponse:
    """Convert a LocalSalesInvoice entity to response DTO."""
    from src.core.entities.local_sale import LocalSalesInvoice

    inv: LocalSalesInvoice = invoice  # type: ignore[assignment]
    return LocalSalesInvoiceResponse(
        id=inv.id,  # type: ignore[arg-type]
        invoice_number=inv.invoice_number,
        customer_name=inv.customer_name,
        sale_date=inv.sale_date,
        subtotal=inv.subtotal,
        tax_amount=inv.tax_amount,
        total_amount=inv.total_amount,
        total_cost=inv.total_cost,
        total_profit=inv.total_profit,
        notes=inv.notes,
        items=[
            LocalSalesItemResponse(
                id=item.id,  # type: ignore[arg-type]
                inventory_item_id=item.inventory_item_id,
                material_id=item.material_id,
                description=item.description,
                quantity=item.quantity,
                unit_price=item.unit_price,
                cost_basis=item.cost_basis,
                line_total=item.line_total,
                profit=item.profit,
            )
            for item in inv.items
        ],
        created_at=inv.created_at,
    )


@router.post(
    "/invoices",
    response_model=LocalSalesInvoiceResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
async def create_sales_invoice(
    request: CreateSalesInvoiceRequest,
    use_case: CreateSalesInvoiceUseCase = Depends(get_create_sales_invoice_use_case),
) -> LocalSalesInvoiceResponse:
    """Create a local sales invoice, deduct stock, and compute profit."""
    result = await use_case.execute(request)
    return use_case.to_response(result)


@router.get(
    "/invoices",
    response_model=SalesInvoiceListResponse,
)
async def list_sales_invoices(
    limit: int = 100,
    offset: int = 0,
    store: SQLiteSalesStore = Depends(get_sales_inv_store),
) -> SalesInvoiceListResponse:
    """List local sales invoices."""
    invoices = await store.list_invoices(limit=limit, offset=offset)
    return SalesInvoiceListResponse(
        invoices=[_entity_to_response(inv) for inv in invoices],
        total=len(invoices),
    )


@router.get(
    "/invoices/{invoice_id}",
    response_model=LocalSalesInvoiceResponse,
    responses={404: {"model": ErrorResponse}},
)
async def get_sales_invoice(
    invoice_id: int,
    store: SQLiteSalesStore = Depends(get_sales_inv_store),
) -> LocalSalesInvoiceResponse:
    """Get a sales invoice by ID."""
    invoice = await store.get_invoice(invoice_id)
    if invoice is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sales invoice not found: {invoice_id}",
        )
    return _entity_to_response(invoice)


@router.get(
    "/invoices/{invoice_id}/pdf",
    responses={
        404: {"model": ErrorResponse, "description": "Sales invoice not found"},
    },
)
async def get_sales_invoice_pdf(
    invoice_id: int,
    use_case: CreateSalesPdfUseCase = Depends(get_create_sales_pdf_use_case),
) -> Response:
    """Generate and download a PDF for a sales invoice."""
    try:
        result = await use_case.execute(invoice_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return Response(
        content=result.pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{result.file_path}"',
        },
    )
