"""
Fpdf2 implementation of proforma PDF rendering.

Builds a structured PDF with invoice and audit information.
"""

from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.core.entities.invoice import AuditResult, Invoice, RowType
from src.core.services.proforma_pdf_service import IProformaPdfRenderer


class Fpdf2ProformaRenderer(IProformaPdfRenderer):
    """Renders proforma PDFs using fpdf2."""

    def render(self, invoice: Invoice, audit: AuditResult) -> bytes:
        """Render invoice and audit data into PDF bytes."""
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        self._render_header(pdf, invoice)
        self._render_proforma_summary(pdf, invoice, audit)
        self._render_items_table(pdf, invoice, audit)
        self._render_totals(pdf, invoice)
        self._render_bank_details(pdf, invoice, audit)
        self._render_footer(pdf, audit)

        return bytes(pdf.output())

    def _render_header(self, pdf: FPDF, invoice: Invoice) -> None:
        """Render PDF header with company info and invoice number."""
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(
            0, 10, "PROFORMA INVOICE", align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(5)

        pdf.set_font("Helvetica", "", 10)
        if invoice.invoice_no:
            pdf.cell(0, 6, f"Invoice No: {invoice.invoice_no}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.invoice_date:
            pdf.cell(0, 6, f"Date: {invoice.invoice_date}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.seller_name:
            pdf.cell(0, 6, f"Seller: {invoice.seller_name}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.buyer_name:
            pdf.cell(0, 6, f"Buyer: {invoice.buyer_name}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.currency:
            pdf.cell(0, 6, f"Currency: {invoice.currency}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(5)

    def _render_proforma_summary(
        self, pdf: FPDF, invoice: Invoice, audit: AuditResult
    ) -> None:
        """Render proforma summary section from audit data."""
        if not audit.proforma_summary:
            return

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)

        summary = audit.proforma_summary
        for key, value in summary.items():
            text = f"{key}: {value}"
            pdf.cell(0, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    def _render_items_table(
        self, pdf: FPDF, invoice: Invoice, audit: AuditResult
    ) -> None:
        """Render items table."""
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Items", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Table header
        col_widths = [10, 60, 25, 30, 30, 35]
        headers = ["#", "Description", "Qty", "Unit", "Unit Price", "Total"]

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(220, 220, 220)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 7, header, border=1, fill=True)
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", "", 8)
        items = [item for item in invoice.items if item.row_type == RowType.LINE_ITEM]
        for idx, item in enumerate(items, 1):
            desc = (item.description or item.item_name)[:40]
            unit = (item.unit or "")[:10]
            pdf.cell(col_widths[0], 6, str(idx), border=1)
            pdf.cell(col_widths[1], 6, desc, border=1)
            pdf.cell(col_widths[2], 6, f"{item.quantity:g}", border=1, align="R")
            pdf.cell(col_widths[3], 6, unit, border=1)
            pdf.cell(col_widths[4], 6, f"{item.unit_price:,.2f}", border=1, align="R")
            pdf.cell(col_widths[5], 6, f"{item.total_price:,.2f}", border=1, align="R")
            pdf.ln()

        pdf.ln(3)

    def _render_totals(self, pdf: FPDF, invoice: Invoice) -> None:
        """Render totals section."""
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, "Totals", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)

        if invoice.subtotal:
            pdf.cell(100, 6, "Subtotal:", align="R")
            pdf.cell(0, 6, f"{invoice.subtotal:,.2f} {invoice.currency}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.tax_amount:
            pdf.cell(100, 6, "Tax:", align="R")
            pdf.cell(0, 6, f"{invoice.tax_amount:,.2f} {invoice.currency}",
                     new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        if invoice.discount_amount:
            pdf.cell(100, 6, "Discount:", align="R")
            pdf.cell(
                0, 6, f"-{invoice.discount_amount:,.2f} {invoice.currency}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(100, 8, "Total:", align="R")
        pdf.cell(0, 8, f"{invoice.total_amount:,.2f} {invoice.currency}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    def _render_bank_details(
        self, pdf: FPDF, invoice: Invoice, audit: AuditResult
    ) -> None:
        """Render bank details section."""
        bank = invoice.bank_details
        bank_check = audit.bank_details_check

        if not bank and not bank_check:
            return

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Bank Details", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 9)

        if bank:
            if bank.beneficiary_name:
                pdf.cell(0, 5, f"Beneficiary: {bank.beneficiary_name}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if bank.bank_name:
                pdf.cell(0, 5, f"Bank: {bank.bank_name}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if bank.account_number:
                pdf.cell(0, 5, f"Account: {bank.account_number}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if bank.iban:
                pdf.cell(0, 5, f"IBAN: {bank.iban}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            if bank.swift:
                pdf.cell(0, 5, f"SWIFT: {bank.swift}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        elif bank_check:
            for key, value in bank_check.items():
                pdf.cell(0, 5, f"{key}: {value}",
                         new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(3)

    def _render_footer(self, pdf: FPDF, audit: AuditResult) -> None:
        """Render footer with audit status."""
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, f"Audit Status: {audit.status.value}",
                 new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.cell(
            0, 5,
            f"Generated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
