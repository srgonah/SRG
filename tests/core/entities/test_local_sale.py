"""Tests for local sales entities."""



from src.core.entities.local_sale import LocalSalesInvoice, LocalSalesItem


class TestLocalSalesItem:
    """Tests for LocalSalesItem entity."""

    def test_compute_line_total(self):
        """Test line_total = quantity * unit_price."""
        item = LocalSalesItem(
            inventory_item_id=1,
            material_id="MAT-001",
            description="Cable 3x2.5mm",
            quantity=10.0,
            unit_price=5.0,
        )
        assert item.line_total == 50.0

    def test_compute_profit(self):
        """Test profit = line_total - cost_basis."""
        item = LocalSalesItem(
            inventory_item_id=1,
            material_id="MAT-001",
            description="Cable 3x2.5mm",
            quantity=10.0,
            unit_price=5.0,
            cost_basis=30.0,
        )
        assert item.line_total == 50.0
        assert item.profit == 20.0

    def test_zero_profit(self):
        """Test zero profit when selling at cost."""
        item = LocalSalesItem(
            inventory_item_id=1,
            material_id="MAT-001",
            description="Cable",
            quantity=10.0,
            unit_price=3.0,
            cost_basis=30.0,
        )
        assert item.profit == 0.0

    def test_negative_profit(self):
        """Test negative profit (loss)."""
        item = LocalSalesItem(
            inventory_item_id=1,
            material_id="MAT-001",
            description="Cable",
            quantity=10.0,
            unit_price=2.0,
            cost_basis=30.0,
        )
        assert item.profit == -10.0

    def test_defaults(self):
        """Test default values."""
        item = LocalSalesItem(
            inventory_item_id=1,
            material_id="MAT-001",
            description="Test",
            quantity=1.0,
            unit_price=10.0,
        )
        assert item.id is None
        assert item.sales_invoice_id is None
        assert item.cost_basis == 0.0


class TestLocalSalesInvoice:
    """Tests for LocalSalesInvoice entity."""

    def test_compute_totals(self):
        """Test compute_totals model_validator."""
        items = [
            LocalSalesItem(
                inventory_item_id=1,
                material_id="MAT-001",
                description="Item A",
                quantity=10.0,
                unit_price=5.0,
                cost_basis=30.0,
            ),
            LocalSalesItem(
                inventory_item_id=2,
                material_id="MAT-002",
                description="Item B",
                quantity=5.0,
                unit_price=20.0,
                cost_basis=50.0,
            ),
        ]
        invoice = LocalSalesInvoice(
            invoice_number="LS-001",
            customer_name="Test Customer",
            items=items,
        )
        assert invoice.subtotal == 150.0  # 50 + 100
        assert invoice.total_cost == 80.0  # 30 + 50
        assert invoice.total_amount == 150.0  # subtotal + 0 tax
        assert invoice.total_profit == 70.0  # 150 - 80

    def test_compute_totals_with_tax(self):
        """Test totals with tax."""
        items = [
            LocalSalesItem(
                inventory_item_id=1,
                material_id="MAT-001",
                description="Item A",
                quantity=10.0,
                unit_price=10.0,
                cost_basis=50.0,
            ),
        ]
        invoice = LocalSalesInvoice(
            invoice_number="LS-002",
            customer_name="Test",
            tax_amount=5.0,
            items=items,
        )
        assert invoice.subtotal == 100.0
        assert invoice.total_amount == 105.0
        assert invoice.total_profit == 55.0  # 105 - 50

    def test_empty_items(self):
        """Test invoice with no items."""
        invoice = LocalSalesInvoice(
            invoice_number="LS-003",
            customer_name="Test",
        )
        assert invoice.subtotal == 0.0
        assert invoice.total_amount == 0.0
        assert invoice.total_profit == 0.0
        assert invoice.items == []

    def test_defaults(self):
        """Test default values."""
        invoice = LocalSalesInvoice(
            invoice_number="LS-004",
            customer_name="Test",
        )
        assert invoice.id is None
        assert invoice.notes is None
        assert invoice.tax_amount == 0.0
