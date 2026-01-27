"""
Unit tests for InvoiceAuditorService rule-based checks.

Tests:
- Required field validation
- Mathematical calculations
- Duplicate detection
- Date validation
- Line item validation
- Graceful LLM degradation
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.entities.invoice import Invoice, IssueSeverity, LineItem
from src.core.services.invoice_auditor import InvoiceAuditorService


class TestRequiredFieldsCheck:
    """Tests for _check_required_fields."""

    @pytest.fixture
    def auditor(self):
        """Auditor service without LLM."""
        return InvoiceAuditorService()

    def test_all_fields_present(self, auditor):
        """Should return no issues when all required fields present."""
        invoice = Invoice(
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[
                LineItem(item_name="Product", quantity=1, unit_price=100, total_price=100)
            ],
        )

        issues = auditor._check_required_fields(invoice)

        assert len(issues) == 0

    def test_missing_invoice_number(self, auditor):
        """Should flag missing invoice number."""
        invoice = Invoice(
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[LineItem(item_name="Product", quantity=1, unit_price=100, total_price=100)],
        )

        issues = auditor._check_required_fields(invoice)

        assert len(issues) == 1
        assert issues[0].code == "MISSING_REQUIRED_FIELD"
        assert issues[0].severity == IssueSeverity.ERROR
        assert "invoice number" in issues[0].message.lower()

    def test_missing_seller_name(self, auditor):
        """Should flag missing seller name."""
        invoice = Invoice(
            invoice_no="INV-001",
            invoice_date=date.today(),
            items=[LineItem(item_name="Product", quantity=1, unit_price=100, total_price=100)],
        )

        issues = auditor._check_required_fields(invoice)

        assert len(issues) == 1
        assert issues[0].field == "seller_name"

    def test_missing_invoice_date(self, auditor):
        """Should flag missing invoice date."""
        invoice = Invoice(
            invoice_no="INV-001",
            seller_name="Test Seller",
            items=[LineItem(item_name="Product", quantity=1, unit_price=100, total_price=100)],
        )

        issues = auditor._check_required_fields(invoice)

        assert len(issues) == 1
        assert issues[0].field == "invoice_date"

    def test_no_line_items(self, auditor):
        """Should flag missing line items."""
        invoice = Invoice(
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[],
        )

        issues = auditor._check_required_fields(invoice)

        assert len(issues) == 1
        assert issues[0].code == "NO_LINE_ITEMS"

    def test_multiple_missing_fields(self, auditor):
        """Should report all missing fields."""
        invoice = Invoice(items=[])

        issues = auditor._check_required_fields(invoice)

        # Missing: invoice_no, seller_name, invoice_date, items
        assert len(issues) == 4


class TestMathCheck:
    """Tests for _check_math."""

    @pytest.fixture
    def auditor(self):
        return InvoiceAuditorService()

    def test_correct_line_totals(self, auditor):
        """Should pass when line totals are correct."""
        invoice = Invoice(
            items=[
                LineItem(item_name="A", quantity=2, unit_price=10.00, total_price=20.00),
                LineItem(item_name="B", quantity=3, unit_price=15.00, total_price=45.00),
            ],
        )

        issues, checks = auditor._check_math(invoice)

        assert len(issues) == 0
        assert len(checks) == 2
        assert all(c.passed for c in checks)

    def test_incorrect_line_total(self, auditor):
        """Should flag incorrect line total."""
        invoice = Invoice(
            items=[
                LineItem(item_name="A", quantity=2, unit_price=10.00, total_price=25.00),  # Wrong!
            ],
        )

        issues, checks = auditor._check_math(invoice)

        assert len(issues) == 1
        assert issues[0].code == "LINE_TOTAL_MISMATCH"
        assert issues[0].severity == IssueSeverity.ERROR
        assert issues[0].expected == "20.0"
        assert issues[0].actual == "25.0"

    def test_invoice_total_correct(self, auditor):
        """Should pass when invoice total matches sum of items."""
        invoice = Invoice(
            total_amount=65.00,
            items=[
                LineItem(item_name="A", quantity=2, unit_price=10.00, total_price=20.00),
                LineItem(item_name="B", quantity=3, unit_price=15.00, total_price=45.00),
            ],
        )

        issues, checks = auditor._check_math(invoice)

        assert len(issues) == 0
        # 2 line checks + 1 total check
        assert len(checks) == 3

    def test_invoice_total_mismatch_small(self, auditor):
        """Should warn on small total mismatch."""
        invoice = Invoice(
            total_amount=66.00,  # Off by 1.00
            items=[
                LineItem(item_name="A", quantity=2, unit_price=10.00, total_price=20.00),
                LineItem(item_name="B", quantity=3, unit_price=15.00, total_price=45.00),
            ],
        )

        issues, checks = auditor._check_math(invoice)

        assert len(issues) == 1
        assert issues[0].code == "TOTAL_MISMATCH"
        assert issues[0].severity == IssueSeverity.WARNING  # Small diff = warning

    def test_invoice_total_mismatch_large(self, auditor):
        """Should error on large total mismatch."""
        invoice = Invoice(
            total_amount=100.00,  # Off by 35.00
            items=[
                LineItem(item_name="A", quantity=2, unit_price=10.00, total_price=20.00),
                LineItem(item_name="B", quantity=3, unit_price=15.00, total_price=45.00),
            ],
        )

        issues, checks = auditor._check_math(invoice)

        assert len(issues) == 1
        assert issues[0].severity == IssueSeverity.ERROR  # Large diff = error

    def test_tax_calculation_error(self, auditor):
        """Should flag tax calculation mismatch."""
        invoice = Invoice(
            subtotal=100.00,
            tax_amount=15.00,
            total_amount=120.00,  # Should be 115.00
            items=[
                LineItem(item_name="A", quantity=10, unit_price=10.00, total_price=100.00),
            ],
        )

        issues, checks = auditor._check_math(invoice)

        # Should have tax calculation issue
        tax_issues = [i for i in issues if i.code == "TAX_CALCULATION_ERROR"]
        assert len(tax_issues) == 1


class TestDuplicateCheck:
    """Tests for _check_duplicates."""

    @pytest.fixture
    def auditor(self):
        return InvoiceAuditorService()

    def test_no_duplicates(self, auditor):
        """Should pass with unique items."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.00, total_price=10.00),
                LineItem(item_name="Product B", quantity=2, unit_price=20.00, total_price=40.00),
            ],
        )

        issues = auditor._check_duplicates(invoice)

        assert len(issues) == 0

    def test_duplicate_detected(self, auditor):
        """Should flag duplicate items (same name and price)."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.00, total_price=10.00),
                LineItem(item_name="Product A", quantity=2, unit_price=10.00, total_price=20.00),
            ],
        )

        issues = auditor._check_duplicates(invoice)

        assert len(issues) == 1
        assert issues[0].code == "POSSIBLE_DUPLICATE"
        assert "line 1 and 2" in issues[0].message

    def test_same_name_different_price_ok(self, auditor):
        """Same name but different price should not be flagged."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.00, total_price=10.00),
                LineItem(item_name="Product A", quantity=1, unit_price=15.00, total_price=15.00),
            ],
        )

        issues = auditor._check_duplicates(invoice)

        assert len(issues) == 0

    def test_case_insensitive_duplicate(self, auditor):
        """Should detect duplicates regardless of case."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.00, total_price=10.00),
                LineItem(item_name="PRODUCT A", quantity=2, unit_price=10.00, total_price=20.00),
            ],
        )

        issues = auditor._check_duplicates(invoice)

        assert len(issues) == 1


class TestDateCheck:
    """Tests for _check_dates."""

    @pytest.fixture
    def auditor(self):
        return InvoiceAuditorService()

    def test_valid_date(self, auditor):
        """Should pass for valid recent date."""
        invoice = Invoice(invoice_date=date.today() - timedelta(days=30))

        issues = auditor._check_dates(invoice)

        assert len(issues) == 0

    def test_future_date(self, auditor):
        """Should warn on future date."""
        invoice = Invoice(invoice_date=date.today() + timedelta(days=7))

        issues = auditor._check_dates(invoice)

        assert len(issues) == 1
        assert issues[0].code == "FUTURE_DATE"
        assert issues[0].severity == IssueSeverity.WARNING

    def test_old_date(self, auditor):
        """Should warn on date over 1 year old."""
        invoice = Invoice(invoice_date=date.today() - timedelta(days=400))

        issues = auditor._check_dates(invoice)

        assert len(issues) == 1
        assert issues[0].code == "OLD_DATE"

    def test_due_before_invoice(self, auditor):
        """Should error when due date is before invoice date."""
        invoice = Invoice(
            invoice_date=date.today(),
            due_date=date.today() - timedelta(days=10),
        )

        issues = auditor._check_dates(invoice)

        assert len(issues) == 1
        assert issues[0].code == "DUE_BEFORE_INVOICE"
        assert issues[0].severity == IssueSeverity.ERROR


class TestLineItemCheck:
    """Tests for _check_line_items."""

    @pytest.fixture
    def auditor(self):
        return InvoiceAuditorService()

    def test_valid_line_items(self, auditor):
        """Should pass for valid line items."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Valid Product", quantity=5, unit_price=10.00, total_price=50.00),
            ],
        )

        issues = auditor._check_line_items(invoice)

        assert len(issues) == 0

    def test_negative_quantity(self, auditor):
        """Should warn on negative quantity."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product", quantity=-5, unit_price=10.00, total_price=-50.00),
            ],
        )

        issues = auditor._check_line_items(invoice)

        neg_qty = [i for i in issues if i.code == "NEGATIVE_QUANTITY"]
        assert len(neg_qty) == 1

    def test_negative_price(self, auditor):
        """Should warn on negative unit price."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product", quantity=5, unit_price=-10.00, total_price=-50.00),
            ],
        )

        issues = auditor._check_line_items(invoice)

        neg_price = [i for i in issues if i.code == "NEGATIVE_PRICE"]
        assert len(neg_price) == 1

    def test_zero_quantity(self, auditor):
        """Should warn on zero quantity."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product", quantity=0, unit_price=10.00, total_price=0.00),
            ],
        )

        issues = auditor._check_line_items(invoice)

        zero_qty = [i for i in issues if i.code == "ZERO_QUANTITY"]
        assert len(zero_qty) == 1

    def test_high_unit_price(self, auditor):
        """Should warn on unusually high unit price."""
        invoice = Invoice(
            items=[
                LineItem(item_name="Product", quantity=1, unit_price=2_000_000.00, total_price=2_000_000.00),
            ],
        )

        issues = auditor._check_line_items(invoice)

        high_price = [i for i in issues if i.code == "HIGH_UNIT_PRICE"]
        assert len(high_price) == 1

    def test_missing_description(self, auditor):
        """Should warn on missing or too short description."""
        invoice = Invoice(
            items=[
                LineItem(item_name="", quantity=1, unit_price=10.00, total_price=10.00),
                LineItem(item_name="AB", quantity=1, unit_price=10.00, total_price=10.00),  # Too short
            ],
        )

        issues = auditor._check_line_items(invoice)

        missing_desc = [i for i in issues if i.code == "MISSING_DESCRIPTION"]
        assert len(missing_desc) == 2


class TestFullAudit:
    """Integration tests for full audit flow."""

    @pytest.fixture
    def auditor(self):
        return InvoiceAuditorService()

    @pytest.mark.asyncio
    async def test_audit_valid_invoice(self, auditor):
        """Should pass audit for valid invoice."""
        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            total_amount=65.00,
            items=[
                LineItem(item_name="Product A", quantity=2, unit_price=10.00, total_price=20.00),
                LineItem(item_name="Product B", quantity=3, unit_price=15.00, total_price=45.00),
            ],
        )

        result = await auditor.audit_invoice(invoice, use_llm=False, save_result=False)

        assert result.passed is True
        assert result.confidence == 1.0
        assert len(result.issues) == 0
        assert len(result.arithmetic_checks) > 0

    @pytest.mark.asyncio
    async def test_audit_invalid_invoice(self, auditor):
        """Should fail audit for invalid invoice."""
        invoice = Invoice(
            id=1,
            # Missing required fields
            total_amount=100.00,
            items=[
                LineItem(item_name="Product", quantity=2, unit_price=10.00, total_price=25.00),  # Wrong total
            ],
        )

        result = await auditor.audit_invoice(invoice, use_llm=False, save_result=False)

        assert result.passed is False
        assert result.confidence < 1.0
        assert len(result.issues) > 0

    @pytest.mark.asyncio
    async def test_audit_rules_only_fast(self, auditor):
        """audit_rules_only should skip LLM."""
        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[LineItem(item_name="Product", quantity=1, unit_price=10.00, total_price=10.00)],
        )

        result = await auditor.audit_rules_only(invoice)

        assert result.metadata.get("llm_used") is False


class TestLLMGracefulDegradation:
    """Tests for LLM failure handling."""

    @pytest.mark.asyncio
    async def test_llm_unavailable_continues(self):
        """Should continue audit when LLM is unavailable."""
        mock_llm = AsyncMock()
        mock_llm.is_available.return_value = False

        auditor = InvoiceAuditorService(llm_provider=mock_llm)

        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[LineItem(item_name="Product", quantity=1, unit_price=10.00, total_price=10.00)],
        )

        result = await auditor.audit_invoice(invoice, use_llm=True, save_result=False)

        # Should still complete with rule-based checks
        assert result is not None
        assert result.metadata.get("llm_used") is False

    @pytest.mark.asyncio
    async def test_llm_error_graceful_degradation(self):
        """Should add warning but continue when LLM fails."""
        mock_llm = AsyncMock()
        mock_llm.is_available.return_value = True
        mock_llm.generate.side_effect = Exception("LLM connection failed")

        auditor = InvoiceAuditorService(llm_provider=mock_llm)

        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[LineItem(item_name="Product", quantity=1, unit_price=10.00, total_price=10.00)],
        )

        result = await auditor.audit_invoice(invoice, use_llm=True, save_result=False)

        # Should complete and add warning
        assert result is not None
        llm_warnings = [i for i in result.issues if i.code == "LLM_UNAVAILABLE"]
        assert len(llm_warnings) == 1
