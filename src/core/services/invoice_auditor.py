"""
Invoice auditor service.

Layer-pure service combining rule-based validation with optional LLM analysis.
NO infrastructure imports - depends only on core entities, interfaces, exceptions.
"""

import json
import re
from datetime import datetime, timedelta

from src.core.entities.invoice import (
    ArithmeticCheck,
    AuditIssue,
    AuditResult,
    Invoice,
    IssueSeverity,
    RowType,
)
from src.core.interfaces import IInvoiceStore, ILLMProvider
from src.core.interfaces.price_history import IPriceHistoryStore


class InvoiceAuditorService:
    """
    Invoice auditing with rule-based and optional LLM analysis.

    Performs:
    - Mathematical validation (fast, always runs)
    - Format validation (fast, always runs)
    - Price anomaly detection via historical data (fast, optional)
    - Semantic analysis via LLM (slow, optional, graceful degradation)

    Required interfaces for DI:
    - ILLMProvider: Optional LLM for semantic analysis
    - IInvoiceStore: Optional invoice/audit persistence
    - IPriceHistoryStore: Optional price history for anomaly detection
    """

    # Default price deviation threshold (20%)
    DEFAULT_PRICE_ANOMALY_THRESHOLD = 0.20
    # Default cross-invoice duplicate detection window (days)
    DEFAULT_DUPLICATE_WINDOW_DAYS = 30

    def __init__(
        self,
        llm_provider: ILLMProvider | None = None,
        invoice_store: IInvoiceStore | None = None,
        price_history_store: IPriceHistoryStore | None = None,
        price_anomaly_threshold: float | None = None,
        duplicate_window_days: int | None = None,
    ):
        """
        Initialize auditor service with injected dependencies.

        Args:
            llm_provider: Optional LLM provider for semantic analysis
            invoice_store: Optional store for persisting audit results
            price_history_store: Optional store for price anomaly detection
            price_anomaly_threshold: Deviation threshold (0.0–1.0). Default 0.20 (20%).
            duplicate_window_days: Window for cross-invoice duplicate detection. Default 30.
        """
        self._llm = llm_provider
        self._invoice_store = invoice_store
        self._price_store = price_history_store
        self._price_threshold = (
            price_anomaly_threshold
            if price_anomaly_threshold is not None
            else self.DEFAULT_PRICE_ANOMALY_THRESHOLD
        )
        self._duplicate_window = (
            duplicate_window_days
            if duplicate_window_days is not None
            else self.DEFAULT_DUPLICATE_WINDOW_DAYS
        )

    async def audit_invoice(
        self,
        invoice: Invoice,
        use_llm: bool = True,
        save_result: bool = True,
    ) -> AuditResult:
        """
        Perform complete invoice audit.

        Rule-based checks always run first (fast).
        LLM analysis runs second if enabled (slow, graceful degradation).

        Args:
            invoice: Invoice to audit
            use_llm: Whether to attempt LLM semantic analysis
            save_result: Whether to persist audit result

        Returns:
            AuditResult with all findings
        """
        start_time = datetime.now()
        issues: list[AuditIssue] = []
        arithmetic_checks: list[ArithmeticCheck] = []

        # === Rule-based checks (always run, fast) ===
        issues.extend(self._check_required_fields(invoice))
        math_issues, math_checks = self._check_math(invoice)
        issues.extend(math_issues)
        arithmetic_checks.extend(math_checks)
        issues.extend(self._check_duplicates(invoice))
        issues.extend(self._check_dates(invoice))
        issues.extend(self._check_line_items(invoice))

        # === Price anomaly + cross-invoice duplicate checks (optional) ===
        if self._price_store:
            try:
                price_issues = await self._check_price_anomalies(invoice)
                issues.extend(price_issues)
            except Exception as e:
                issues.append(
                    AuditIssue(
                        code="PRICE_CHECK_ERROR",
                        severity=IssueSeverity.INFO,
                        message=f"Price anomaly check skipped: {e}",
                        category="price_anomaly",
                    )
                )
            try:
                dup_issues = await self._check_cross_invoice_duplicates(invoice)
                issues.extend(dup_issues)
            except Exception as e:
                issues.append(
                    AuditIssue(
                        code="DUPLICATE_CHECK_ERROR",
                        severity=IssueSeverity.INFO,
                        message=f"Cross-invoice duplicate check skipped: {e}",
                        category="cross_invoice_duplicate",
                    )
                )

        # === LLM semantic analysis (optional, graceful degradation) ===
        llm_used = False
        if use_llm and self._llm:
            try:
                if self._llm.is_available():
                    llm_issues = await self._llm_analysis(invoice)
                    issues.extend(llm_issues)
                    llm_used = True
            except Exception as e:
                # Graceful degradation - add warning but continue
                issues.append(
                    AuditIssue(
                        code="LLM_UNAVAILABLE",
                        severity=IssueSeverity.WARNING,
                        message=f"LLM analysis skipped: {str(e)}",
                        category="llm_error",
                    )
                )

        # Calculate audit metrics
        error_count = sum(1 for i in issues if i.severity == IssueSeverity.ERROR)
        warning_count = sum(1 for i in issues if i.severity == IssueSeverity.WARNING)
        passed = error_count == 0

        # Confidence based on findings
        if not issues:
            confidence = 1.0
        else:
            confidence = max(0.0, 1.0 - (error_count * 0.15 + warning_count * 0.05))

        duration_ms = (datetime.now() - start_time).total_seconds() * 1000

        result = AuditResult(
            invoice_id=invoice.id or 0,
            passed=passed,
            confidence=confidence,
            issues=issues,
            arithmetic_checks=arithmetic_checks,
            audited_at=datetime.now(),
            metadata={
                "llm_used": llm_used,
                "duration_ms": round(duration_ms, 2),
                "error_count": error_count,
                "warning_count": warning_count,
            },
        )

        # Optionally persist
        if save_result and self._invoice_store and invoice.id:
            result = await self._invoice_store.create_audit_result(result)

        return result

    async def audit_rules_only(self, invoice: Invoice) -> AuditResult:
        """
        Perform rule-based audit only (no LLM).

        Fast audit suitable for batch processing.
        """
        return await self.audit_invoice(invoice, use_llm=False, save_result=False)

    def _check_required_fields(self, invoice: Invoice) -> list[AuditIssue]:
        """Check for missing required fields."""
        issues = []

        required_fields = [
            ("invoice_no", "Invoice number"),
            ("seller_name", "Seller name"),
            ("invoice_date", "Invoice date"),
        ]

        for field, label in required_fields:
            value = getattr(invoice, field, None)
            if not value:
                issues.append(
                    AuditIssue(
                        code="MISSING_REQUIRED_FIELD",
                        severity=IssueSeverity.ERROR,
                        message=f"Missing required field: {label}",
                        category="missing_field",
                        field=field,
                    )
                )

        if not invoice.items:
            issues.append(
                AuditIssue(
                    code="NO_LINE_ITEMS",
                    severity=IssueSeverity.ERROR,
                    message="No line items found",
                    category="missing_field",
                    field="items",
                )
            )

        return issues

    def _check_math(
        self, invoice: Invoice
    ) -> tuple[list[AuditIssue], list[ArithmeticCheck]]:
        """Verify mathematical calculations."""
        issues = []
        checks = []

        # Check line item totals
        for i, item in enumerate(invoice.items):
            expected = round(item.quantity * item.unit_price, 2)
            actual = item.total_price
            passed = abs(actual - expected) <= 0.01

            checks.append(
                ArithmeticCheck(
                    check_type="line_total",
                    expected=expected,
                    actual=actual,
                    passed=passed,
                    field=f"items[{i}].total_price",
                )
            )

            if not passed:
                issues.append(
                    AuditIssue(
                        code="LINE_TOTAL_MISMATCH",
                        severity=IssueSeverity.ERROR,
                        message=f"Line {i + 1} total mismatch: {actual} != {expected}",
                        category="math_error",
                        field=f"items[{i}].total_price",
                        expected=str(expected),
                        actual=str(actual),
                    )
                )

        # Check document total
        if invoice.total_amount and invoice.items:
            calculated = sum(item.total_price for item in invoice.items)
            diff = abs(invoice.total_amount - calculated)
            passed = diff <= 0.02

            checks.append(
                ArithmeticCheck(
                    check_type="invoice_total",
                    expected=calculated,
                    actual=invoice.total_amount,
                    passed=passed,
                    field="total_amount",
                )
            )

            if not passed:
                severity = IssueSeverity.ERROR if diff > 1.0 else IssueSeverity.WARNING
                issues.append(
                    AuditIssue(
                        code="TOTAL_MISMATCH",
                        severity=severity,
                        message=f"Invoice total mismatch: declared {invoice.total_amount} != calculated {calculated:.2f}",
                        category="total_mismatch",
                        field="total_amount",
                        expected=str(round(calculated, 2)),
                        actual=str(invoice.total_amount),
                    )
                )

        # Check tax calculations if present
        if invoice.tax_amount and invoice.subtotal:
            expected_total = invoice.subtotal + invoice.tax_amount
            if invoice.total_amount:
                diff = abs(invoice.total_amount - expected_total)
                passed = diff <= 0.02

                checks.append(
                    ArithmeticCheck(
                        check_type="tax_total",
                        expected=expected_total,
                        actual=invoice.total_amount,
                        passed=passed,
                        field="total_amount",
                    )
                )

                if not passed:
                    issues.append(
                        AuditIssue(
                            code="TAX_CALCULATION_ERROR",
                            severity=IssueSeverity.WARNING,
                            message="Total doesn't match subtotal + tax",
                            category="tax_calculation",
                            field="tax_amount",
                        )
                    )

        return issues, checks

    def _check_duplicates(self, invoice: Invoice) -> list[AuditIssue]:
        """Check for duplicate line items."""
        issues = []
        seen: dict[tuple[str, float], int] = {}

        for i, item in enumerate(invoice.items):
            key = (item.item_name.lower().strip(), item.unit_price)

            if key in seen:
                issues.append(
                    AuditIssue(
                        code="POSSIBLE_DUPLICATE",
                        severity=IssueSeverity.WARNING,
                        message=f"Possible duplicate: line {seen[key] + 1} and {i + 1}",
                        category="duplicate",
                        field=f"items[{i}]",
                    )
                )
            else:
                seen[key] = i

        return issues

    def _check_dates(self, invoice: Invoice) -> list[AuditIssue]:
        """Validate date fields."""
        issues = []
        today = datetime.now().date()

        if invoice.invoice_date:
            # Future date check
            if invoice.invoice_date > today:
                issues.append(
                    AuditIssue(
                        code="FUTURE_DATE",
                        severity=IssueSeverity.WARNING,
                        message=f"Invoice date is in the future: {invoice.invoice_date}",
                        category="date_error",
                        field="invoice_date",
                    )
                )

            # Too old check (> 1 year)
            one_year_ago = today - timedelta(days=365)
            if invoice.invoice_date < one_year_ago:
                issues.append(
                    AuditIssue(
                        code="OLD_DATE",
                        severity=IssueSeverity.WARNING,
                        message=f"Invoice date is over 1 year old: {invoice.invoice_date}",
                        category="date_warning",
                        field="invoice_date",
                    )
                )

        # Due date before invoice date
        if invoice.due_date and invoice.invoice_date:
            if invoice.due_date < invoice.invoice_date:
                issues.append(
                    AuditIssue(
                        code="DUE_BEFORE_INVOICE",
                        severity=IssueSeverity.ERROR,
                        message="Due date is before invoice date",
                        category="date_error",
                        field="due_date",
                    )
                )

        return issues

    def _check_line_items(self, invoice: Invoice) -> list[AuditIssue]:
        """Validate individual line items."""
        issues = []

        for i, item in enumerate(invoice.items):
            # Negative values
            if item.quantity < 0:
                issues.append(
                    AuditIssue(
                        code="NEGATIVE_QUANTITY",
                        severity=IssueSeverity.WARNING,
                        message=f"Line {i + 1}: Negative quantity",
                        category="value_error",
                        field=f"items[{i}].quantity",
                    )
                )

            if item.unit_price < 0:
                issues.append(
                    AuditIssue(
                        code="NEGATIVE_PRICE",
                        severity=IssueSeverity.WARNING,
                        message=f"Line {i + 1}: Negative unit price",
                        category="value_error",
                        field=f"items[{i}].unit_price",
                    )
                )

            # Zero quantity
            if item.quantity == 0:
                issues.append(
                    AuditIssue(
                        code="ZERO_QUANTITY",
                        severity=IssueSeverity.WARNING,
                        message=f"Line {i + 1}: Zero quantity",
                        category="value_error",
                        field=f"items[{i}].quantity",
                    )
                )

            # Unusually high values
            if item.unit_price > 1_000_000:
                issues.append(
                    AuditIssue(
                        code="HIGH_UNIT_PRICE",
                        severity=IssueSeverity.WARNING,
                        message=f"Line {i + 1}: Unusually high unit price: {item.unit_price}",
                        category="value_warning",
                        field=f"items[{i}].unit_price",
                    )
                )

            # Empty or too short description
            if not item.item_name or len(item.item_name.strip()) < 3:
                issues.append(
                    AuditIssue(
                        code="MISSING_DESCRIPTION",
                        severity=IssueSeverity.WARNING,
                        message=f"Line {i + 1}: Missing or too short description",
                        category="missing_field",
                        field=f"items[{i}].item_name",
                    )
                )

        return issues

    async def _check_price_anomalies(self, invoice: Invoice) -> list[AuditIssue]:
        """
        Check for price anomalies based on historical price data.

        Compares each line item's unit_price against the historical average
        from v_item_price_stats. Flags items where deviation exceeds the
        configured threshold.

        Returns list of AuditIssue for anomalous prices.
        """
        if not self._price_store:
            return []

        issues: list[AuditIssue] = []

        for i, item in enumerate(invoice.items):
            if item.row_type != RowType.LINE_ITEM:
                continue
            if item.unit_price <= 0 or not item.item_name.strip():
                continue

            # Normalize item name for stats lookup
            normalized = item.item_name.strip().lower()

            # Query price stats — try item+seller first, fallback to item only
            stats = await self._price_store.get_price_stats(
                item_name=normalized,
                seller=invoice.seller_name,
            )
            if not stats:
                stats = await self._price_store.get_price_stats(
                    item_name=normalized,
                )
            if not stats:
                continue

            stat = stats[0]
            avg_price = stat.get("avg_price", 0)
            min_price = stat.get("min_price", 0)
            max_price = stat.get("max_price", 0)
            occurrence_count = stat.get("occurrence_count", 0)

            # Need at least 2 historical data points for meaningful comparison
            if occurrence_count < 2 or avg_price <= 0:
                continue

            current_price = item.unit_price
            deviation = abs(current_price - avg_price) / avg_price

            if deviation > self._price_threshold:
                direction = "above" if current_price > avg_price else "below"
                pct = round(deviation * 100, 1)

                issues.append(
                    AuditIssue(
                        code="PRICE_ANOMALY",
                        severity=IssueSeverity.WARNING,
                        message=(
                            f"Line {i + 1} '{item.item_name}': unit price "
                            f"{current_price:.2f} is {pct}% {direction} "
                            f"historical average {avg_price:.2f} "
                            f"(range {min_price:.2f}–{max_price:.2f}, "
                            f"{occurrence_count} records)"
                        ),
                        category="price_anomaly",
                        field=f"items[{i}].unit_price",
                        expected=str(round(avg_price, 2)),
                        actual=str(round(current_price, 2)),
                    )
                )

        return issues

    async def _check_cross_invoice_duplicates(self, invoice: Invoice) -> list[AuditIssue]:
        """
        Check for cross-invoice duplicates.

        Warns when the same item+seller combination appears in prior invoices
        within the configured window (default 30 days).

        Returns list of AuditIssue for duplicate entries.
        """
        if not self._price_store:
            return []
        if not invoice.invoice_date:
            return []

        issues: list[AuditIssue] = []
        window_start = invoice.invoice_date - timedelta(days=self._duplicate_window)
        # Exclude the invoice date itself to avoid matching the current invoice
        window_end = invoice.invoice_date - timedelta(days=1)

        if window_start > window_end:
            return []

        date_from = window_start.isoformat()
        date_to = window_end.isoformat()

        for i, item in enumerate(invoice.items):
            if item.row_type != RowType.LINE_ITEM:
                continue
            if not item.item_name.strip():
                continue

            normalized = item.item_name.strip().lower()
            seller = invoice.seller_name or ""

            if not seller.strip():
                continue

            history = await self._price_store.get_price_history(
                item_name=normalized,
                seller=seller,
                date_from=date_from,
                date_to=date_to,
                limit=10,
            )

            # Filter for exact normalized name match (get_price_history uses LIKE)
            exact_matches = [
                h for h in history
                if h.get("item_name", "").strip().lower() == normalized
            ]

            if exact_matches:
                dates = sorted({h.get("invoice_date", "?") for h in exact_matches})
                issues.append(
                    AuditIssue(
                        code="CROSS_INVOICE_DUPLICATE",
                        severity=IssueSeverity.WARNING,
                        message=(
                            f"Line {i + 1} '{item.item_name}': same item+seller "
                            f"appeared on {len(exact_matches)} prior record(s) "
                            f"within {self._duplicate_window} days "
                            f"(dates: {', '.join(dates)})"
                        ),
                        category="cross_invoice_duplicate",
                        field=f"items[{i}]",
                    )
                )

        return issues

    async def _llm_analysis(self, invoice: Invoice) -> list[AuditIssue]:
        """Perform LLM-powered semantic analysis."""
        if not self._llm:
            return []

        issues = []
        summary = self._build_invoice_summary(invoice)

        prompt = f"""Analyze this invoice for potential issues:

{summary}

Check for:
1. Suspicious patterns (unusual quantities, prices)
2. Possible errors in descriptions
3. Missing information that should be present
4. Any red flags or anomalies

Respond ONLY with a JSON array of findings. Each finding should have:
- "issue": brief description of the problem
- "severity": "error" or "warning"
- "line": line number if applicable (null otherwise)

If no issues found, respond with empty array: []

JSON response:"""

        try:
            llm_response = await self._llm.generate(
                prompt,
                max_tokens=500,
                temperature=0.1,
            )
            response = llm_response.text

            # Parse LLM response
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                llm_issues = json.loads(json_match.group())

                for item in llm_issues:
                    if isinstance(item, dict) and "issue" in item:
                        severity = (
                            IssueSeverity.ERROR
                            if item.get("severity") == "error"
                            else IssueSeverity.WARNING
                        )
                        issues.append(
                            AuditIssue(
                                code="LLM_FINDING",
                                severity=severity,
                                message=item["issue"],
                                category="llm_analysis",
                                field=f"items[{item['line'] - 1}]"
                                if item.get("line")
                                else "",
                            )
                        )

        except json.JSONDecodeError:
            pass  # LLM didn't return valid JSON, skip
        except Exception:
            # Re-raise so outer handler can add warning about LLM failure
            raise

        return issues

    def _build_invoice_summary(self, invoice: Invoice) -> str:
        """Build text summary of invoice for LLM."""
        lines = [
            f"Invoice #: {invoice.invoice_no or 'N/A'}",
            f"Seller: {invoice.seller_name or 'N/A'}",
            f"Date: {invoice.invoice_date or 'N/A'}",
            f"Total: {invoice.total_amount or invoice.calculated_total}",
            "",
            "Line Items:",
        ]

        for i, item in enumerate(invoice.items, 1):
            lines.append(
                f"{i}. {item.item_name} | "
                f"Qty: {item.quantity} | "
                f"Unit: {item.unit_price} | "
                f"Total: {item.total_price}"
            )

        return "\n".join(lines)

    async def get_audit_history(
        self,
        invoice_id: int,
        limit: int = 10,
    ) -> list[AuditResult]:
        """Get audit history for an invoice."""
        if not self._invoice_store:
            return []

        return await self._invoice_store.list_audit_results(
            invoice_id=invoice_id,
            limit=limit,
        )
