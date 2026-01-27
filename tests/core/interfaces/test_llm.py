"""Unit tests for LLM interface dataclasses and enums."""

import pytest

from src.core.interfaces.llm import (
    HealthStatus,
    IEmbeddingProvider,
    ILLMProvider,
    IVisionProvider,
    LLMProvider,
    LLMResponse,
    VisionResponse,
)


class TestLLMProvider:
    """Tests for LLMProvider enum."""

    def test_ollama_value(self):
        assert LLMProvider.OLLAMA.value == "ollama"

    def test_llama_cpp_value(self):
        assert LLMProvider.LLAMA_CPP.value == "llama_cpp"


class TestLLMResponse:
    """Tests for LLMResponse dataclass."""

    def test_required_fields(self):
        response = LLMResponse(text="Hello, world!", model="llama3.1:8b")
        assert response.text == "Hello, world!"
        assert response.model == "llama3.1:8b"

    def test_default_values(self):
        response = LLMResponse(text="Test", model="test-model")
        assert response.done is True
        assert response.done_reason is None
        assert response.prompt_tokens == 0
        assert response.completion_tokens == 0
        assert response.total_tokens == 0
        assert response.error is None

    def test_with_token_counts(self):
        response = LLMResponse(
            text="Generated text",
            model="llama3.1:8b",
            done=True,
            done_reason="stop",
            prompt_tokens=50,
            completion_tokens=100,
            total_tokens=150,
        )
        assert response.prompt_tokens == 50
        assert response.completion_tokens == 100
        assert response.total_tokens == 150
        assert response.done_reason == "stop"

    def test_with_error(self):
        response = LLMResponse(
            text="",
            model="llama3.1:8b",
            done=False,
            error="Connection timeout",
        )
        assert response.error == "Connection timeout"
        assert response.done is False


class TestVisionResponse:
    """Tests for VisionResponse dataclass."""

    def test_required_fields(self):
        response = VisionResponse(text="Image description", model="llava:13b")
        assert response.text == "Image description"
        assert response.model == "llava:13b"

    def test_default_values(self):
        response = VisionResponse(text="Test", model="test-model")
        assert response.image_tokens == 0
        assert response.error is None

    def test_with_image_tokens(self):
        response = VisionResponse(
            text="Invoice shows...",
            model="llava:13b",
            image_tokens=576,
        )
        assert response.image_tokens == 576


class TestHealthStatus:
    """Tests for HealthStatus dataclass."""

    def test_required_fields(self):
        status = HealthStatus(available=True, provider="ollama")
        assert status.available is True
        assert status.provider == "ollama"

    def test_default_values(self):
        status = HealthStatus(available=False, provider="ollama")
        assert status.model is None
        assert status.error is None
        assert status.response_time_ms is None

    def test_healthy_status(self):
        status = HealthStatus(
            available=True,
            provider="ollama",
            model="llama3.1:8b",
            response_time_ms=150.5,
        )
        assert status.available is True
        assert status.model == "llama3.1:8b"
        assert status.response_time_ms == 150.5

    def test_unhealthy_status(self):
        status = HealthStatus(
            available=False,
            provider="ollama",
            error="Connection refused",
        )
        assert status.available is False
        assert status.error == "Connection refused"


class TestILLMProviderInterface:
    """Tests for ILLMProvider abstract interface."""

    def test_is_abstract_class(self):
        """Verify ILLMProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            ILLMProvider()

    def test_abstract_methods_defined(self):
        """Verify all required abstract methods are defined."""
        abstract_methods = {
            "generate",
            "generate_stream",
            "chat",
            "check_health",
            "is_available",
        }
        actual_methods = set(ILLMProvider.__abstractmethods__)
        assert abstract_methods == actual_methods


class TestIVisionProviderInterface:
    """Tests for IVisionProvider abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IVisionProvider()

    def test_abstract_methods_defined(self):
        abstract_methods = {
            "analyze_image",
            "analyze_image_base64",
            "check_health",
        }
        actual_methods = set(IVisionProvider.__abstractmethods__)
        assert abstract_methods == actual_methods


class TestIEmbeddingProviderInterface:
    """Tests for IEmbeddingProvider abstract interface."""

    def test_is_abstract_class(self):
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            IEmbeddingProvider()

    def test_abstract_methods_defined(self):
        abstract_methods = {
            "embed_single",
            "embed_batch",
            "get_dimension",
            "is_loaded",
        }
        actual_methods = set(IEmbeddingProvider.__abstractmethods__)
        assert abstract_methods == actual_methods
