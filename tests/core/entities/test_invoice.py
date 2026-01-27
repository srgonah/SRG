"""Unit tests for invoice domain entities."""

from datetime import datetime
from decimal import Decimal

import pytest

from src.core.entities.invoice import (
    ArithmeticCheck,
    AuditIssue,
    AuditResult,
    AuditStatus,
    BankDetails,
    Invoice,
    LineItem,
    ParsingStatus,
    RowType,
)


class TestRowType:
    """Tests for RowType enum."""

    def test_line_item_value(self):
        assert RowType.LINE_ITEM.value == "line_item"

    def test_header_value(self):
        assert RowType.HEADER.value == "header"

    def test_summary_value(self):
        assert RowType.SUMMARY.value == "summary"

    def test_subtotal_value(self):
        assert RowType.SUBTOTAL.value == "subtotal"


class TestParsingStatus:
    """Tests for ParsingStatus enum."""

    def test_all_values_exist(self):
        expected = {"ok", "partial", "failed", "needs_review"}
        actual = {s.value for s in ParsingStatus}
        assert actual == expected


class TestAuditStatus:
    """Tests for AuditStatus enum."""

    def test_valid_statuses(self):
        """Verify the 4 required audit statuses exist."""
        expected = {"PASS", "HOLD", "FAIL", "ERROR"}
        actual = {s.value for s in AuditStatus}
        assert actual == expected


class TestLineItemCoerceNumeric:
    """Tests for LineItem numeric field coercion."""

    def test_none_coerces_to_zero(self):
        item = LineItem(quantity=None, unit_price=None, total_price=None)
        assert item.quantity == 0.0
        assert item.unit_price == 0.0
        assert item.total_price == 0.0

    def test_empty_string_coerces_to_zero(self):
        item = LineItem(quantity="", unit_price="", total_price="")
        assert item.quantity == 0.0
        assert item.unit_price == 0.0
        assert item.total_price == 0.0

    def test_int_coerces_to_float(self):
        item = LineItem(quantity=10, unit_price=100, total_price=1000)
        assert item.quantity == 10.0
        assert isinstance(item.quantity, float)

    def test_decimal_coerces_to_float(self):
        item = LineItem(quantity=Decimal("5.5"))
        assert item.quantity == 5.5
        assert isinstance(item.quantity, float)

    def test_string_number_coerces_to_float(self):
        item = LineItem(quantity="123.45", unit_price="67.89")
        assert item.quantity == 123.45
        assert item.unit_price == 67.89

    def test_comma_separated_number_coerces(self):
        item = LineItem(total_price="1,234.56")
        assert item.total_price == 1234.56

    def test_none_string_coerces_to_zero(self):
        item = LineItem(quantity="None", unit_price="null", total_price="nan")
        assert item.quantity == 0.0
        assert item.unit_price == 0.0
        assert item.total_price == 0.0

    def test_invalid_string_coerces_to_zero(self):
        item = LineItem(quantity="not_a_number")
        assert item.quantity == 0.0


class TestLineItemStringCoercion:
    """Tests for LineItem string field coercion."""

    def test_none_item_name_coerces_to_empty(self):
        item = LineItem(item_name=None)
        assert item.item_name == ""

    def test_none_description_coerces_to_empty(self):
        item = LineItem(description=None)
        assert item.description == ""

    def test_string_is_stripped(self):
        item = LineItem(item_name="  Product X  ", description="  Description  ")
        assert item.item_name == "Product X"
        assert item.description == "Description"


class TestLineItemCalculatedTotal:
    """Tests for LineItem.calculated_total property."""

    def test_calculated_total(self):
        item = LineItem(quantity=5, unit_price=10.0)
        assert item.calculated_total == 50.0

    def test_calculated_total_with_decimals(self):
        item = LineItem(quantity=3.5, unit_price=7.25)
        assert item.calculated_total == pytest.approx(25.375, rel=1e-6)

    def test_calculated_total_zero_quantity(self):
        item = LineItem(quantity=0, unit_price=100.0)
        assert item.calculated_total == 0.0


class TestLineItemArithmeticError:
    """Tests for LineItem.has_arithmetic_error property."""

    def test_no_error_when_total_matches(self):
        item = LineItem(quantity=5, unit_price=10.0, total_price=50.0)
        assert item.has_arithmetic_error is False

    def test_no_error_within_tolerance(self):
        item = LineItem(quantity=5, unit_price=10.0, total_price=50.009)
        assert item.has_arithmetic_error is False

    def test_error_beyond_tolerance(self):
        item = LineItem(quantity=5, unit_price=10.0, total_price=50.02)
        assert item.has_arithmetic_error is True

    def test_no_error_when_total_is_zero(self):
        item = LineItem(quantity=5, unit_price=10.0, total_price=0.0)
        assert item.has_arithmetic_error is False

    def test_no_error_when_quantity_is_zero(self):
        item = LineItem(quantity=0, unit_price=10.0, total_price=50.0)
        assert item.has_arithmetic_error is False


class TestLineItemDefaults:
    """Tests for LineItem default values."""

    def test_default_values(self):
        item = LineItem()
        assert item.id is None
        assert item.invoice_id is None
        assert item.line_number == 0
        assert item.item_name == ""
        assert item.description == ""
        assert item.hs_code is None
        assert item.unit is None
        assert item.brand is None
        assert item.model is None
        assert item.quantity == 0.0
        assert item.unit_price == 0.0
        assert item.total_price == 0.0
        assert item.row_type == RowType.LINE_ITEM


class TestBankDetails:
    """Tests for BankDetails entity."""

    def test_all_fields_optional(self):
        bank = BankDetails()
        assert bank.beneficiary_name is None
        assert bank.bank_name is None
        assert bank.account_number is None
        assert bank.iban is None
        assert bank.swift is None
        assert bank.bank_address is None

    def test_full_bank_details(self):
        bank = BankDetails(
            beneficiary_name="Test Company",
            bank_name="Test Bank",
            account_number="123456789",
            iban="DZ89370400440532013000",
            swift="TESTDZAL",
            bank_address="123 Bank St",
        )
        assert bank.beneficiary_name == "Test Company"
        assert bank.iban == "DZ89370400440532013000"


class TestInvoiceCoerceNumeric:
    """Tests for Invoice numeric field coercion."""

    def test_none_values_coerce_to_zero(self):
        invoice = Invoice(
            total_amount=None,
            subtotal=None,
            tax_amount=None,
            discount_amount=None,
        )
        assert invoice.total_amount == 0.0
        assert invoice.subtotal == 0.0
        assert invoice.tax_amount == 0.0
        assert invoice.discount_amount == 0.0

    def test_all_numeric_fields_coerce(self):
        invoice = Invoice(
            total_amount="1,234.56",
            subtotal="1,000",
            tax_amount="234.56",
            quality_score="0.95",
            confidence="0.87",
        )
        assert invoice.total_amount == 1234.56
        assert invoice.subtotal == 1000.0
        assert invoice.tax_amount == 234.56
        assert invoice.quality_score == 0.95
        assert invoice.confidence == 0.87


class TestInvoiceItemsCount:
    """Tests for Invoice.items_count property."""

    def test_empty_items(self):
        invoice = Invoice()
        assert invoice.items_count == 0

    def test_only_line_items_counted(self):
        invoice = Invoice(
            items=[
                LineItem(item_name="Item 1", row_type=RowType.LINE_ITEM),
                LineItem(item_name="Item 2", row_type=RowType.LINE_ITEM),
                LineItem(item_name="Header", row_type=RowType.HEADER),
                LineItem(item_name="Subtotal", row_type=RowType.SUBTOTAL),
            ]
        )
        assert invoice.items_count == 2


class TestInvoiceCalculatedTotal:
    """Tests for Invoice.calculated_total property."""

    def test_sum_of_line_items(self):
        invoice = Invoice(
            items=[
                LineItem(total_price=100.0, row_type=RowType.LINE_ITEM),
                LineItem(total_price=200.0, row_type=RowType.LINE_ITEM),
                LineItem(total_price=50.0, row_type=RowType.SUBTOTAL),
            ]
        )
        assert invoice.calculated_total == 300.0

    def test_empty_items_returns_zero(self):
        invoice = Invoice()
        assert invoice.calculated_total == 0.0


class TestInvoiceHasTotalMismatch:
    """Tests for Invoice.has_total_mismatch property."""

    def test_no_mismatch_when_total_matches(self):
        invoice = Invoice(
            total_amount=300.0,
            items=[
                LineItem(total_price=100.0),
                LineItem(total_price=200.0),
            ],
        )
        assert invoice.has_total_mismatch is False

    def test_no_mismatch_within_1_percent(self):
        invoice = Invoice(
            total_amount=300.0,
            items=[
                LineItem(total_price=100.0),
                LineItem(total_price=197.0),  # 297 vs 300 = 1% threshold
            ],
        )
        assert invoice.has_total_mismatch is False

    def test_mismatch_beyond_1_percent(self):
        invoice = Invoice(
            total_amount=300.0,
            items=[
                LineItem(total_price=100.0),
                LineItem(total_price=190.0),  # 290 vs 300 = >1%
            ],
        )
        assert invoice.has_total_mismatch is True

    def test_no_mismatch_when_total_is_zero(self):
        invoice = Invoice(
            total_amount=0.0,
            items=[LineItem(total_price=100.0)],
        )
        assert invoice.has_total_mismatch is False


class TestInvoiceDefaults:
    """Tests for Invoice default values."""

    def test_default_currency(self):
        invoice = Invoice()
        assert invoice.currency == "USD"

    def test_default_parsing_status(self):
        invoice = Invoice()
        assert invoice.parsing_status == ParsingStatus.OK

    def test_default_parser_version(self):
        invoice = Invoice()
        assert invoice.parser_version == "v1.0"

    def test_timestamps_auto_generated(self):
        before = datetime.utcnow()
        invoice = Invoice()
        after = datetime.utcnow()
        assert before <= invoice.created_at <= after
        assert before <= invoice.updated_at <= after


class TestAuditIssue:
    """Tests for AuditIssue entity."""

    def test_required_fields(self):
        issue = AuditIssue(
            code="TOTAL_MISMATCH",
            field="total_amount",
            severity="error",
            category="arithmetic",
            message="Total mismatch",
        )
        assert issue.code == "TOTAL_MISMATCH"
        assert issue.field == "total_amount"
        assert issue.level == "error"  # level is a property alias for severity.value
        assert issue.category == "arithmetic"
        assert issue.message == "Total mismatch"

    def test_optional_fields(self):
        issue = AuditIssue(
            code="SLIGHT_VARIANCE",
            field="total",
            severity="warning",
            category="arithmetic",
            message="Slight variance",
            expected="100.00",
            actual="99.95",
        )
        assert issue.expected == "100.00"
        assert issue.actual == "99.95"


class TestArithmeticCheck:
    """Tests for ArithmeticCheck entity."""

    def test_default_values(self):
        check = ArithmeticCheck()
        assert check.check_type == ""
        assert check.field == ""
        assert check.expected == 0.0
        assert check.actual == 0.0
        assert check.difference == 0.0
        assert check.passed is True
        assert check.description == ""
        assert check.line_number is None

    def test_with_data(self):
        check = ArithmeticCheck(
            check_type="line_total",
            field="items[0].total_price",
            expected=100.0,
            actual=100.0,
            difference=0.0,
            passed=True,
            description="Line total check",
            line_number=1,
        )
        assert check.check_type == "line_total"
        assert check.expected == 100.0
        assert check.line_number == 1


class TestAuditResult:
    """Tests for AuditResult entity."""

    def test_required_fields(self):
        result = AuditResult(invoice_id=1)
        assert result.invoice_id == 1
        assert result.success is True
        assert result.audit_type == "llm"
        assert result.status == AuditStatus.HOLD

    def test_trace_id_auto_generated(self):
        result = AuditResult(invoice_id=1)
        assert result.trace_id is not None
        assert len(result.trace_id) == 36  # UUID format

    def test_errors_count_property(self):
        result = AuditResult(
            invoice_id=1,
            issues=[
                AuditIssue(code="ERR1", field="a", severity="error", category="c", message="m"),
                AuditIssue(code="WARN1", field="b", severity="warning", category="c", message="m"),
                AuditIssue(code="ERR2", field="c", severity="error", category="c", message="m"),
            ],
        )
        assert result.errors_count == 2

    def test_warnings_count_property(self):
        result = AuditResult(
            invoice_id=1,
            issues=[
                AuditIssue(code="WARN1", field="a", severity="warning", category="c", message="m"),
                AuditIssue(code="WARN2", field="b", severity="warning", category="c", message="m"),
                AuditIssue(code="INFO1", field="c", severity="info", category="c", message="m"),
            ],
        )
        assert result.warnings_count == 2

    def test_to_dict(self):
        result = AuditResult(
            invoice_id=1,
            status=AuditStatus.PASS,
            success=True,
        )
        data = result.to_dict()
        assert isinstance(data, dict)
        assert data["invoice_id"] == 1
        assert data["status"] == "PASS"
        assert data["success"] is True

    def test_9_sections_present(self):
        """Verify all 9 audit report sections exist."""
        result = AuditResult(invoice_id=1)
        assert hasattr(result, "document_intake")
        assert hasattr(result, "proforma_summary")
        assert hasattr(result, "items_table")
        assert hasattr(result, "arithmetic_check")
        assert hasattr(result, "amount_words_check")
        assert hasattr(result, "bank_details_check")
        assert hasattr(result, "commercial_terms_suggestions")
        assert hasattr(result, "contract_summary")
        assert hasattr(result, "final_verdict")


class TestAuditFindingAlias:
    """Test AuditFinding backward compatibility alias."""

    def test_alias_exists(self):
        from src.core.entities.invoice import AuditFinding

        issue = AuditFinding(
            code="TEST_CODE",
            field="test",
            severity="error",
            category="test",
            message="test",
        )
        assert isinstance(issue, AuditIssue)
