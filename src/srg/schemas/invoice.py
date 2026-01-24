"""Invoice schemas."""

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class LineItemSchema(BaseModel):
    """Line item in an invoice."""

    model_config = ConfigDict(from_attributes=True)

    description: str
    quantity: float
    unit: str | None = None
    unit_price: float
    total_price: float
    reference: str | None = None


class InvoiceResponse(BaseModel):
    """Invoice response schema."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    document_id: str | None = None
    invoice_number: str | None = None
    vendor_name: str | None = None
    vendor_address: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    currency: str = "DZD"
    line_items: list[LineItemSchema] = []
    calculated_total: float
    source_file: str | None = None
    parsed_at: datetime
    confidence: float = 0.0


class InvoiceListResponse(BaseModel):
    """Paginated invoice list response."""

    invoices: list[InvoiceResponse]
    total: int
    limit: int
    offset: int


class AuditRequest(BaseModel):
    """Audit request schema."""

    use_llm: bool = True
    rules: list[str] | None = None


class AuditFinding(BaseModel):
    """Single audit finding."""

    category: str
    severity: str
    message: str
    field: str | None = None
    expected: str | None = None
    actual: str | None = None


class AuditResultResponse(BaseModel):
    """Audit result response."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    invoice_id: str
    passed: bool
    confidence: float
    findings: list[AuditFinding]
    audited_at: datetime
    error_count: int
    warning_count: int
