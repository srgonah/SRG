"""
Error handling middleware.

Standardizes all API error responses to include:
- error_code: machine-readable identifier
- message: human-readable description
- hint: suggested recovery action
"""

import traceback
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from src.application.dto.responses import ErrorResponse
from src.config import get_logger
from src.core.exceptions import (
    AuditError,
    ChatError,
    ConfigurationError,
    IndexingError,
    LLMError,
    ParserError,
    SearchError,
    SRGError,
    StorageError,
    ValidationError,
)

logger = get_logger(__name__)


# Map exceptions to HTTP status codes
EXCEPTION_STATUS_MAP: dict[type[Exception], int] = {
    ValidationError: status.HTTP_400_BAD_REQUEST,
    ParserError: 422,
    StorageError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    LLMError: status.HTTP_503_SERVICE_UNAVAILABLE,
    SearchError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ConfigurationError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    AuditError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    IndexingError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    ChatError: status.HTTP_500_INTERNAL_SERVER_ERROR,
    FileNotFoundError: status.HTTP_404_NOT_FOUND,
    ValueError: status.HTTP_400_BAD_REQUEST,
    KeyError: status.HTTP_404_NOT_FOUND,
}

# Hint messages per error code / exception type
HINT_MAP: dict[str, str] = {
    "INVOICE_NOT_FOUND": "Check the invoice ID and try GET /api/invoices to list available invoices.",
    "DOCUMENT_NOT_FOUND": "Check the document ID and try GET /api/documents to list available documents.",
    "SESSION_NOT_FOUND": "Check the session ID and try GET /api/sessions to list available sessions.",
    "MATERIAL_NOT_FOUND": "Check the material ID and try GET /api/catalog/ to list materials.",
    "DUPLICATE_DOCUMENT": "A document with the same file hash already exists.",
    "PARSING_FAILED": "Ensure the file is a valid PDF or image. Try a different parser.",
    "TEMPLATE_NOT_FOUND": "Upload using vendor_hint or template_id to select a parser template.",
    "EXTRACTION_ERROR": "The file may be corrupted or password-protected.",
    "LLM_UNAVAILABLE": "The LLM provider is offline. Retry later or disable LLM features.",
    "LLM_TIMEOUT": "The LLM request timed out. Retry with a shorter document.",
    "CIRCUIT_BREAKER_OPEN": "Too many LLM failures. Wait for cooldown before retrying.",
    "INDEX_NOT_READY": "The search index is not built. Run POST /api/documents/index first.",
    "EMBEDDING_ERROR": "Embedding generation failed. Check the embedding provider status.",
    "AUDIT_FAILED": "The audit could not complete. Check the invoice data.",
    "VALIDATION_ERROR": "Check the request body against the API schema.",
    "DATABASE_ERROR": "A database operation failed. Check server logs.",
    "ValidationError": "Check the request body fields and types.",
    "FileNotFoundError": "The requested file or resource was not found.",
    "ValueError": "A parameter value is invalid. Check the request.",
    "KeyError": "The requested key was not found.",
}

# Default hints by HTTP status code
STATUS_HINTS: dict[int, str] = {
    400: "Check the request parameters and body.",
    404: "The requested resource was not found. Verify the ID.",
    422: "The request could not be processed. Check the input format.",
    500: "An internal error occurred. Check server logs.",
    503: "The service is temporarily unavailable. Retry later.",
}


def _get_hint(error_code: str, status_code: int) -> str:
    """Resolve hint from error code, falling back to status-based hint."""
    return HINT_MAP.get(error_code) or STATUS_HINTS.get(status_code, "")


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Converts exceptions to standardized JSON error responses.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """Handle request with error catching."""
        try:
            return await call_next(request)

        except Exception as e:
            return self._handle_exception(request, e)

    def _handle_exception(
        self,
        request: Request,
        exc: Exception,
    ) -> JSONResponse:
        """Convert exception to standardized JSON response."""
        # Get status code
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        for exc_type, code in EXCEPTION_STATUS_MAP.items():
            if isinstance(exc, exc_type):
                status_code = code
                break

        # Get error code: prefer SRGError.code, fall back to class name
        if isinstance(exc, SRGError):
            error_code = exc.code
        else:
            error_code = exc.__class__.__name__

        # Get request ID if available
        request_id = getattr(request.state, "request_id", None)

        # Log error
        logger.error(
            "unhandled_exception",
            request_id=request_id,
            path=request.url.path,
            error_type=error_code,
            error=str(exc),
            traceback=traceback.format_exc() if status_code >= 500 else None,
        )

        # Build response
        hint = _get_hint(error_code, status_code)

        error_response = ErrorResponse(
            error_code=error_code,
            message=str(exc),
            hint=hint,
            path=request.url.path,
        )

        return JSONResponse(
            status_code=status_code,
            content=error_response.model_dump(mode="json"),
        )


def setup_exception_handlers(app: FastAPI) -> None:
    """Set up FastAPI exception handlers."""
    from fastapi.exceptions import RequestValidationError
    from starlette.exceptions import HTTPException

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        """Handle Pydantic validation errors."""
        errors = []
        for error in exc.errors():
            loc = " -> ".join(str(part) for part in error["loc"])
            errors.append(f"{loc}: {error['msg']}")

        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error_code="VALIDATION_ERROR",
                message="Request validation failed",
                hint="Check the request body fields and types.",
                detail="; ".join(errors),
                path=request.url.path,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """Handle HTTP exceptions with standardized format."""
        # Infer error code from status
        error_code = _infer_error_code(exc.status_code, exc.detail or "")
        hint = _get_hint(error_code, exc.status_code)

        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error_code=error_code,
                message=exc.detail or "An error occurred",
                hint=hint,
                path=request.url.path,
            ).model_dump(mode="json"),
        )


def _infer_error_code(status_code: int, detail: str) -> str:
    """Infer a machine-readable error code from HTTPException detail."""
    detail_lower = detail.lower()

    if status_code == 404:
        if "invoice" in detail_lower:
            return "INVOICE_NOT_FOUND"
        if "document" in detail_lower:
            return "DOCUMENT_NOT_FOUND"
        if "session" in detail_lower:
            return "SESSION_NOT_FOUND"
        if "material" in detail_lower:
            return "MATERIAL_NOT_FOUND"
        if "reminder" in detail_lower:
            return "REMINDER_NOT_FOUND"
        if "company" in detail_lower:
            return "COMPANY_DOCUMENT_NOT_FOUND"
        return "NOT_FOUND"

    if status_code == 400:
        return "BAD_REQUEST"

    if status_code == 422:
        return "UNPROCESSABLE_ENTITY"

    return "HTTP_ERROR"
