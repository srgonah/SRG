"""
Template-based PDF renderer.

Renders PDF documents using configurable templates with backgrounds,
signatures, stamps, and dynamic positioning.
"""

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF, XPos, YPos

from src.config import get_logger, get_settings
from src.core.entities.template import PdfTemplate, Position

_logger = get_logger(__name__)


class _TemplatePdf(FPDF):
    """Custom FPDF class with template support."""

    def __init__(self, template: PdfTemplate | None = None):
        orientation = "P" if not template or template.orientation == "portrait" else "L"
        super().__init__(orientation=orientation, unit="mm", format="A4")

        self.template = template
        self.settings = get_settings().pdf

        # Set margins
        if template:
            self.set_margins(
                template.margin_left,
                template.margin_top,
                template.margin_right,
            )
            self.set_auto_page_break(auto=True, margin=template.margin_bottom)
        else:
            self.set_margins(10, 10, 10)
            self.set_auto_page_break(auto=True, margin=15)

        self.alias_nb_pages()

    def header(self):
        """Add background image if template has one."""
        if self.template and self.template.background_path:
            bg_path = Path(self.template.background_path)
            if bg_path.exists():
                # Add background image covering the whole page
                self.image(
                    str(bg_path),
                    x=0,
                    y=0,
                    w=210,  # A4 width
                    h=297,  # A4 height
                )

    def footer(self):
        """Add page number footer."""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(128)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}", align="C")


class TemplateRenderer:
    """Renders PDF documents using templates."""

    def __init__(self, template: PdfTemplate | None = None):
        self.template = template
        self.settings = get_settings().pdf

    def render(self, data: dict[str, Any]) -> bytes:
        """Render a document to PDF bytes."""
        pdf = _TemplatePdf(self.template)
        pdf.add_page()

        # Set default font
        pdf.set_font("Helvetica", size=10)

        # Render sections based on document type
        doc_type = data.get("document_type", "proforma")

        if doc_type in ["proforma", "sales_invoice", "quote", "receipt"]:
            self._render_invoice_document(pdf, data)
        else:
            self._render_generic_document(pdf, data)

        return pdf.output()

    def _render_invoice_document(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render an invoice-style document (proforma or sales)."""
        # Header with company info
        self._render_header(pdf, data)

        # Document title and number
        self._render_document_info(pdf, data)

        # Parties (seller and buyer)
        self._render_parties(pdf, data)

        # Items table
        self._render_items_table(pdf, data)

        # Totals
        self._render_totals(pdf, data)

        # Bank details
        if data.get("bank_details"):
            self._render_bank_details(pdf, data)

        # Notes and terms
        self._render_notes(pdf, data)

        # Signature and stamp
        self._render_signature_stamp(pdf)

    def _render_header(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render document header with company info."""
        # Use template position or default
        y_start = 15
        if self.template and self.template.positions.company_name:
            y_start = self.template.positions.company_name.y

        pdf.set_xy(10, y_start)

        # Logo
        logo_path = None
        if self.template and self.template.logo_path:
            logo_path = self.template.logo_path
        elif self.settings.logo_path:
            logo_path = self.settings.logo_path

        if logo_path and Path(logo_path).exists():
            pdf.image(logo_path, x=10, y=y_start, h=15)
            pdf.set_xy(40, y_start)

        # Company name
        company_name = self.settings.company_name
        if data.get("seller", {}).get("name"):
            company_name = data["seller"]["name"]

        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 6, company_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Company address
        pdf.set_font("Helvetica", size=9)
        if data.get("seller", {}).get("address"):
            pdf.multi_cell(0, 4, data["seller"]["address"])
        elif self.settings.company_address:
            pdf.multi_cell(0, 4, self.settings.company_address)

        # Contact info
        contact_parts = []
        if data.get("seller", {}).get("phone") or self.settings.company_phone:
            contact_parts.append(f"Tel: {data.get('seller', {}).get('phone') or self.settings.company_phone}")
        if data.get("seller", {}).get("email") or self.settings.company_email:
            contact_parts.append(f"Email: {data.get('seller', {}).get('email') or self.settings.company_email}")

        if contact_parts:
            pdf.cell(0, 5, " | ".join(contact_parts), new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)

        # Separator line
        pdf.set_draw_color(200)
        pdf.line(10, pdf.get_y(), 200, pdf.get_y())
        pdf.ln(5)

    def _render_document_info(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render document title and number."""
        doc_type = data.get("document_type", "proforma")

        # Document title
        title_map = {
            "proforma": "PROFORMA INVOICE",
            "sales_invoice": "SALES INVOICE",
            "quote": "QUOTATION",
            "receipt": "RECEIPT",
        }
        title = title_map.get(doc_type, "DOCUMENT")

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, title, align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Document number and date
        pdf.set_font("Helvetica", size=10)
        doc_number = data.get("document_number", "")
        doc_date = data.get("document_date", datetime.now().strftime("%Y-%m-%d"))

        pdf.cell(100, 6, f"No: {doc_number}")
        pdf.cell(0, 6, f"Date: {doc_date}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if data.get("valid_until"):
            pdf.cell(0, 6, f"Valid Until: {data['valid_until']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)

    def _render_parties(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render seller and buyer information side by side."""
        start_y = pdf.get_y()

        # Buyer info (right side)
        pdf.set_xy(110, start_y)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Bill To:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        buyer = data.get("buyer", {})
        pdf.set_xy(110, pdf.get_y())
        pdf.set_font("Helvetica", size=10)

        if buyer.get("name"):
            pdf.cell(0, 5, buyer["name"], new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_x(110)

        if buyer.get("address"):
            pdf.set_x(110)
            pdf.multi_cell(90, 4, buyer["address"])

        if buyer.get("phone"):
            pdf.set_x(110)
            pdf.cell(0, 5, f"Tel: {buyer['phone']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if buyer.get("email"):
            pdf.set_x(110)
            pdf.cell(0, 5, f"Email: {buyer['email']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if buyer.get("tax_id"):
            pdf.set_x(110)
            pdf.cell(0, 5, f"Tax ID: {buyer['tax_id']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        end_y = pdf.get_y()
        pdf.set_y(max(start_y + 30, end_y) + 5)

    def _render_items_table(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render the items table."""
        items = data.get("items", [])
        currency = data.get("currency", "AED")

        if not items:
            return

        # Table header
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(230, 230, 230)

        # Column widths
        col_widths = [10, 80, 20, 15, 30, 35]  # #, Description, Qty, Unit, Price, Total

        headers = ["#", "Description", "Qty", "Unit", f"Price ({currency})", f"Total ({currency})"]
        for i, (header, width) in enumerate(zip(headers, col_widths)):
            align = "R" if i >= 2 else "L"
            pdf.cell(width, 7, header, border=1, align=align, fill=True)
        pdf.ln()

        # Table rows
        pdf.set_font("Helvetica", size=9)
        for idx, item in enumerate(items, 1):
            # Alternate row colors
            if idx % 2 == 0:
                pdf.set_fill_color(245, 245, 245)
            else:
                pdf.set_fill_color(255, 255, 255)

            fill = True

            pdf.cell(col_widths[0], 6, str(idx), border=1, fill=fill)
            pdf.cell(col_widths[1], 6, str(item.get("description", ""))[:50], border=1, fill=fill)
            pdf.cell(col_widths[2], 6, str(item.get("quantity", 0)), border=1, align="R", fill=fill)
            pdf.cell(col_widths[3], 6, str(item.get("unit", "")), border=1, align="C", fill=fill)
            pdf.cell(col_widths[4], 6, f"{item.get('unit_price', 0):,.2f}", border=1, align="R", fill=fill)
            pdf.cell(col_widths[5], 6, f"{item.get('total', 0):,.2f}", border=1, align="R", fill=fill)
            pdf.ln()

        pdf.ln(5)

    def _render_totals(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render totals section."""
        currency = data.get("currency", "AED")

        # Position totals on the right
        pdf.set_x(120)
        pdf.set_font("Helvetica", size=10)

        # Subtotal
        pdf.cell(40, 6, "Subtotal:", align="R")
        pdf.cell(40, 6, f"{currency} {data.get('subtotal', 0):,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Tax
        if data.get("tax_amount", 0) > 0:
            pdf.set_x(120)
            pdf.cell(40, 6, "Tax:", align="R")
            pdf.cell(40, 6, f"{currency} {data.get('tax_amount', 0):,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Discount
        if data.get("discount_amount", 0) > 0:
            pdf.set_x(120)
            pdf.cell(40, 6, "Discount:", align="R")
            pdf.cell(40, 6, f"-{currency} {data.get('discount_amount', 0):,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Total
        pdf.set_x(120)
        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(40, 8, "TOTAL:", align="R")
        pdf.cell(40, 8, f"{currency} {data.get('total_amount', 0):,.2f}", align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)

    def _render_bank_details(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render bank details section."""
        bank = data.get("bank_details", {})
        if not bank:
            return

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 6, "Bank Details:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", size=9)

        if bank.get("bank_name"):
            pdf.cell(0, 5, f"Bank: {bank['bank_name']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if bank.get("account_name"):
            pdf.cell(0, 5, f"Account Name: {bank['account_name']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if bank.get("account_number"):
            pdf.cell(0, 5, f"Account No: {bank['account_number']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if bank.get("iban"):
            pdf.cell(0, 5, f"IBAN: {bank['iban']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        if bank.get("swift_code"):
            pdf.cell(0, 5, f"SWIFT: {bank['swift_code']}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)

    def _render_notes(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render notes and terms."""
        if data.get("notes"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Notes:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", size=9)
            pdf.multi_cell(0, 4, data["notes"])
            pdf.ln(3)

        if data.get("terms"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Terms & Conditions:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", size=9)
            pdf.multi_cell(0, 4, data["terms"])
            pdf.ln(3)

        if data.get("payment_terms"):
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 6, "Payment Terms:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            pdf.set_font("Helvetica", size=9)
            pdf.multi_cell(0, 4, data["payment_terms"])

    def _render_signature_stamp(self, pdf: _TemplatePdf):
        """Render signature and stamp if template has them."""
        if not self.template:
            return

        y_pos = pdf.get_y() + 10

        # Ensure we're not too close to the bottom
        if y_pos > 250:
            pdf.add_page()
            y_pos = 30

        # Signature
        if self.template.signature_path and Path(self.template.signature_path).exists():
            sig_x = 20
            sig_y = y_pos
            if self.template.positions.signature:
                sig_x = self.template.positions.signature.x
                sig_y = self.template.positions.signature.y

            pdf.image(self.template.signature_path, x=sig_x, y=sig_y, h=20)

        # Stamp
        if self.template.stamp_path and Path(self.template.stamp_path).exists():
            stamp_x = 140
            stamp_y = y_pos
            if self.template.positions.stamp:
                stamp_x = self.template.positions.stamp.x
                stamp_y = self.template.positions.stamp.y

            pdf.image(self.template.stamp_path, x=stamp_x, y=stamp_y, h=25)

    def _render_generic_document(self, pdf: _TemplatePdf, data: dict[str, Any]):
        """Render a generic document type."""
        # Simple text rendering for unsupported types
        pdf.set_font("Helvetica", size=12)
        pdf.multi_cell(0, 6, str(data))
