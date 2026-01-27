"""
Abstract interfaces for invoice parsers.

Defines contracts for template, table-aware, and vision parsers.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from src.core.entities.invoice import Invoice, LineItem


@dataclass
class ParserResult:
    """Result from invoice parsing."""

    success: bool
    invoice: Invoice | None = None
    items: list[LineItem] | None = None
    confidence: float = 0.0
    parser_name: str = ""
    error: str | None = None
    metadata: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.items is None:
            self.items = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class TemplateMatch:
    """Result of template matching."""

    template_id: str
    template_name: str
    confidence: float
    company_key: str
    parser_hints: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.parser_hints is None:
            self.parser_hints = {}


class IInvoiceParser(ABC):
    """
    Abstract interface for invoice parsers.

    Implementations: TemplateParser, TableAwareParser, VisionParser
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Parser identifier name."""
        pass

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Parser priority (higher = tried first).

        Template: 100, Table-aware: 80, Vision: 60
        """
        pass

    @abstractmethod
    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse invoice text into structured data.

        Args:
            text: Extracted text content
            filename: Original filename
            hints: Optional parsing hints from template detection

        Returns:
            ParserResult with invoice and items
        """
        pass

    @abstractmethod
    def can_parse(self, text: str, hints: dict[str, Any] | None = None) -> float:
        """
        Check if parser can handle this content.

        Args:
            text: Text to evaluate
            hints: Optional hints

        Returns:
            Confidence score (0-1), 0 means cannot parse
        """
        pass


class ITemplateDetector(ABC):
    """
    Interface for template detection.

    Matches invoice content against known company templates.
    """

    @abstractmethod
    def detect(self, text: str) -> TemplateMatch | None:
        """
        Detect which template matches the invoice.

        Args:
            text: Invoice text content

        Returns:
            TemplateMatch if found, None otherwise
        """
        pass

    @abstractmethod
    def load_templates(self, template_dir: str) -> int:
        """
        Load templates from directory.

        Args:
            template_dir: Path to templates directory

        Returns:
            Number of templates loaded
        """
        pass

    @abstractmethod
    def get_template(self, template_id: str) -> dict[str, Any] | None:
        """Get template by ID."""
        pass

    @abstractmethod
    def list_templates(self) -> list[dict[str, Any]]:
        """List all loaded templates."""
        pass


class ITextExtractor(ABC):
    """
    Interface for text extraction from documents.

    Handles PDF, image, and OCR extraction.
    """

    @abstractmethod
    async def extract(self, file_path: str) -> str:
        """
        Extract text from a document file.

        Args:
            file_path: Path to document

        Returns:
            Extracted text content
        """
        pass

    @abstractmethod
    async def extract_pages(self, file_path: str) -> list[tuple[int, str]]:
        """
        Extract text from each page separately.

        Args:
            file_path: Path to document

        Returns:
            List of (page_number, text) tuples
        """
        pass

    @abstractmethod
    async def extract_with_images(
        self,
        file_path: str,
        output_dir: str,
    ) -> tuple[str, list[str]]:
        """
        Extract text and save page images.

        Args:
            file_path: Path to document
            output_dir: Directory for page images

        Returns:
            Tuple of (full_text, list_of_image_paths)
        """
        pass


class IParserRegistry(ABC):
    """
    Registry for parser strategy selection.

    Manages multiple parsers and orchestrates parsing.
    """

    @abstractmethod
    def register(self, parser: IInvoiceParser) -> None:
        """Register a parser implementation."""
        pass

    @abstractmethod
    def unregister(self, parser_name: str) -> bool:
        """Unregister a parser by name."""
        pass

    @abstractmethod
    def get_parsers(self) -> list[IInvoiceParser]:
        """Get all registered parsers sorted by priority."""
        pass

    @abstractmethod
    async def parse(
        self,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse using the best available parser.

        Tries parsers in priority order until one succeeds.

        Args:
            text: Invoice text content
            filename: Original filename
            hints: Optional parsing hints

        Returns:
            ParserResult from first successful parser
        """
        pass

    @abstractmethod
    async def parse_with_parser(
        self,
        parser_name: str,
        text: str,
        filename: str,
        hints: dict[str, Any] | None = None,
    ) -> ParserResult:
        """
        Parse using a specific parser by name.

        Args:
            parser_name: Name of parser to use
            text: Invoice text content
            filename: Original filename
            hints: Optional parsing hints

        Returns:
            ParserResult from specified parser
        """
        pass
