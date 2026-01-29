"""
Fpdf2 implementation of proforma PDF rendering.

Builds a structured PDF with invoice and audit information,
including company branding, alternating row shading, page numbers,
and configurable header/footer text from PdfSettings.
"""

import os
import re
from datetime import datetime

from fpdf import FPDF
from fpdf.enums import XPos, YPos

from src.config.settings import PdfSettings, get_settings
from src.core.entities.invoice import AuditResult, Invoice, RowType
from src.core.services.proforma_pdf_service import IProformaPdfRenderer


# ---------------------------------------------------------------------------
# Arabic / RTL helpers
# ---------------------------------------------------------------------------

_ARABIC_RE = re.compile(
    r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]"
)


def _contains_arabic(text: str) -> bool:
    """Return True if *text* contains at least one Arabic character."""
    return bool(_ARABIC_RE.search(text))


def _strip_arabic(text: str) -> str:
    """Remove Arabic characters from *text* to avoid encoding errors.

    When no Arabic-capable font is loaded, fpdf2's built-in fonts
    (Helvetica, Courier, etc.) will raise ``FPDFUnicodeEncodingException``
    for Arabic code-points.  This helper replaces them with '?' so the
    rest of the text can still be rendered.
    """
    return _ARABIC_RE.sub("?", text)


# ---------------------------------------------------------------------------
# Custom FPDF subclass with page-number footer
# ---------------------------------------------------------------------------

class _ProformaPdf(FPDF):
    """FPDF subclass that renders a footer on every page."""

    def __init__(self, pdf_settings: PdfSettings) -> None:
        super().__init__()
        self._pdf_settings = pdf_settings
        self._generation_date = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    # fpdf2 calls this automatically at the bottom of each page.
    def footer(self) -> None:  # noqa: D401
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


class Fpdf2ProformaRenderer(IProformaPdfRenderer):
    """Renders proforma PDFs using fpdf2 with improved layout."""

    def __init__(self, pdf_settings: PdfSettings | None = None) -> None:
        if pdf_settings is None:
            pdf_settings = get_settings().pdf
        self._settings = pdf_settings
        self._arabic_font_loaded = False

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def render(self, invoice: Invoice, audit: AuditResult) -> bytes:
        """Render invoice and audit data into PDF bytes."""
        pdf = _ProformaPdf(self._settings)
        pdf.alias_nb_pages()
        pdf.set_auto_page_break(auto=True, margin=20)

        self._arabic_font_loaded = False
        self._maybe_load_arabic_font(pdf)

        pdf.add_page()

        self._render_header(pdf, invoice)
        self._render_separator(pdf)
        self._render_proforma_summary(pdf, invoice, audit)
        self._render_items_table(pdf, invoice, audit)
        self._render_totals(pdf, invoice)
        self._render_bank_details(pdf, invoice, audit)
        self._render_audit_status(pdf, audit)

        return bytes(pdf.output())

    # ------------------------------------------------------------------
    # Arabic font loading
    # ------------------------------------------------------------------

    def _maybe_load_arabic_font(self, pdf: FPDF) -> None:
        """Load an Arabic-capable TTF font if configured and available.

        fpdf2 supports adding external TTF fonts via ``add_font()``.
        When ``pdf.arabic_font_path`` is set in the application settings
        and the file exists, we register it under the family name
        ``"ArabicFont"``.  If the path is empty or the file is missing
        the renderer will silently fall back to the built-in Helvetica
        font (which cannot display Arabic glyphs).

        To enable Arabic support:
        1. Download a TTF font that covers Arabic, e.g.
           *NotoSansArabic-Regular.ttf* or *DejaVuSans.ttf*.
        2. Set the environment variable ``PDF_ARABIC_FONT_PATH`` to the
           absolute path of the font file, or configure it in ``.env``.
        """
        font_path = self._settings.arabic_font_path
        if not font_path:
            return
        if not os.path.isfile(font_path):
            return
        try:
            pdf.add_font("ArabicFont", "", font_path, uni=True)
            self._arabic_font_loaded = True
        except Exception:
            # If the font cannot be loaded we degrade gracefully.
            self._arabic_font_loaded = False

    def _safe_text(self, text: str) -> str:
        """Return *text* safe for the current font.

        If an Arabic-capable font is loaded, text is returned as-is.
        Otherwise, Arabic characters are replaced with '?' to prevent
        ``FPDFUnicodeEncodingException`` from fpdf2's built-in fonts.
        """
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

    def _render_header(self, pdf: FPDF, invoice: Invoice) -> None:
        """Render PDF header with logo placeholder, company info, and title."""
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
        self._use_font_for_text(pdf, company_name, "Helvetica", "B", 10)
        pdf.cell(0, 5, company_name, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

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

        # --- "PROFORMA INVOICE" title ---
        pdf.ln(4)
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(
            0, 12, "PROFORMA INVOICE", align="C",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
        pdf.ln(3)

        # --- Invoice metadata ---
        pdf.set_font("Helvetica", "", 10)
        if invoice.invoice_no:
            pdf.cell(
                0, 6, f"Invoice No: {invoice.invoice_no}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        if invoice.invoice_date:
            pdf.cell(
                0, 6, f"Date: {invoice.invoice_date}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        if invoice.seller_name:
            seller = self._safe_text(invoice.seller_name)
            self._use_font_for_text(pdf, seller, size=10)
            pdf.cell(
                0, 6, f"Seller: {seller}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        if invoice.buyer_name:
            buyer = self._safe_text(invoice.buyer_name)
            self._use_font_for_text(pdf, buyer, size=10)
            pdf.cell(
                0, 6, f"Buyer: {buyer}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        if invoice.currency:
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(
                0, 6, f"Currency: {invoice.currency}",
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
        # Reset colours
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
            text = self._safe_text(f"{key}: {value}")
            self._use_font_for_text(pdf, text, size=9)
            pdf.cell(0, 5, text, new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.ln(3)

    def _render_items_table(
        self, pdf: FPDF, invoice: Invoice, audit: AuditResult
    ) -> None:
        """Render items table with borders and alternating row shading."""
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Items", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Column definitions
        col_widths = [10, 60, 25, 30, 30, 35]
        headers = ["#", "Description", "Qty", "Unit", "Unit Price", "Total"]

        # Table header row
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(70, 70, 70)
        pdf.set_text_color(255, 255, 255)
        for i, header in enumerate(headers):
            pdf.cell(col_widths[i], 7, header, border=1, fill=True, align="C")
        pdf.ln()
        pdf.set_text_color(0, 0, 0)

        # Table rows with alternating shading
        pdf.set_font("Helvetica", "", 8)
        items = [item for item in invoice.items if item.row_type == RowType.LINE_ITEM]

        for idx, item in enumerate(items, 1):
            desc = self._safe_text((item.description or item.item_name)[:40])
            unit = self._safe_text((item.unit or "")[:10])

            # Alternating row background
            if idx % 2 == 0:
                pdf.set_fill_color(240, 240, 240)
                fill = True
            else:
                fill = False

            self._use_font_for_text(pdf, desc, size=8)
            pdf.cell(col_widths[0], 6, str(idx), border=1, fill=fill)
            pdf.cell(col_widths[1], 6, desc, border=1, fill=fill)
            pdf.cell(
                col_widths[2], 6, f"{item.quantity:g}",
                border=1, align="R", fill=fill,
            )
            pdf.cell(col_widths[3], 6, unit, border=1, fill=fill)
            pdf.cell(
                col_widths[4], 6, f"{item.unit_price:,.2f}",
                border=1, align="R", fill=fill,
            )
            pdf.cell(
                col_widths[5], 6, f"{item.total_price:,.2f}",
                border=1, align="R", fill=fill,
            )
            pdf.ln()

        pdf.ln(3)

    def _render_totals(self, pdf: FPDF, invoice: Invoice) -> None:
        """Render totals section."""
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, "Totals", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)

        if invoice.subtotal:
            pdf.cell(100, 6, "Subtotal:", align="R")
            pdf.cell(
                0, 6, f"{invoice.subtotal:,.2f} {invoice.currency}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        if invoice.tax_amount:
            pdf.cell(100, 6, "Tax:", align="R")
            pdf.cell(
                0, 6, f"{invoice.tax_amount:,.2f} {invoice.currency}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )
        if invoice.discount_amount:
            pdf.cell(100, 6, "Discount:", align="R")
            pdf.cell(
                0, 6, f"-{invoice.discount_amount:,.2f} {invoice.currency}",
                new_x=XPos.LMARGIN, new_y=YPos.NEXT,
            )

        pdf.set_font("Helvetica", "B", 11)
        pdf.cell(100, 8, "Total:", align="R")
        pdf.cell(
            0, 8, f"{invoice.total_amount:,.2f} {invoice.currency}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
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
                pdf.cell(
                    0, 5, f"Beneficiary: {bank.beneficiary_name}",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                )
            if bank.bank_name:
                pdf.cell(
                    0, 5, f"Bank: {bank.bank_name}",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                )
            if bank.account_number:
                pdf.cell(
                    0, 5, f"Account: {bank.account_number}",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                )
            if bank.iban:
                pdf.cell(
                    0, 5, f"IBAN: {bank.iban}",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                )
            if bank.swift:
                pdf.cell(
                    0, 5, f"SWIFT: {bank.swift}",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                )
        elif bank_check:
            for key, value in bank_check.items():
                pdf.cell(
                    0, 5, f"{key}: {value}",
                    new_x=XPos.LMARGIN, new_y=YPos.NEXT,
                )

        pdf.ln(3)

    @staticmethod
    def _render_audit_status(pdf: FPDF, audit: AuditResult) -> None:
        """Render audit status line (above the automatic footer)."""
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(
            0, 5, f"Audit Status: {audit.status.value}",
            new_x=XPos.LMARGIN, new_y=YPos.NEXT,
        )
