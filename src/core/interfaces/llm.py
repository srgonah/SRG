"""
Abstract interfaces for LLM and embedding providers.

Defines contracts that Ollama and llama-cpp implementations must fulfill.
"""

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass
from enum import Enum

import numpy as np


class LLMProvider(str, Enum):
    """Supported LLM provider types."""

    OLLAMA = "ollama"
    LLAMA_CPP = "llama_cpp"


@dataclass
class LLMResponse:
    """Response from LLM generation."""

    text: str
    model: str
    done: bool = True
    done_reason: str | None = None
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    error: str | None = None


@dataclass
class VisionResponse:
    """Response from vision model."""

    text: str
    model: str
    image_tokens: int = 0
    error: str | None = None


@dataclass
class HealthStatus:
    """LLM provider health status."""

    available: bool
    provider: str
    model: str | None = None
    error: str | None = None
    response_time_ms: float | None = None


class ILLMProvider(ABC):
    """
    Abstract interface for LLM providers.

    Implementations: OllamaProvider, LlamaCppProvider
    """

    @abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """
        Generate text completion.

        Args:
            prompt: User prompt
            system_prompt: Optional system prompt
            temperature: Sampling temperature (0-2)
            max_tokens: Maximum tokens to generate
            stop: Stop sequences

        Returns:
            LLMResponse with generated text
        """
        pass

    @abstractmethod
    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[str]:
        """
        Generate text with streaming output.

        Yields:
            Text chunks as they're generated
        """
        pass

    @abstractmethod
    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LLMResponse:
        """
        Chat completion with message history.

        Args:
            messages: List of {"role": "user"|"assistant"|"system", "content": "..."}
            temperature: Sampling temperature
            max_tokens: Maximum tokens to generate

        Returns:
            LLMResponse with assistant reply
        """
        pass

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """
        Check if the LLM provider is available.

        Returns:
            HealthStatus with availability info
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        Synchronous availability check (cached).

        Returns:
            True if provider is ready
        """
        pass


class IVisionProvider(ABC):
    """
    Abstract interface for vision/multimodal providers.

    Used for extracting text from invoice images.
    """

    @abstractmethod
    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        max_tokens: int = 2048,
    ) -> VisionResponse:
        """
        Analyze an image with a text prompt.

        Args:
            image_path: Path to image file
            prompt: Instruction prompt for analysis
            max_tokens: Maximum tokens to generate

        Returns:
            VisionResponse with extracted text
        """
        pass

    @abstractmethod
    async def analyze_image_base64(
        self,
        image_data: str,
        prompt: str,
        max_tokens: int = 2048,
    ) -> VisionResponse:
        """
        Analyze a base64-encoded image.

        Args:
            image_data: Base64-encoded image data
            prompt: Instruction prompt
            max_tokens: Maximum tokens to generate

        Returns:
            VisionResponse with extracted text
        """
        pass

    @abstractmethod
    async def check_health(self) -> HealthStatus:
        """Check if vision model is available."""
        pass


class IEmbeddingProvider(ABC):
    """
    Abstract interface for embedding providers.

    Used for generating vector embeddings for search.
    """

    @abstractmethod
    def embed_single(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Input text

        Returns:
            Embedding vector as numpy array
        """
        pass

    @abstractmethod
    def embed_batch(
        self,
        texts: list[str],
        batch_size: int = 32,
    ) -> np.ndarray:
        """
        Generate embeddings for multiple texts.

        Args:
            texts: List of input texts
            batch_size: Processing batch size

        Returns:
            Embedding matrix (n_texts x dimension)
        """
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """
        Get the embedding dimension.

        Returns:
            Embedding vector dimension
        """
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """
        Check if the embedding model is loaded.

        Returns:
            True if model is ready
        """
        pass
