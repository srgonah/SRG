"""
Error handling middleware.
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
    StorageError,
    ValidationError,
)

logger = get_logger(__name__)


# Map exceptions to HTTP status codes
EXCEPTION_STATUS_MAP = {
    ValidationError: status.HTTP_400_BAD_REQUEST,
    ParserError: status.HTTP_422_UNPROCESSABLE_ENTITY,
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


class ErrorHandlerMiddleware(BaseHTTPMiddleware):
    """
    Global error handling middleware.

    Converts exceptions to JSON error responses.
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
        """Convert exception to JSON response."""
        # Get status code
        status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

        for exc_type, code in EXCEPTION_STATUS_MAP.items():
            if isinstance(exc, exc_type):
                status_code = code
                break

        # Get error code
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
        error_response = ErrorResponse(
            error=str(exc),
            code=error_code,
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=ErrorResponse(
                error="Validation error",
                detail="; ".join(errors),
                code="ValidationError",
                path=request.url.path,
            ).model_dump(mode="json"),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(
        request: Request,
        exc: HTTPException,
    ) -> JSONResponse:
        """Handle HTTP exceptions."""
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=exc.detail,
                code="HTTPException",
                path=request.url.path,
            ).model_dump(mode="json"),
        )
