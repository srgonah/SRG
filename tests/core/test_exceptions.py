"""Unit tests for domain exceptions."""

import pytest

from src.core.exceptions import (
    AuditError,
    AuditFailedError,
    ChatError,
    CircuitBreakerOpenError,
    ConfigurationError,
    DatabaseError,
    DocumentNotFoundError,
    DuplicateDocumentError,
    EmbeddingError,
    ExtractionError,
    FileTooLargeError,
    IndexingError,
    IndexNotReadyError,
    InvoiceNotFoundError,
    LLMError,
    LLMResponseError,
    LLMTimeoutError,
    LLMUnavailableError,
    ModelNotFoundError,
    ParserError,
    ParsingFailedError,
    SearchError,
    SessionNotFoundError,
    SRGError,
    StorageError,
    TemplateNotFoundError,
    UnsupportedFileTypeError,
    ValidationError,
)


class TestSRGError:
    """Tests for base SRGError exception."""

    def test_basic_initialization(self):
        error = SRGError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.message == "Something went wrong"
        assert error.code == "SRGError"
        assert error.details == {}

    def test_with_custom_code(self):
        error = SRGError("Error message", code="CUSTOM_ERROR")
        assert error.code == "CUSTOM_ERROR"

    def test_with_details(self):
        error = SRGError("Error", details={"key": "value", "count": 5})
        assert error.details["key"] == "value"
        assert error.details["count"] == 5

    def test_to_dict(self):
        error = SRGError(
            "Test error",
            code="TEST_CODE",
            details={"extra": "info"},
        )
        result = error.to_dict()
        assert result == {
            "error": "TEST_CODE",
            "message": "Test error",
            "details": {"extra": "info"},
        }

    def test_inherits_from_exception(self):
        error = SRGError("Test")
        assert isinstance(error, Exception)


class TestStorageErrors:
    """Tests for storage-related exceptions."""

    def test_storage_error_inheritance(self):
        error = StorageError("Storage failed")
        assert isinstance(error, SRGError)

    def test_document_not_found_error(self):
        error = DocumentNotFoundError(doc_id=123)
        assert error.code == "DOCUMENT_NOT_FOUND"
        assert "123" in error.message
        assert error.details["doc_id"] == 123

    def test_invoice_not_found_error(self):
        error = InvoiceNotFoundError(invoice_id=456)
        assert error.code == "INVOICE_NOT_FOUND"
        assert "456" in error.message
        assert error.details["invoice_id"] == 456

    def test_session_not_found_error(self):
        error = SessionNotFoundError(session_id="abc-123")
        assert error.code == "SESSION_NOT_FOUND"
        assert "abc-123" in error.message
        assert error.details["session_id"] == "abc-123"

    def test_duplicate_document_error(self):
        error = DuplicateDocumentError(
            file_hash="abc123hash",
            existing_id=789,
        )
        assert error.code == "DUPLICATE_DOCUMENT"
        assert "abc123hash" in error.message
        assert error.details["file_hash"] == "abc123hash"
        assert error.details["existing_id"] == 789

    def test_database_error(self):
        error = DatabaseError(
            operation="insert",
            error="connection refused",
        )
        assert error.code == "DATABASE_ERROR"
        assert "insert" in error.message
        assert "connection refused" in error.message
        assert error.details["operation"] == "insert"
        assert error.details["error"] == "connection refused"


class TestLLMErrors:
    """Tests for LLM-related exceptions."""

    def test_llm_error_inheritance(self):
        error = LLMError("LLM failed")
        assert isinstance(error, SRGError)

    def test_llm_unavailable_error_basic(self):
        error = LLMUnavailableError(provider="ollama")
        assert error.code == "LLM_UNAVAILABLE"
        assert "ollama" in error.message
        assert error.details["provider"] == "ollama"
        assert error.details["reason"] is None

    def test_llm_unavailable_error_with_reason(self):
        error = LLMUnavailableError(
            provider="ollama",
            reason="Connection refused",
        )
        assert "Connection refused" in error.message
        assert error.details["reason"] == "Connection refused"

    def test_llm_timeout_error(self):
        error = LLMTimeoutError(timeout=120)
        assert error.code == "LLM_TIMEOUT"
        assert "120" in error.message
        assert error.details["timeout"] == 120
        assert error.details["operation"] == "generation"

    def test_llm_timeout_error_custom_operation(self):
        error = LLMTimeoutError(timeout=60, operation="embedding")
        assert "embedding" in error.message
        assert error.details["operation"] == "embedding"

    def test_llm_response_error(self):
        error = LLMResponseError(
            reason="JSON parse failed",
            response="Invalid {json",
        )
        assert error.code == "LLM_RESPONSE_ERROR"
        assert "JSON parse failed" in error.message
        assert error.details["reason"] == "JSON parse failed"
        assert "Invalid {json" in error.details["response_preview"]

    def test_llm_response_error_truncates_preview(self):
        long_response = "x" * 500
        error = LLMResponseError(reason="test", response=long_response)
        assert len(error.details["response_preview"]) == 200

    def test_model_not_found_error(self):
        error = ModelNotFoundError(model="llama3:latest", provider="ollama")
        assert error.code == "MODEL_NOT_FOUND"
        assert "llama3:latest" in error.message
        assert "ollama" in error.message
        assert error.details["model"] == "llama3:latest"
        assert error.details["provider"] == "ollama"

    def test_circuit_breaker_open_error(self):
        error = CircuitBreakerOpenError(provider="ollama", cooldown_remaining=30)
        assert error.code == "CIRCUIT_BREAKER_OPEN"
        assert "ollama" in error.message
        assert "30" in error.message
        assert error.details["cooldown_remaining"] == 30


class TestParserErrors:
    """Tests for parser-related exceptions."""

    def test_parser_error_inheritance(self):
        error = ParserError("Parser failed")
        assert isinstance(error, SRGError)

    def test_parsing_failed_error(self):
        error = ParsingFailedError(
            filename="invoice.pdf",
            reason="No tables found",
            parser="table_aware",
        )
        assert error.code == "PARSING_FAILED"
        assert "invoice.pdf" in error.message
        assert "No tables found" in error.message
        assert error.details["filename"] == "invoice.pdf"
        assert error.details["reason"] == "No tables found"
        assert error.details["parser"] == "table_aware"

    def test_parsing_failed_error_no_parser(self):
        error = ParsingFailedError(filename="test.pdf", reason="Unknown format")
        assert error.details["parser"] is None

    def test_template_not_found_error(self):
        error = TemplateNotFoundError(company_key="ABC_COMPANY")
        assert error.code == "TEMPLATE_NOT_FOUND"
        assert "ABC_COMPANY" in error.message
        assert error.details["company_key"] == "ABC_COMPANY"

    def test_extraction_error(self):
        error = ExtractionError(
            filename="corrupted.pdf",
            reason="PDF is encrypted",
        )
        assert error.code == "EXTRACTION_ERROR"
        assert "corrupted.pdf" in error.message
        assert "PDF is encrypted" in error.message
        assert error.details["filename"] == "corrupted.pdf"


class TestSearchErrors:
    """Tests for search-related exceptions."""

    def test_search_error_inheritance(self):
        error = SearchError("Search failed")
        assert isinstance(error, SRGError)

    def test_index_not_ready_error(self):
        error = IndexNotReadyError(index_name="chunks")
        assert error.code == "INDEX_NOT_READY"
        assert "chunks" in error.message
        assert error.details["index_name"] == "chunks"

    def test_embedding_error(self):
        error = EmbeddingError(reason="Model not loaded")
        assert error.code == "EMBEDDING_ERROR"
        assert "Model not loaded" in error.message
        assert error.details["reason"] == "Model not loaded"


class TestAuditErrors:
    """Tests for audit-related exceptions."""

    def test_audit_error_inheritance(self):
        error = AuditError("Audit failed")
        assert isinstance(error, SRGError)

    def test_audit_failed_error(self):
        error = AuditFailedError(
            invoice_id=123,
            reason="LLM returned invalid JSON",
        )
        assert error.code == "AUDIT_FAILED"
        assert "123" in error.message
        assert "LLM returned invalid JSON" in error.message
        assert error.details["invoice_id"] == 123
        assert error.details["reason"] == "LLM returned invalid JSON"


class TestValidationErrors:
    """Tests for validation-related exceptions."""

    def test_validation_error_inheritance(self):
        error = ValidationError(field="email", message="Invalid format")
        assert isinstance(error, SRGError)

    def test_validation_error(self):
        error = ValidationError(
            field="invoice_date",
            message="Must be a valid date",
            value="not-a-date",
        )
        assert error.code == "VALIDATION_ERROR"
        assert "invoice_date" in error.message
        assert "Must be a valid date" in error.message
        assert error.details["field"] == "invoice_date"
        assert error.details["message"] == "Must be a valid date"
        assert error.details["value"] == "not-a-date"

    def test_validation_error_truncates_value(self):
        long_value = "x" * 200
        error = ValidationError(field="data", message="Too long", value=long_value)
        assert len(error.details["value"]) == 100

    def test_file_too_large_error(self):
        error = FileTooLargeError(
            filename="huge.pdf",
            size=100_000_000,
            max_size=50_000_000,
        )
        assert error.code == "VALIDATION_ERROR"  # Inherits from ValidationError
        assert "huge.pdf" in error.message
        assert error.details["filename"] == "huge.pdf"
        assert error.details["size"] == 100_000_000
        assert error.details["max_size"] == 50_000_000

    def test_unsupported_file_type_error(self):
        error = UnsupportedFileTypeError(
            filename="document.exe",
            extension=".exe",
            allowed=[".pdf", ".png", ".jpg"],
        )
        assert error.code == "VALIDATION_ERROR"
        assert ".exe" in error.message
        assert error.details["filename"] == "document.exe"
        assert error.details["extension"] == ".exe"
        assert error.details["allowed"] == [".pdf", ".png", ".jpg"]


class TestOtherErrors:
    """Tests for other exception types."""

    def test_chat_error(self):
        error = ChatError("Chat operation failed")
        assert isinstance(error, SRGError)
        assert error.code == "ChatError"

    def test_indexing_error(self):
        error = IndexingError("Indexing failed")
        assert isinstance(error, SRGError)
        assert error.code == "IndexingError"

    def test_configuration_error(self):
        error = ConfigurationError("Invalid configuration")
        assert isinstance(error, SRGError)
        assert error.code == "ConfigurationError"


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""

    def test_all_exceptions_inherit_from_srg_error(self):
        exceptions = [
            StorageError("test"),
            DocumentNotFoundError(1),
            InvoiceNotFoundError(1),
            SessionNotFoundError("id"),
            DuplicateDocumentError("hash", 1),
            DatabaseError("op", "err"),
            LLMError("test"),
            LLMUnavailableError("provider"),
            LLMTimeoutError(60),
            LLMResponseError("reason"),
            ModelNotFoundError("model", "provider"),
            CircuitBreakerOpenError("provider", 30),
            ParserError("test"),
            ParsingFailedError("file", "reason"),
            TemplateNotFoundError("company"),
            ExtractionError("file", "reason"),
            SearchError("test"),
            IndexNotReadyError("index"),
            EmbeddingError("reason"),
            AuditError("test"),
            AuditFailedError(1, "reason"),
            ValidationError("field", "msg"),
            FileTooLargeError("file", 100, 50),
            UnsupportedFileTypeError("file", ".exe", [".pdf"]),
            ChatError("test"),
            IndexingError("test"),
            ConfigurationError("test"),
        ]

        for exc in exceptions:
            assert isinstance(exc, SRGError), f"{type(exc).__name__} should inherit from SRGError"
            assert hasattr(exc, "to_dict"), f"{type(exc).__name__} should have to_dict method"


class TestExceptionCatchability:
    """Tests for catching exceptions by type."""

    def test_catch_storage_errors(self):
        """All storage errors should be catchable by StorageError."""
        storage_errors = [
            DocumentNotFoundError(1),
            InvoiceNotFoundError(1),
            SessionNotFoundError("id"),
            DuplicateDocumentError("hash", 1),
            DatabaseError("op", "err"),
        ]
        for exc in storage_errors:
            try:
                raise exc
            except StorageError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{type(exc).__name__} should be catchable by StorageError")

    def test_catch_llm_errors(self):
        """All LLM errors should be catchable by LLMError."""
        llm_errors = [
            LLMUnavailableError("provider"),
            LLMTimeoutError(60),
            LLMResponseError("reason"),
            ModelNotFoundError("model", "provider"),
            CircuitBreakerOpenError("provider", 30),
        ]
        for exc in llm_errors:
            try:
                raise exc
            except LLMError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{type(exc).__name__} should be catchable by LLMError")

    def test_catch_parser_errors(self):
        """All parser errors should be catchable by ParserError."""
        parser_errors = [
            ParsingFailedError("file", "reason"),
            TemplateNotFoundError("company"),
            ExtractionError("file", "reason"),
        ]
        for exc in parser_errors:
            try:
                raise exc
            except ParserError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{type(exc).__name__} should be catchable by ParserError")

    def test_catch_validation_errors(self):
        """All validation errors should be catchable by ValidationError."""
        validation_errors = [
            FileTooLargeError("file", 100, 50),
            UnsupportedFileTypeError("file", ".exe", [".pdf"]),
        ]
        for exc in validation_errors:
            try:
                raise exc
            except ValidationError:
                pass  # Expected
            except Exception:
                pytest.fail(f"{type(exc).__name__} should be catchable by ValidationError")
