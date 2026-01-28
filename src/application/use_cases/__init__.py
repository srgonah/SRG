"""Application use cases."""

from src.application.use_cases.add_to_catalog import AddToCatalogUseCase, AutoMatchResult
from src.application.use_cases.audit_invoice import AuditInvoiceUseCase
from src.application.use_cases.chat_with_context import ChatWithContextUseCase
from src.application.use_cases.check_expiring_documents import (
    CheckExpiringDocumentsUseCase,
    ExpiryCheckResult,
)
from src.application.use_cases.create_sales_invoice import CreateSalesInvoiceUseCase
from src.application.use_cases.evaluate_reminder_insights import (
    EvaluateReminderInsightsUseCase,
    InsightEvaluationResult,
)
from src.application.use_cases.generate_proforma_pdf import GenerateProformaPdfUseCase
from src.application.use_cases.ingest_material import IngestMaterialUseCase
from src.application.use_cases.issue_stock import IssueStockUseCase
from src.application.use_cases.receive_stock import ReceiveStockUseCase
from src.application.use_cases.search_documents import SearchDocumentsUseCase
from src.application.use_cases.upload_invoice import UploadInvoiceUseCase

__all__ = [
    "UploadInvoiceUseCase",
    "AuditInvoiceUseCase",
    "SearchDocumentsUseCase",
    "ChatWithContextUseCase",
    "AddToCatalogUseCase",
    "AutoMatchResult",
    "GenerateProformaPdfUseCase",
    "IngestMaterialUseCase",
    "CheckExpiringDocumentsUseCase",
    "ExpiryCheckResult",
    "EvaluateReminderInsightsUseCase",
    "InsightEvaluationResult",
    "ReceiveStockUseCase",
    "IssueStockUseCase",
    "CreateSalesInvoiceUseCase",
]
