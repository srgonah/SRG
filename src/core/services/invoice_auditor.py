"""
Invoice auditor service.

Combines rule-based validation with LLM-powered analysis.
"""

from datetime import datetime

from src.config import get_logger, get_settings
from src.core.entities.invoice import AuditFinding, AuditResult, Invoice
from src.infrastructure.llm import ILLMProvider, get_llm_provider

logger = get_logger(__name__)


class InvoiceAuditorService:
    """
    Invoice auditing with rule-based and LLM analysis.

    Performs:
    - Mathematical validation
    - Format validation
    - Semantic analysis via LLM
    """

    def __init__(self, llm_provider: ILLMProvider | None = None):
        """
        Initialize auditor service.

        Args:
            llm_provider: Optional custom LLM provider
        """
        self._llm = llm_provider
        self._settings = get_settings()

    def _get_llm(self) -> ILLMProvider:
        """Lazy load LLM provider."""
        if self._llm is None:
            self._llm = get_llm_provider()
        return self._llm

    async def audit_invoice(
        self,
        invoice: Invoice,
        use_llm: bool = True,
    ) -> AuditResult:
        """
        Perform complete invoice audit.

        Args:
            invoice: Invoice to audit
            use_llm: Whether to use LLM for semantic analysis

        Returns:
            AuditResult with all findings
        """
        logger.info(
            "starting_audit",
            invoice_id=invoice.id,
            invoice_number=invoice.invoice_number,
            use_llm=use_llm,
        )

        findings = []
        start_time = datetime.now()

        # Rule-based checks
        findings.extend(self._check_required_fields(invoice))
        findings.extend(self._check_math(invoice))
        findings.extend(self._check_duplicates(invoice))
        findings.extend(self._check_dates(invoice))
        findings.extend(self._check_line_items(invoice))

        # LLM semantic analysis
        if use_llm:
            try:
                llm_findings = await self._llm_analysis(invoice)
                findings.extend(llm_findings)
            except Exception as e:
                logger.warning("llm_audit_failed", error=str(e))
                findings.append(
                    AuditFinding(
                        category="llm_error",
                        severity="warning",
                        message=f"LLM analysis failed: {str(e)}",
                    )
                )

        # Calculate scores
        errors = sum(1 for f in findings if f.severity == "error")
        warnings = sum(1 for f in findings if f.severity == "warning")
        passed = errors == 0

        # Confidence based on finding severity
        if not findings:
            confidence = 1.0
        else:
            confidence = max(0.0, 1.0 - (errors * 0.15 + warnings * 0.05))

        result = AuditResult(
            invoice_id=invoice.id,
            passed=passed,
            confidence=confidence,
            findings=findings,
            audited_at=datetime.now(),
        )

        duration = (datetime.now() - start_time).total_seconds()

        logger.info(
            "audit_complete",
            invoice_id=invoice.id,
            passed=passed,
            errors=errors,
            warnings=warnings,
            confidence=confidence,
            duration_sec=duration,
        )

        return result

    def _check_required_fields(self, invoice: Invoice) -> list[AuditFinding]:
        """Check for missing required fields."""
        findings = []

        required = [
            ("invoice_number", "Invoice number"),
            ("vendor_name", "Vendor name"),
            ("invoice_date", "Invoice date"),
        ]

        for field, label in required:
            value = getattr(invoice, field, None)
            if not value:
                findings.append(
                    AuditFinding(
                        category="missing_field",
                        severity="error",
                        message=f"Missing required field: {label}",
                        field=field,
                    )
                )

        if not invoice.line_items:
            findings.append(
                AuditFinding(
                    category="missing_field",
                    severity="error",
                    message="No line items found",
                    field="line_items",
                )
            )

        return findings

    def _check_math(self, invoice: Invoice) -> list[AuditFinding]:
        """Verify mathematical calculations."""
        findings = []

        # Check line item totals
        for i, item in enumerate(invoice.line_items):
            expected = round(item.quantity * item.unit_price, 2)
            actual = item.total_price

            if abs(actual - expected) > 0.01:
                findings.append(
                    AuditFinding(
                        category="math_error",
                        severity="error",
                        message=f"Line {i + 1} total mismatch: {actual} != {expected}",
                        field=f"line_items[{i}].total_price",
                        expected=str(expected),
                        actual=str(actual),
                    )
                )

        # Check document total
        if invoice.total_amount:
            calculated = invoice.calculated_total
            declared = invoice.total_amount

            # Allow small rounding difference
            diff = abs(declared - calculated)
            if diff > 0.02:
                severity = "error" if diff > 1.0 else "warning"
                findings.append(
                    AuditFinding(
                        category="total_mismatch",
                        severity=severity,
                        message=f"Total mismatch: declared {declared} != calculated {calculated}",
                        field="total_amount",
                        expected=str(calculated),
                        actual=str(declared),
                    )
                )

        # Check tax calculations if present
        if invoice.tax_amount and invoice.subtotal:
            expected_total = invoice.subtotal + invoice.tax_amount
            if invoice.total_amount:
                if abs(invoice.total_amount - expected_total) > 0.02:
                    findings.append(
                        AuditFinding(
                            category="tax_calculation",
                            severity="warning",
                            message="Total doesn't match subtotal + tax",
                            field="tax_amount",
                        )
                    )

        return findings

    def _check_duplicates(self, invoice: Invoice) -> list[AuditFinding]:
        """Check for duplicate line items."""
        findings = []

        seen = {}
        for i, item in enumerate(invoice.line_items):
            key = (item.description.lower().strip(), item.unit_price)

            if key in seen:
                findings.append(
                    AuditFinding(
                        category="duplicate",
                        severity="warning",
                        message=f"Possible duplicate: line {seen[key] + 1} and {i + 1}",
                        field=f"line_items[{i}]",
                    )
                )
            else:
                seen[key] = i

        return findings

    def _check_dates(self, invoice: Invoice) -> list[AuditFinding]:
        """Validate date fields."""
        findings = []
        today = datetime.now().date()

        if invoice.invoice_date:
            # Check if date is in the future
            if invoice.invoice_date > today:
                findings.append(
                    AuditFinding(
                        category="date_error",
                        severity="warning",
                        message=f"Invoice date is in the future: {invoice.invoice_date}",
                        field="invoice_date",
                    )
                )

            # Check if date is too old (> 1 year)
            from datetime import timedelta

            if invoice.invoice_date < (today - timedelta(days=365)):
                findings.append(
                    AuditFinding(
                        category="date_warning",
                        severity="warning",
                        message=f"Invoice date is over 1 year old: {invoice.invoice_date}",
                        field="invoice_date",
                    )
                )

        if invoice.due_date and invoice.invoice_date:
            if invoice.due_date < invoice.invoice_date:
                findings.append(
                    AuditFinding(
                        category="date_error",
                        severity="error",
                        message="Due date is before invoice date",
                        field="due_date",
                    )
                )

        return findings

    def _check_line_items(self, invoice: Invoice) -> list[AuditFinding]:
        """Validate individual line items."""
        findings = []

        for i, item in enumerate(invoice.line_items):
            # Negative values
            if item.quantity < 0:
                findings.append(
                    AuditFinding(
                        category="value_error",
                        severity="warning",
                        message=f"Line {i + 1}: Negative quantity",
                        field=f"line_items[{i}].quantity",
                    )
                )

            if item.unit_price < 0:
                findings.append(
                    AuditFinding(
                        category="value_error",
                        severity="warning",
                        message=f"Line {i + 1}: Negative unit price",
                        field=f"line_items[{i}].unit_price",
                    )
                )

            # Zero values
            if item.quantity == 0:
                findings.append(
                    AuditFinding(
                        category="value_error",
                        severity="warning",
                        message=f"Line {i + 1}: Zero quantity",
                        field=f"line_items[{i}].quantity",
                    )
                )

            # Unusually high values
            if item.unit_price > 1000000:
                findings.append(
                    AuditFinding(
                        category="value_warning",
                        severity="warning",
                        message=f"Line {i + 1}: Unusually high unit price: {item.unit_price}",
                        field=f"line_items[{i}].unit_price",
                    )
                )

            # Empty description
            if not item.description or len(item.description.strip()) < 3:
                findings.append(
                    AuditFinding(
                        category="missing_field",
                        severity="warning",
                        message=f"Line {i + 1}: Missing or too short description",
                        field=f"line_items[{i}].description",
                    )
                )

        return findings

    async def _llm_analysis(self, invoice: Invoice) -> list[AuditFinding]:
        """Perform LLM-powered semantic analysis."""
        findings = []

        # Build invoice summary for LLM
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
            llm = self._get_llm()
            response = await llm.generate(
                prompt,
                max_tokens=500,
                temperature=0.1,
            )

            # Parse LLM response
            import json
            import re

            # Extract JSON from response
            json_match = re.search(r"\[.*\]", response, re.DOTALL)
            if json_match:
                issues = json.loads(json_match.group())

                for issue in issues:
                    if isinstance(issue, dict) and "issue" in issue:
                        findings.append(
                            AuditFinding(
                                category="llm_analysis",
                                severity=issue.get("severity", "warning"),
                                message=issue["issue"],
                                field=f"line_items[{issue['line'] - 1}]"
                                if issue.get("line")
                                else None,
                            )
                        )

        except json.JSONDecodeError:
            logger.debug("llm_response_not_json", response=response[:200])
        except Exception as e:
            logger.warning("llm_analysis_error", error=str(e))

        return findings

    def _build_invoice_summary(self, invoice: Invoice) -> str:
        """Build text summary of invoice for LLM."""
        lines = [
            f"Invoice #: {invoice.invoice_number or 'N/A'}",
            f"Vendor: {invoice.vendor_name or 'N/A'}",
            f"Date: {invoice.invoice_date or 'N/A'}",
            f"Total: {invoice.total_amount or invoice.calculated_total}",
            "",
            "Line Items:",
        ]

        for i, item in enumerate(invoice.line_items, 1):
            lines.append(
                f"{i}. {item.description} | "
                f"Qty: {item.quantity} | "
                f"Unit: {item.unit_price} | "
                f"Total: {item.total_price}"
            )

        return "\n".join(lines)


# Singleton
_auditor_service: InvoiceAuditorService | None = None


def get_invoice_auditor_service() -> InvoiceAuditorService:
    """Get or create invoice auditor service singleton."""
    global _auditor_service
    if _auditor_service is None:
        _auditor_service = InvoiceAuditorService()
    return _auditor_service
