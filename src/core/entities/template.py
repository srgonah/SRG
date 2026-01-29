"""
PDF Template entity.

Represents a reusable PDF template with background image, signature, stamp,
and configurable positions for dynamic content.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class TemplateType(str, Enum):
    """Type of PDF template."""

    PROFORMA = "proforma"
    SALES = "sales"
    QUOTE = "quote"
    RECEIPT = "receipt"


@dataclass
class Position:
    """Position and size configuration for a template element."""

    x: float  # X coordinate (mm from left)
    y: float  # Y coordinate (mm from top)
    width: float | None = None  # Width in mm (optional)
    height: float | None = None  # Height in mm (optional)
    font_size: int | None = None  # Font size for text elements
    alignment: str = "left"  # left, center, right


@dataclass
class TemplatePositions:
    """Positions for all dynamic elements in the template."""

    # Header positions
    company_name: Position | None = None
    company_address: Position | None = None
    company_phone: Position | None = None
    company_email: Position | None = None
    logo: Position | None = None

    # Document info positions
    document_title: Position | None = None
    document_number: Position | None = None
    document_date: Position | None = None

    # Party positions
    seller_info: Position | None = None
    buyer_info: Position | None = None

    # Bank details position
    bank_details: Position | None = None

    # Items table position
    items_table: Position | None = None

    # Totals position
    totals: Position | None = None

    # Signature and stamp positions
    signature: Position | None = None
    stamp: Position | None = None

    # Footer position
    footer: Position | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                result[key] = {
                    "x": value.x,
                    "y": value.y,
                    "width": value.width,
                    "height": value.height,
                    "font_size": value.font_size,
                    "alignment": value.alignment,
                }
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "TemplatePositions":
        """Create from dictionary."""
        positions = cls()
        for key, value in data.items():
            if hasattr(positions, key) and value:
                setattr(
                    positions,
                    key,
                    Position(
                        x=value.get("x", 0),
                        y=value.get("y", 0),
                        width=value.get("width"),
                        height=value.get("height"),
                        font_size=value.get("font_size"),
                        alignment=value.get("alignment", "left"),
                    ),
                )
        return positions


@dataclass
class PdfTemplate:
    """PDF template with customizable layout and assets."""

    id: int | None = None
    name: str = ""
    description: str = ""
    template_type: TemplateType = TemplateType.PROFORMA

    # Asset file paths (stored in data/templates/)
    background_path: str | None = None  # Background image (PNG/JPG)
    signature_path: str | None = None  # Signature image
    stamp_path: str | None = None  # Stamp/seal image
    logo_path: str | None = None  # Company logo

    # Layout configuration
    positions: TemplatePositions = field(default_factory=TemplatePositions)

    # Page settings
    page_size: str = "A4"  # A4, Letter, etc.
    orientation: str = "portrait"  # portrait, landscape
    margin_top: float = 10.0
    margin_bottom: float = 10.0
    margin_left: float = 10.0
    margin_right: float = 10.0

    # Styling
    primary_color: str = "#000000"
    secondary_color: str = "#666666"
    header_font_size: int = 12
    body_font_size: int = 10

    # Metadata
    is_default: bool = False
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Ensure template_type is enum."""
        if isinstance(self.template_type, str):
            self.template_type = TemplateType(self.template_type)
