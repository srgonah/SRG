"""
Sales invoice PDF renderer using fpdf2.

Generates a professional sales invoice PDF with item details,
profit summary, and page-numbered footer.  Shares styling
conventions with the proforma renderer (logo placeholder,
alternating row shading, configurable header/footer text).
"""

import os
import re
from abc import ABC, abstractmethod
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.config.settings import PdfSettings, get_settings
from src.core.entities.local_sale import LocalSalesInvoice


# ---------------------------------------------------------------------------
# Arabic / RTL helpers (shared logic with proforma renderer)
# ---------------------------------------------------------------------------

_ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def _contains_arabic(text: str) -> bool:
    """Return True if *text* contains at least one Arabic character."""
    return bool(_ARABIC_RE.search(text))


def _strip_arabic(text: str) -> str:
    """Replace Arabic characters with '?' to avoid encoding errors."""
    return _ARABIC_RE.sub("?", text)


# ---------------------------------------------------------------------------
# Interface
# ---------------------------------------------------------------------------


class ISalesPdfRenderer(ABC):
    """Interface for sales invoice PDF rendering implementations."""

    @abstractmethod
    def render(self, invoice: LocalSalesInvoice) -> bytes:
        """Render a local sales invoice into PDF bytes."""
        ...


# ---------------------------------------------------------------------------
# Custom FPDF subclass with page-number footer
# ---------------------------------------------------------------------------


class _SalesPdf(FPDF):
    """FPDF subclass that renders a footer on every page."""

    def __init__(self, pdf_settings: PdfSettings) -> None:
        super().__init__()
        self._pdf_settings = pdf_settings
        self._generation_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    def footer(self) -> None:
        """Render footer with page numbers and generation date."""
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        footer_text = self._pdf_settings.footer_text
        self.cell(0, 5, footer_text, align="L")
        self.set_x(-60)
        self.cell(
            0,
            5,
            f"Page {self.page_no()} of {{nb}} | {self._generation_date}",
            align="R",
        )


# ---------------------------------------------------------------------------
# Concrete renderer
# ---------------------------------------------------------------------------


class Fpdf2SalesRenderer(ISalesPdfRenderer):
    """Renders sales invoice PDFs using fpdf2 with improved layout."""

    def __init__(self, pdf_settings: PdfSettings | None = None) -> None:
        if pdf_settings is None:
            pdf_settings = get_settings().pdf
        self._settings = pdf_settings
        self._arabic_font_loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, invoice: LocalSalesInvoice) -> bytes:
        """Render a LocalSalesInvoice into PDF bytes."""
        pdf = _SalesPdf(self._settings)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        self._arabic_font_loaded = False
        self._maybe_load_arabic_font(pdf)

        pdf.add_page()

        self._render_header(pdf, invoice)
        self._render_separator(pdf)
        self._render_items_table(pdf, invoice)
        self._render_summary(pdf, invoice)

        return bytes(pdf.output())

    # ------------------------------------------------------------------
    # Arabic font loading
    # ------------------------------------------------------------------

    def _maybe_load_arabic_font(self, pdf: FPDF) -> None:
        """Load an Arabic-capable TTF font if configured."""
        font_path = self._settings.arabic_font_path
        if not font_path or not os.path.isfile(font_path):
            return
        try:
            pdf.add_font("ArabicFont", "", font_path, uni=True)
            self._arabic_font_loaded = True
        except Exception:
            self._arabic_font_loaded = False

    def _safe_text(self, text: str) -> str:
        """Return *text* safe for the current font."""
        if self._arabic_font_loaded:
            return text
        if _contains_arabic(text):
            return _strip_arabic(text)
        return text

    def _use_font_for_text(
        self,
        pdf: FPDF,
        text: str,
        family: str = "Helvetica",
        style: str = "",
        size: int = 10,
    ) -> None:
        """Set font, switching to ArabicFont when Arabic text is detected."""
        if self._arabic_font_loaded and _contains_arabic(text):
            pdf.set_font("ArabicFont", "", size)
        else:
            pdf.set_font(family, style, size)

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _render_header(self, pdf: FPDF, invoice: LocalSalesInvoice) -> None:
        """Render header with logo placeholder, company info, and title."""
        # --- Logo placeholder (top-left, 40x20 mm) ---
        logo_path = self._settings.logo_path
        if logo_path and os.path.isfile(logo_path):
            try:
                pdf.image(logo_path, x=10, y=10, w=40, h=20)
            except Exception:
                self._draw_logo_placeholder(pdf)
        else:
            self._draw_logo_placeholder(pdf)

        # --- Company info (right of logo) ---
        pdf.set_xy(55, 10)
        company_name = self._safe_text(self._settings.company_name)
        self._use_font_for_text(
            pdf, company_name, "Helvetica", "B", 10,
        )
        pdf.cell(
            0, 5, company_name,
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

        pdf.set_x(55)
        pdf.set_font("Helvetica", "", 8)
        if self._settings.company_address:
            pdf.cell(
                0, 4, self._settings.company_address,
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            pdf.set_x(55)
        if self._settings.company_phone:
            pdf.cell(
                0, 4, f"Tel: {self._settings.company_phone}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
            pdf.set_x(55)
        if self._settings.company_email:
            pdf.cell(
                0, 4, f"Email: {self._settings.company_email}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )

        # Ensure Y is below logo area
        if pdf.get_y() < 32:
            pdf.set_y(32)

        # --- "SALES INVOICE" title ---
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(
            0, 12, "SALES INVOICE", align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(3)

        # --- Invoice metadata ---
        pdf.set_font("Helvetica", "", 10)
        pdf.cell(
            0, 6, f"Invoice No: {invoice.invoice_number}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.cell(
            0, 6, f"Date: {invoice.sale_date}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        customer = self._safe_text(invoice.customer_name)
        self._use_font_for_text(pdf, customer, size=10)
        pdf.cell(
            0, 6, f"Customer: {customer}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        if invoice.notes:
            notes = self._safe_text(invoice.notes)
            self._use_font_for_text(pdf, notes, size=10)
            pdf.cell(
                0, 6, f"Notes: {notes}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        pdf.ln(3)

    @staticmethod
    def _draw_logo_placeholder(pdf: FPDF) -> None:
        """Draw an empty rectangle with 'LOGO' text as placeholder."""
        x, y = 10, 10
        w, h = 40, 20
        pdf.set_draw_color(180, 180, 180)
        pdf.rect(x, y, w, h)
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(180, 180, 180)
        pdf.set_xy(x, y + 6)
        pdf.cell(w, 8, "LOGO", align="C")
        pdf.set_draw_color(0, 0, 0)
        pdf.set_text_color(0, 0, 0)

    @staticmethod
    def _render_separator(pdf: FPDF) -> None:
        """Draw a horizontal line separator between header and body."""
        y = pdf.get_y()
        pdf.set_draw_color(100, 100, 100)
        pdf.line(10, y, 200, y)
        pdf.set_draw_color(0, 0, 0)
        pdf.ln(4)

    def _render_items_table(
        self, pdf: FPDF, invoice: LocalSalesInvoice
    ) -> None:
        """Render items table with borders and alternating row shading."""
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Items", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Column definitions
        # Item Name | Qty | Unit Cost (WAC) | Sell Price | Total | Profit
        col_widths = [50, 18, 28, 28, 28, 28]
        headers = ["Item Name", "Qty", "Unit Cost", "Sell Price", "Total", "Profit"]

        # Table header row
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(70, 70, 70)
        pdf.set_text_color(255, 255, 255)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 7, header, border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        # Table rows
        pdf.set_font("Helvetica", "", 8)
        for idx, item in enumerate(invoice.items, 1):
            desc = self._safe_text(
                item.description[:35] if item.description else ""
            )
            # WAC unit cost = cost_basis / quantity (if qty > 0)
            unit_cost = item.cost_basis / item.quantity if item.quantity else 0.0

            # Alternating row background
            if idx % 2 == 0:
                pdf.set_fill_color(240, 240, 240)
                fill = True
            else:
                fill = False

            self._use_font_for_text(pdf, desc, size=8)
            pdf.cell(col_widths[0], 6, desc, border=1, fill=fill)
            pdf.cell(
                col_widths[1], 6, f"{item.quantity:g}",
                border=1, align="R", fill=fill,
            )
            pdf.cell(
                col_widths[2], 6, f"{unit_cost:,.2f}",
                border=1, align="R", fill=fill,
            )
            pdf.cell(
                col_widths[3], 6, f"{item.unit_price:,.2f}",
                border=1, align="R", fill=fill,
            )
            pdf.cell(
                col_widths[4], 6, f"{item.line_total:,.2f}",
                border=1, align="R", fill=fill,
            )
            pdf.cell(
                col_widths[5], 6, f"{item.profit:,.2f}",
                border=1, align="R", fill=fill,
            )
            pdf.ln()

        pdf.ln(3)

    @staticmethod
    def _render_summary(pdf: FPDF, invoice: LocalSalesInvoice) -> None:
        """Render summary section with subtotal, profit, and grand total."""
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, "Summary", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)

        pdf.cell(120, 6, "Subtotal:", align="R")
        pdf.cell(
            0, 6, f"{invoice.subtotal:,.2f}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

        if invoice.tax_amount:
            pdf.cell(120, 6, "Tax:", align="R")
            pdf.cell(
                0, 6, f"{invoice.tax_amount:,.2f}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )

        pdf.cell(120, 6, "Total Cost:", align="R")
        pdf.cell(
            0, 6, f"{invoice.total_cost:,.2f}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(120, 6, "Total Profit:", align="R")
        pdf.cell(
            0, 6, f"{invoice.total_profit:,.2f}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )

        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(120, 8, "Grand Total:", align="R")
        pdf.cell(
            0, 8, f"{invoice.total_amount:,.2f}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(3)
