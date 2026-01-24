"""
llama-cpp-python LLM provider implementation.

Provides direct local inference using llama-cpp-python bindings.
"""

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path

from src.config import get_logger, get_settings
from src.core.exceptions import LLMUnavailableError
from src.core.interfaces import HealthStatus, ILLMProvider, LLMResponse
from src.infrastructure.llm.base import BaseLLMProvider, format_chat_messages

logger = get_logger(__name__)

# Try to import llama-cpp-python
try:
    from llama_cpp import Llama

    LLAMA_CPP_AVAILABLE = True
except ImportError:
    LLAMA_CPP_AVAILABLE = False
    Llama = None


class LlamaCppProvider(BaseLLMProvider, ILLMProvider):
    """
    llama-cpp-python local inference provider.

    Runs models directly using llama.cpp bindings.
    """

    def __init__(self, model_path: str | None = None):
        super().__init__()

        if not LLAMA_CPP_AVAILABLE:
            raise ImportError(
                "llama-cpp-python not installed. Install with: pip install llama-cpp-python"
            )

        settings = get_settings()
        self.model_path = model_path or settings.llm.model_name
        self.max_tokens = settings.llm.max_tokens
        self.temperature = settings.llm.temperature

        self._model: Llama | None = None
        self._model_loaded = False

    def _load_model(self) -> None:
        """Load the model if not already loaded."""
        if self._model is not None:
            return

        path = Path(self.model_path)
        if not path.exists():
            raise LLMUnavailableError(
                "llama_cpp",
                f"Model file not found: {self.model_path}",
            )

        logger.info("loading_llama_model", path=str(path))

        self._model = Llama(
            model_path=str(path),
            n_ctx=4096,
            n_batch=512,
            n_gpu_layers=-1,  # Use GPU if available
            verbose=False,
        )
        self._model_loaded = True

        logger.info("llama_model_loaded", path=str(path))

    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = None,
        max_tokens: int = None,
        stop: list[str] | None = None,
    ) -> LLMResponse:
        """Generate text completion."""
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        async def _do_generate():
            # Run in thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(
                None,
                self._generate_sync,
                full_prompt,
                temperature,
                max_tokens,
                stop,
            )

        return await self._with_resilience(_do_generate)

    def _generate_sync(
        self,
        prompt: str,
        temperature: float,
        max_tokens: int,
        stop: list[str] | None,
    ) -> LLMResponse:
        """Synchronous generation (runs in thread pool)."""
        self._load_model()

        start_time = time.time()

        output = self._model(
            prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            stop=stop or [],
            echo=False,
        )

        elapsed = time.time() - start_time

        response_text = output["choices"][0]["text"]
        finish_reason = output["choices"][0].get("finish_reason")

        logger.info(
            "llama_cpp_generate",
            prompt_len=len(prompt),
            response_len=len(response_text),
            elapsed_ms=int(elapsed * 1000),
            finish_reason=finish_reason,
        )

        return LLMResponse(
            text=response_text,
            model=self.model_path,
            done=True,
            done_reason=finish_reason,
            prompt_tokens=output.get("usage", {}).get("prompt_tokens", 0),
            completion_tokens=output.get("usage", {}).get("completion_tokens", 0),
        )

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = None,
        max_tokens: int = None,
    ) -> AsyncIterator[str]:
        """Generate text with streaming output."""
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        full_prompt = prompt
        if system_prompt:
            full_prompt = f"{system_prompt}\n\n{prompt}"

        self._load_model()

        # Run streaming in thread pool
        loop = asyncio.get_event_loop()
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        def _stream_sync():
            for output in self._model(
                full_prompt,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True,
            ):
                text = output["choices"][0]["text"]
                asyncio.run_coroutine_threadsafe(queue.put(text), loop)

            asyncio.run_coroutine_threadsafe(queue.put(None), loop)

        # Start streaming in background
        loop.run_in_executor(None, _stream_sync)

        # Yield tokens as they arrive
        while True:
            token = await queue.get()
            if token is None:
                break
            yield token

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> LLMResponse:
        """Chat completion with message history."""
        # Convert messages to prompt format
        prompt = format_chat_messages(messages)
        prompt += "\nAssistant:"

        return await self.generate(
            prompt,
            temperature=temperature,
            max_tokens=max_tokens,
        )

    async def check_health(self) -> HealthStatus:
        """Check if llama-cpp is available."""
        if not LLAMA_CPP_AVAILABLE:
            return HealthStatus(
                available=False,
                provider="llama_cpp",
                error="llama-cpp-python not installed",
            )

        path = Path(self.model_path)
        if not path.exists():
            return HealthStatus(
                available=False,
                provider="llama_cpp",
                model=self.model_path,
                error=f"Model file not found: {self.model_path}",
            )

        # Try to load model
        try:
            start_time = time.time()
            self._load_model()
            elapsed = (time.time() - start_time) * 1000

            return HealthStatus(
                available=True,
                provider="llama_cpp",
                model=self.model_path,
                response_time_ms=elapsed,
            )
        except Exception as e:
            return HealthStatus(
                available=False,
                provider="llama_cpp",
                error=str(e),
            )

    def is_available(self) -> bool:
        """Check availability synchronously."""
        if not LLAMA_CPP_AVAILABLE:
            return False

        if self.circuit_breaker.is_open:
            return False

        return Path(self.model_path).exists()


# Singleton
_llama_cpp_provider: LlamaCppProvider | None = None


def get_llama_cpp_provider(model_path: str | None = None) -> LlamaCppProvider:
    """Get or create the llama-cpp provider singleton."""
    global _llama_cpp_provider
    if _llama_cpp_provider is None:
        _llama_cpp_provider = LlamaCppProvider(model_path)
    return _llama_cpp_provider
