"""
Invoice domain entities with Pydantic v2 validation.

All numeric fields use validators to ensure they're never None,
preventing TypeError in downstream comparisons.
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator


class RowType(str, Enum):
    """Type of row in invoice table."""

    LINE_ITEM = "line_item"
    HEADER = "header"
    SUMMARY = "summary"
    SUBTOTAL = "subtotal"


class ParsingStatus(str, Enum):
    """Invoice parsing status."""

    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    NEEDS_REVIEW = "needs_review"


class AuditStatus(str, Enum):
    """Invoice audit verdict."""

    PASS = "PASS"
    HOLD = "HOLD"
    FAIL = "FAIL"
    ERROR = "ERROR"


class IssueSeverity(str, Enum):
    """Severity level for audit issues."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class LineItem(BaseModel):
    """
    Invoice line item with guaranteed-valid numeric fields.

    Numeric fields default to 0.0 (never None) to prevent comparison crashes.
    """

    id: int | None = None
    invoice_id: int | None = None
    line_number: int = 0

    # Identification
    item_name: str = ""
    description: str = ""
    hs_code: str | None = None
    unit: str | None = None
    brand: str | None = None
    model: str | None = None

    # Numeric fields - NEVER None
    quantity: float = 0.0
    unit_price: float = 0.0
    total_price: float = 0.0

    # Metadata
    row_type: RowType = RowType.LINE_ITEM

    @field_validator("quantity", "unit_price", "total_price", mode="before")
    @classmethod
    def coerce_numeric(cls, v: Any) -> float:
        """Convert None/empty/invalid to 0.0."""
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, Decimal):
            return float(v)
        try:
            s = str(v).strip().replace(",", "")
            if s.lower() in {"none", "nan", "null", ""}:
                return 0.0
            return float(s)
        except (ValueError, TypeError, AttributeError):
            return 0.0

    @field_validator("item_name", "description", mode="before")
    @classmethod
    def coerce_string(cls, v: Any) -> str:
        """Ensure string fields are never None."""
        if v is None:
            return ""
        return str(v).strip()

    @property
    def calculated_total(self) -> float:
        """Calculate expected total from qty * price."""
        return self.quantity * self.unit_price

    @property
    def has_arithmetic_error(self) -> bool:
        """Check if stated total differs from calculated."""
        if self.total_price == 0.0 or self.quantity == 0.0:
            return False
        expected = self.calculated_total
        diff = abs(self.total_price - expected)
        return diff > 0.01  # Allow 1 cent tolerance


class BankDetails(BaseModel):
    """Bank account information."""

    beneficiary_name: str | None = None
    bank_name: str | None = None
    account_number: str | None = None
    iban: str | None = None
    swift: str | None = None
    bank_address: str | None = None


class Invoice(BaseModel):
    """
    Parsed invoice with guaranteed-valid fields.

    All numeric fields default to 0.0 to prevent comparison crashes.
    """

    id: int | None = None
    doc_id: int | None = None

    # Invoice metadata
    invoice_no: str | None = None
    invoice_date: date | None = None
    due_date: date | None = None
    seller_name: str | None = None
    buyer_name: str | None = None
    company_key: str | None = None
    currency: str = "USD"

    # Numeric totals - NEVER None
    total_amount: float = 0.0
    subtotal: float = 0.0
    tax_amount: float = 0.0
    discount_amount: float = 0.0
    total_quantity: float = 0.0

    # Quality metrics
    quality_score: float = 0.0
    confidence: float = 0.0
    template_confidence: float = 0.0

    # Parsing metadata
    parser_version: str = "v1.0"
    template_id: str | None = None
    parsing_status: ParsingStatus = ParsingStatus.OK
    error_message: str | None = None

    # Line items
    items: list[LineItem] = Field(default_factory=list)

    # Bank details
    bank_details: BankDetails | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @field_validator("invoice_date", "due_date", mode="before")
    @classmethod
    def coerce_date(cls, v: Any) -> date | None:
        """Convert string to date, accepting ISO format or common formats."""
        if v is None:
            return None
        if isinstance(v, date):
            return v
        if isinstance(v, datetime):
            return v.date()
        if isinstance(v, str):
            v = v.strip()
            if not v or v.lower() in {"none", "null", ""}:
                return None
            # Try ISO format first
            for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
                try:
                    return datetime.strptime(v, fmt).date()
                except ValueError:
                    continue
        return None

    @field_validator(
        "total_amount",
        "subtotal",
        "tax_amount",
        "discount_amount",
        "total_quantity",
        "quality_score",
        "confidence",
        "template_confidence",
        mode="before",
    )
    @classmethod
    def coerce_numeric(cls, v: Any) -> float:
        """Convert None/empty/invalid to 0.0."""
        if v is None or v == "":
            return 0.0
        if isinstance(v, (int, float)):
            return float(v)
        if isinstance(v, Decimal):
            return float(v)
        try:
            s = str(v).strip().replace(",", "")
            if s.lower() in {"none", "nan", "null", ""}:
                return 0.0
            return float(s)
        except (ValueError, TypeError, AttributeError):
            return 0.0

    @property
    def items_count(self) -> int:
        """Count of line items."""
        return len([i for i in self.items if i.row_type == RowType.LINE_ITEM])

    @property
    def calculated_total(self) -> float:
        """Sum of all line item totals."""
        return sum(i.total_price for i in self.items if i.row_type == RowType.LINE_ITEM)

    @property
    def has_total_mismatch(self) -> bool:
        """Check if stated total differs significantly from sum."""
        if self.total_amount == 0.0:
            return False
        diff = abs(self.total_amount - self.calculated_total)
        threshold = self.total_amount * 0.01  # 1% tolerance
        return diff > threshold


class AuditIssue(BaseModel):
    """Single audit issue/finding."""

    code: str  # Issue code like "MISSING_REQUIRED_FIELD", "LINE_TOTAL_MISMATCH"
    field: str = ""
    severity: IssueSeverity = IssueSeverity.WARNING
    category: str = ""  # "arithmetic", "bank", "contract", "format", "required"
    message: str = ""
    expected: str | None = None
    actual: str | None = None
    line_number: int | None = None  # For line-item issues

    # Backward compatibility alias
    @property
    def level(self) -> str:
        return self.severity.value


# Alias for backward compatibility
AuditFinding = AuditIssue


class ArithmeticCheck(BaseModel):
    """Single arithmetic check result."""

    check_type: str = ""  # "line_total", "invoice_total", "tax_calculation"
    field: str = ""  # Field path like "items[0].total_price" or "total_amount"
    expected: float = 0.0
    actual: float = 0.0
    difference: float = 0.0
    passed: bool = True
    description: str = ""
    line_number: int | None = None


# Backward compatibility alias
ArithmeticCheckItem = ArithmeticCheck


class ArithmeticCheckContainer(BaseModel):
    """Container for all arithmetic verification results (legacy format)."""

    line_checks: list[dict[str, Any]] = Field(default_factory=list)
    total_quantity: dict[str, Any] = Field(default_factory=dict)
    grand_total: dict[str, Any] = Field(default_factory=dict)
    overall_status: str = "PASS"
    checks: list[ArithmeticCheck] = Field(default_factory=list)


class AuditResult(BaseModel):
    """
    Complete audit result for an invoice.

    Structured into 9 sections for the frontend.
    """

    id: int | None = None
    invoice_id: int
    trace_id: str = Field(default_factory=lambda: str(uuid4()))

    # Result metadata
    success: bool = True
    passed: bool = True  # Did the invoice pass all checks?
    audit_type: str = "llm"  # "llm" or "rule_based_fallback"
    status: AuditStatus = AuditStatus.HOLD
    filename: str = ""

    # Audit metadata (llm_used, rule counts, etc.)
    metadata: dict[str, Any] = Field(default_factory=dict)

    # Arithmetic checks (new structured format)
    arithmetic_checks: list[ArithmeticCheck] = Field(default_factory=list)

    # Audited timestamp
    audited_at: datetime | None = None

    # Section 1: Document Intake
    document_intake: dict[str, Any] = Field(default_factory=dict)

    # Section 2: Proforma Summary
    proforma_summary: dict[str, Any] = Field(default_factory=dict)

    # Section 3: Items Table (enriched)
    items_table: list[dict[str, Any]] = Field(default_factory=list)

    # Section 4: Arithmetic Check (legacy container format)
    arithmetic_check: ArithmeticCheckContainer = Field(default_factory=ArithmeticCheckContainer)

    # Section 5: Amount in Words Check
    amount_words_check: dict[str, Any] = Field(default_factory=dict)

    # Section 6: Bank Details Check
    bank_details_check: dict[str, Any] = Field(default_factory=dict)

    # Section 7: Commercial Terms Suggestions
    commercial_terms_suggestions: list[dict[str, Any]] = Field(default_factory=list)

    # Section 8: Contract Summary
    contract_summary: dict[str, Any] = Field(default_factory=dict)

    # Section 9: Final Verdict
    final_verdict: dict[str, Any] = Field(default_factory=dict)

    # Issues list
    issues: list[AuditIssue] = Field(default_factory=list)

    # Processing metadata
    processing_time: float = 0.0
    llm_model: str | None = None
    confidence: float = 0.0
    error_message: str | None = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def errors_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "error")

    @property
    def warnings_count(self) -> int:
        return sum(1 for i in self.issues if i.level == "warning")

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON response."""
        return self.model_dump(mode="json")
