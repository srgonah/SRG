"""Local sales invoice domain entities."""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


class LocalSalesItem(BaseModel):
    """A single line item on a local sales invoice."""

    id: int | None = None
    sales_invoice_id: int | None = None
    inventory_item_id: int  # FK → inventory_items.id
    material_id: str  # FK → materials.id (denormalized)
    description: str
    quantity: float
    unit_price: float  # selling price
    cost_basis: float = 0.0  # avg_cost at time of sale * qty
    line_total: float = 0.0  # quantity * unit_price
    profit: float = 0.0  # line_total - cost_basis
    created_at: datetime = datetime.utcnow()

    @model_validator(mode="after")
    def compute_line(self) -> "LocalSalesItem":
        """Compute line_total and profit from quantity, unit_price, cost_basis."""
        self.line_total = self.quantity * self.unit_price
        self.profit = self.line_total - self.cost_basis
        return self


class LocalSalesInvoice(BaseModel):
    """A local sales invoice with line items and profit calculation."""

    id: int | None = None
    invoice_number: str
    customer_name: str
    sale_date: date = date.today()
    subtotal: float = 0.0
    tax_amount: float = 0.0
    total_amount: float = 0.0
    total_cost: float = 0.0  # sum of item costs
    total_profit: float = 0.0  # total_amount - total_cost
    notes: str | None = None
    items: list[LocalSalesItem] = Field(default_factory=list)
    created_at: datetime = datetime.utcnow()
    updated_at: datetime = datetime.utcnow()

    @model_validator(mode="after")
    def compute_totals(self) -> "LocalSalesInvoice":
        """Compute subtotal, total_cost, total_amount, total_profit from items."""
        if self.items:
            self.subtotal = sum(i.line_total for i in self.items)
            self.total_cost = sum(i.cost_basis for i in self.items)
        self.total_amount = self.subtotal + self.tax_amount
        self.total_profit = self.total_amount - self.total_cost
        return self
