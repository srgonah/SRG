"""
Core business logic services.

Layer-pure services that depend only on:
- src/core/entities/*
- src/core/interfaces/*
- src/core/exceptions.py

NO infrastructure imports. All dependencies injected via constructor.
"""

from src.core.services.chat_service import ChatService
from src.core.services.document_indexer import DocumentIndexerService
from src.core.services.invoice_auditor import InvoiceAuditorService
from src.core.services.invoice_parser import InvoiceParserService
from src.core.services.material_ingestion import IngestionResult, MaterialIngestionService
from src.core.services.proforma_pdf_service import (
    IProformaPdfRenderer,
    ProformaPdfResult,
    ProformaPdfService,
)
from src.core.services.reminder_intelligence import ReminderIntelligenceService
from src.core.services.search_service import SearchContext, SearchService

__all__ = [
    # Invoice Parser
    "InvoiceParserService",
    # Invoice Auditor
    "InvoiceAuditorService",
    # Proforma PDF
    "ProformaPdfService",
    "ProformaPdfResult",
    "IProformaPdfRenderer",
    # Material Ingestion
    "MaterialIngestionService",
    "IngestionResult",
    # Search
    "SearchService",
    "SearchContext",
    # Chat
    "ChatService",
    # Document Indexer
    "DocumentIndexerService",
    # Reminder Intelligence
    "ReminderIntelligenceService",
]
