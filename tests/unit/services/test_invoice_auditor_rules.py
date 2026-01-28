"""
Unit tests for InvoiceAuditorService rule-based checks.

Tests:
- Required field validation
- Mathematical calculations
- Duplicate detection
- Date validation
- Line item validation
- Price anomaly detection
- Graceful LLM degradation
"""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from src.core.entities.invoice import Invoice, IssueSeverity, LineItem, RowType
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


class TestPriceAnomalyCheck:
    """Tests for _check_price_anomalies."""

    def _make_price_store(self, stats: list[dict] | None = None) -> AsyncMock:
        """Create a mock price history store returning given stats."""
        store = AsyncMock()
        store.get_price_stats = AsyncMock(return_value=stats or [])
        return store

    @pytest.mark.asyncio
    async def test_no_price_store_returns_empty(self):
        """Should return no issues if no price store is injected."""
        auditor = InvoiceAuditorService()
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=2, unit_price=100.0, total_price=200.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_no_stats_available(self):
        """Should return no issues when no price history exists."""
        store = self._make_price_store([])
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=2, unit_price=100.0, total_price=200.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_price_within_threshold_no_issue(self):
        """Should return no issues when price is within 20% of average."""
        stats = [{"avg_price": 100.0, "min_price": 80.0, "max_price": 120.0, "occurrence_count": 5}]
        store = self._make_price_store(stats)
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=2, unit_price=115.0, total_price=230.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_price_above_threshold_flags_warning(self):
        """Should flag item when price is >20% above historical average."""
        stats = [{"avg_price": 100.0, "min_price": 80.0, "max_price": 120.0, "occurrence_count": 5}]
        store = self._make_price_store(stats)
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=2, unit_price=150.0, total_price=300.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert len(issues) == 1
        assert issues[0].code == "PRICE_ANOMALY"
        assert issues[0].severity == IssueSeverity.WARNING
        assert "above" in issues[0].message
        assert issues[0].field == "items[0].unit_price"
        assert issues[0].expected == "100.0"
        assert issues[0].actual == "150.0"

    @pytest.mark.asyncio
    async def test_price_below_threshold_flags_warning(self):
        """Should flag item when price is >20% below historical average."""
        stats = [{"avg_price": 100.0, "min_price": 80.0, "max_price": 120.0, "occurrence_count": 5}]
        store = self._make_price_store(stats)
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=2, unit_price=50.0, total_price=100.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert len(issues) == 1
        assert issues[0].code == "PRICE_ANOMALY"
        assert "below" in issues[0].message

    @pytest.mark.asyncio
    async def test_custom_threshold(self):
        """Should respect custom threshold."""
        stats = [{"avg_price": 100.0, "min_price": 90.0, "max_price": 110.0, "occurrence_count": 5}]
        store = self._make_price_store(stats)
        # Set tight threshold of 10%
        auditor = InvoiceAuditorService(
            price_history_store=store,
            price_anomaly_threshold=0.10,
        )
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=115.0, total_price=115.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert len(issues) == 1  # 15% deviation > 10% threshold

    @pytest.mark.asyncio
    async def test_skips_non_line_items(self):
        """Should skip HEADER and SUMMARY rows."""
        stats = [{"avg_price": 100.0, "min_price": 80.0, "max_price": 120.0, "occurrence_count": 5}]
        store = self._make_price_store(stats)
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="TOTAL", quantity=0, unit_price=999.0, total_price=999.0, row_type=RowType.SUMMARY),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_skips_zero_price(self):
        """Should skip items with zero or negative price."""
        stats = [{"avg_price": 100.0, "min_price": 80.0, "max_price": 120.0, "occurrence_count": 5}]
        store = self._make_price_store(stats)
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Free item", quantity=1, unit_price=0.0, total_price=0.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_skips_insufficient_history(self):
        """Should skip when fewer than 2 historical records."""
        stats = [{"avg_price": 100.0, "min_price": 100.0, "max_price": 100.0, "occurrence_count": 1}]
        store = self._make_price_store(stats)
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=200.0, total_price=200.0),
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_multiple_items_flags_only_anomalous(self):
        """Should only flag items that exceed threshold."""
        store = AsyncMock()
        # Return different stats based on item_name
        async def mock_stats(item_name=None, seller=None):
            if item_name == "cheap widget":
                return [{"avg_price": 10.0, "min_price": 8.0, "max_price": 12.0, "occurrence_count": 5}]
            if item_name == "expensive bolt":
                return [{"avg_price": 5.0, "min_price": 4.0, "max_price": 6.0, "occurrence_count": 5}]
            return []

        store.get_price_stats = AsyncMock(side_effect=mock_stats)

        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            items=[
                LineItem(item_name="Cheap Widget", quantity=10, unit_price=11.0, total_price=110.0),  # 10% above, OK
                LineItem(item_name="Expensive Bolt", quantity=5, unit_price=10.0, total_price=50.0),  # 100% above!
            ],
        )

        issues = await auditor._check_price_anomalies(invoice)

        assert len(issues) == 1
        assert "Expensive Bolt" in issues[0].message

    @pytest.mark.asyncio
    async def test_full_audit_includes_price_anomalies(self):
        """Price anomaly check should run as part of full audit."""
        stats = [{"avg_price": 100.0, "min_price": 80.0, "max_price": 120.0, "occurrence_count": 5}]
        store = AsyncMock()
        store.get_price_stats = AsyncMock(return_value=stats)

        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=200.0, total_price=200.0),
            ],
        )

        result = await auditor.audit_invoice(invoice, use_llm=False, save_result=False)

        price_issues = [i for i in result.issues if i.code == "PRICE_ANOMALY"]
        assert len(price_issues) == 1

    @pytest.mark.asyncio
    async def test_price_check_error_graceful_degradation(self):
        """Should add info issue and continue if price check fails."""
        store = AsyncMock()
        store.get_price_stats = AsyncMock(side_effect=Exception("DB error"))

        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Test Seller",
            invoice_date=date.today(),
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=100.0, total_price=100.0),
            ],
        )

        result = await auditor.audit_invoice(invoice, use_llm=False, save_result=False)

        # Should still complete
        assert result is not None
        price_errors = [i for i in result.issues if i.code == "PRICE_CHECK_ERROR"]
        assert len(price_errors) == 1
        assert price_errors[0].severity == IssueSeverity.INFO


class TestCrossInvoiceDuplicateCheck:
    """Tests for _check_cross_invoice_duplicates."""

    def _make_price_store(
        self,
        history: list[dict] | None = None,
        stats: list[dict] | None = None,
    ) -> AsyncMock:
        """Create a mock price history store with configurable returns."""
        store = AsyncMock()
        store.get_price_history = AsyncMock(return_value=history or [])
        store.get_price_stats = AsyncMock(return_value=stats or [])
        return store

    @pytest.mark.asyncio
    async def test_no_price_store_returns_empty(self):
        """Should return no issues if no price store is injected."""
        auditor = InvoiceAuditorService()
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_no_invoice_date_returns_empty(self):
        """Should return no issues if invoice has no date."""
        store = self._make_price_store()
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            seller_name="Seller A",
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_no_prior_history_returns_empty(self):
        """Should return no issues when no prior records exist."""
        store = self._make_price_store(history=[])
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []

    @pytest.mark.asyncio
    async def test_duplicate_found_flags_warning(self):
        """Should flag when same item+seller appeared within the window."""
        prior_date = (date.today() - timedelta(days=10)).isoformat()
        store = self._make_price_store(
            history=[
                {"item_name": "product a", "seller_name": "Seller A", "invoice_date": prior_date,
                 "quantity": 5, "unit_price": 10.0, "currency": "AED"},
            ],
        )
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="Product A", quantity=3, unit_price=10.0, total_price=30.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert len(issues) == 1
        assert issues[0].code == "CROSS_INVOICE_DUPLICATE"
        assert issues[0].severity == IssueSeverity.WARNING
        assert "Product A" in issues[0].message
        assert "items[0]" in issues[0].field

    @pytest.mark.asyncio
    async def test_no_seller_skips_check(self):
        """Should skip items when invoice has no seller name."""
        store = self._make_price_store()
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []
        store.get_price_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_non_line_items(self):
        """Should skip HEADER and SUMMARY rows."""
        store = self._make_price_store()
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="TOTAL", quantity=0, unit_price=0, total_price=100.0, row_type=RowType.SUMMARY),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []
        store.get_price_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_empty_names(self):
        """Should skip items with empty names."""
        store = self._make_price_store()
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="", quantity=1, unit_price=10.0, total_price=10.0),
                LineItem(item_name="   ", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []
        store.get_price_history.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_custom_window_days(self):
        """Should respect custom duplicate window setting."""
        # Record is 20 days old — within 30-day default but outside 15-day custom
        prior_date = (date.today() - timedelta(days=20)).isoformat()
        store = self._make_price_store(
            history=[
                {"item_name": "product a", "seller_name": "Seller A", "invoice_date": prior_date,
                 "quantity": 5, "unit_price": 10.0, "currency": "AED"},
            ],
        )
        auditor = InvoiceAuditorService(
            price_history_store=store,
            duplicate_window_days=15,
        )
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="Product A", quantity=3, unit_price=10.0, total_price=30.0),
            ],
        )

        await auditor._check_cross_invoice_duplicates(invoice)

        # date_from = today - 15, date_to = today - 1
        # The store was called with a narrow window, but the mock returns records regardless.
        # The actual filtering happens in the store. Since mock always returns the record,
        # it will match. The real test of custom window is that the store is called with
        # the correct date parameters.
        call_args = store.get_price_history.call_args
        assert call_args.kwargs["date_from"] == (date.today() - timedelta(days=15)).isoformat()
        assert call_args.kwargs["date_to"] == (date.today() - timedelta(days=1)).isoformat()

    @pytest.mark.asyncio
    async def test_filters_inexact_name_matches(self):
        """Should filter out partial LIKE matches that aren't exact."""
        store = self._make_price_store(
            history=[
                # Partial match — "product a premium" contains "product a" via LIKE
                {"item_name": "product a premium", "seller_name": "Seller A",
                 "invoice_date": (date.today() - timedelta(days=5)).isoformat(),
                 "quantity": 1, "unit_price": 10.0, "currency": "AED"},
            ],
        )
        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert issues == []  # "product a premium" != "product a"

    @pytest.mark.asyncio
    async def test_multiple_items_mixed(self):
        """Should flag only items that have duplicates, not all."""
        async def mock_history(item_name=None, seller=None, date_from=None, date_to=None, limit=10):
            if item_name and "widget" in item_name:
                return [{"item_name": "widget", "seller_name": "Seller A",
                         "invoice_date": (date.today() - timedelta(days=5)).isoformat(),
                         "quantity": 1, "unit_price": 10.0, "currency": "AED"}]
            return []

        store = AsyncMock()
        store.get_price_history = AsyncMock(side_effect=mock_history)
        store.get_price_stats = AsyncMock(return_value=[])

        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            invoice_date=date.today(),
            seller_name="Seller A",
            items=[
                LineItem(item_name="Widget", quantity=1, unit_price=10.0, total_price=10.0),
                LineItem(item_name="New Product", quantity=1, unit_price=20.0, total_price=20.0),
            ],
        )

        issues = await auditor._check_cross_invoice_duplicates(invoice)

        assert len(issues) == 1
        assert "Widget" in issues[0].message

    @pytest.mark.asyncio
    async def test_full_audit_includes_cross_duplicates(self):
        """Cross-invoice duplicate check should run as part of full audit."""
        prior_date = (date.today() - timedelta(days=5)).isoformat()
        store = AsyncMock()
        store.get_price_stats = AsyncMock(return_value=[])
        store.get_price_history = AsyncMock(return_value=[
            {"item_name": "product a", "seller_name": "Seller A",
             "invoice_date": prior_date, "quantity": 1, "unit_price": 10.0, "currency": "AED"},
        ])

        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Seller A",
            invoice_date=date.today(),
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        result = await auditor.audit_invoice(invoice, use_llm=False, save_result=False)

        dup_issues = [i for i in result.issues if i.code == "CROSS_INVOICE_DUPLICATE"]
        assert len(dup_issues) == 1

    @pytest.mark.asyncio
    async def test_duplicate_check_error_graceful_degradation(self):
        """Should add info issue and continue if duplicate check fails."""
        store = AsyncMock()
        store.get_price_stats = AsyncMock(return_value=[])
        store.get_price_history = AsyncMock(side_effect=Exception("DB timeout"))

        auditor = InvoiceAuditorService(price_history_store=store)
        invoice = Invoice(
            id=1,
            invoice_no="INV-001",
            seller_name="Seller A",
            invoice_date=date.today(),
            items=[
                LineItem(item_name="Product A", quantity=1, unit_price=10.0, total_price=10.0),
            ],
        )

        result = await auditor.audit_invoice(invoice, use_llm=False, save_result=False)

        assert result is not None
        dup_errors = [i for i in result.issues if i.code == "DUPLICATE_CHECK_ERROR"]
        assert len(dup_errors) == 1
        assert dup_errors[0].severity == IssueSeverity.INFO
