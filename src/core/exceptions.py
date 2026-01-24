"""
Domain exceptions for the SRG application.

Provides specific exception types for different error scenarios.
"""

from typing import Any


class SRGError(Exception):
    """Base exception for all SRG errors."""

    def __init__(
        self,
        message: str,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> dict:
        """Convert to dictionary for API responses."""
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details,
        }


# Storage Exceptions
class StorageError(SRGError):
    """Base exception for storage operations."""

    pass


class DocumentNotFoundError(StorageError):
    """Document not found in storage."""

    def __init__(self, doc_id: int):
        super().__init__(
            f"Document not found: {doc_id}",
            code="DOCUMENT_NOT_FOUND",
            details={"doc_id": doc_id},
        )


class InvoiceNotFoundError(StorageError):
    """Invoice not found in storage."""

    def __init__(self, invoice_id: int):
        super().__init__(
            f"Invoice not found: {invoice_id}",
            code="INVOICE_NOT_FOUND",
            details={"invoice_id": invoice_id},
        )


class SessionNotFoundError(StorageError):
    """Chat session not found."""

    def __init__(self, session_id: str):
        super().__init__(
            f"Session not found: {session_id}",
            code="SESSION_NOT_FOUND",
            details={"session_id": session_id},
        )


class DuplicateDocumentError(StorageError):
    """Document with same hash already exists."""

    def __init__(self, file_hash: str, existing_id: int):
        super().__init__(
            f"Document already exists with hash: {file_hash}",
            code="DUPLICATE_DOCUMENT",
            details={"file_hash": file_hash, "existing_id": existing_id},
        )


class DatabaseError(StorageError):
    """Database operation failed."""

    def __init__(self, operation: str, error: str):
        super().__init__(
            f"Database error during {operation}: {error}",
            code="DATABASE_ERROR",
            details={"operation": operation, "error": error},
        )


# LLM Exceptions
class LLMError(SRGError):
    """Base exception for LLM operations."""

    pass


class LLMUnavailableError(LLMError):
    """LLM provider is not available."""

    def __init__(self, provider: str, reason: str | None = None):
        super().__init__(
            f"LLM provider unavailable: {provider}" + (f" - {reason}" if reason else ""),
            code="LLM_UNAVAILABLE",
            details={"provider": provider, "reason": reason},
        )


class LLMTimeoutError(LLMError):
    """LLM request timed out."""

    def __init__(self, timeout: int, operation: str = "generation"):
        super().__init__(
            f"LLM {operation} timed out after {timeout} seconds",
            code="LLM_TIMEOUT",
            details={"timeout": timeout, "operation": operation},
        )


class LLMResponseError(LLMError):
    """LLM returned invalid or empty response."""

    def __init__(self, reason: str, response: str | None = None):
        super().__init__(
            f"Invalid LLM response: {reason}",
            code="LLM_RESPONSE_ERROR",
            details={"reason": reason, "response_preview": (response or "")[:200]},
        )


class ModelNotFoundError(LLMError):
    """Requested model not found."""

    def __init__(self, model: str, provider: str):
        super().__init__(
            f"Model '{model}' not found on {provider}",
            code="MODEL_NOT_FOUND",
            details={"model": model, "provider": provider},
        )


class CircuitBreakerOpenError(LLMError):
    """Circuit breaker is open due to repeated failures."""

    def __init__(self, provider: str, cooldown_remaining: int):
        super().__init__(
            f"Circuit breaker open for {provider}, retry in {cooldown_remaining}s",
            code="CIRCUIT_BREAKER_OPEN",
            details={"provider": provider, "cooldown_remaining": cooldown_remaining},
        )


# Parser Exceptions
class ParserError(SRGError):
    """Base exception for parsing operations."""

    pass


class ParsingFailedError(ParserError):
    """Invoice parsing failed."""

    def __init__(self, filename: str, reason: str, parser: str | None = None):
        super().__init__(
            f"Failed to parse '{filename}': {reason}",
            code="PARSING_FAILED",
            details={"filename": filename, "reason": reason, "parser": parser},
        )


class TemplateNotFoundError(ParserError):
    """Template not found for company."""

    def __init__(self, company_key: str):
        super().__init__(
            f"No template found for company: {company_key}",
            code="TEMPLATE_NOT_FOUND",
            details={"company_key": company_key},
        )


class ExtractionError(ParserError):
    """Text extraction from document failed."""

    def __init__(self, filename: str, reason: str):
        super().__init__(
            f"Failed to extract text from '{filename}': {reason}",
            code="EXTRACTION_ERROR",
            details={"filename": filename, "reason": reason},
        )


# Search Exceptions
class SearchError(SRGError):
    """Base exception for search operations."""

    pass


class IndexNotReadyError(SearchError):
    """Search index is not built or loaded."""

    def __init__(self, index_name: str):
        super().__init__(
            f"Index '{index_name}' is not ready",
            code="INDEX_NOT_READY",
            details={"index_name": index_name},
        )


class EmbeddingError(SearchError):
    """Embedding generation failed."""

    def __init__(self, reason: str):
        super().__init__(
            f"Embedding generation failed: {reason}",
            code="EMBEDDING_ERROR",
            details={"reason": reason},
        )


# Audit Exceptions
class AuditError(SRGError):
    """Base exception for audit operations."""

    pass


class AuditFailedError(AuditError):
    """Invoice audit failed."""

    def __init__(self, invoice_id: int, reason: str):
        super().__init__(
            f"Audit failed for invoice {invoice_id}: {reason}",
            code="AUDIT_FAILED",
            details={"invoice_id": invoice_id, "reason": reason},
        )


# Validation Exceptions
class ValidationError(SRGError):
    """Input validation failed."""

    def __init__(self, field: str, message: str, value: Any = None):
        super().__init__(
            f"Validation error for '{field}': {message}",
            code="VALIDATION_ERROR",
            details={
                "field": field,
                "message": message,
                "value": str(value)[:100] if value else None,
            },
        )


class FileTooLargeError(ValidationError):
    """Uploaded file exceeds size limit."""

    def __init__(self, filename: str, size: int, max_size: int):
        super().__init__(
            field="file",
            message=f"File '{filename}' is too large ({size} bytes, max {max_size})",
        )
        self.details.update(
            {
                "filename": filename,
                "size": size,
                "max_size": max_size,
            }
        )


class UnsupportedFileTypeError(ValidationError):
    """File type is not supported."""

    def __init__(self, filename: str, extension: str, allowed: list[str]):
        super().__init__(
            field="file",
            message=f"Unsupported file type '{extension}'. Allowed: {', '.join(allowed)}",
        )
        self.details.update(
            {
                "filename": filename,
                "extension": extension,
                "allowed": allowed,
            }
        )


class ChatError(SRGError):
    """Error during chat operations."""

    pass


class IndexingError(SRGError):
    """Error during document indexing."""

    pass


class ConfigurationError(SRGError):
    """Configuration error."""

    pass
