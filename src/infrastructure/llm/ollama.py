"""
Ollama LLM provider implementation.

Provides HTTP client for Ollama API with chat and vision capabilities.
"""

import base64
import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx

from src.config import get_logger, get_settings
from src.core.exceptions import (
    LLMResponseError,
    LLMUnavailableError,
    ModelNotFoundError,
)
from src.core.interfaces import (
    HealthStatus,
    ILLMProvider,
    IVisionProvider,
    LLMResponse,
    VisionResponse,
)
from src.infrastructure.llm.base import BaseLLMProvider

logger = get_logger(__name__)


class OllamaProvider(BaseLLMProvider, ILLMProvider, IVisionProvider):
    """
    Ollama HTTP API provider.

    Supports text generation, chat, and vision capabilities.
    """

    def __init__(self):
        super().__init__()
        settings = get_settings()
        self.host = settings.llm.host
        self.model = settings.llm.model_name
        self.vision_model = settings.llm.vision_model
        self.timeout = settings.llm.timeout
        self.max_tokens = settings.llm.max_tokens
        self.temperature = settings.llm.temperature

    async def _make_request(
        self,
        endpoint: str,
        payload: dict,
        timeout: int | None = None,
    ) -> dict:
        """Make HTTP request to Ollama API."""
        url = f"{self.host}/{endpoint}"
        timeout = timeout or self.timeout

        async with httpx.AsyncClient(timeout=timeout + 5) as client:
            response = await client.post(url, json=payload, timeout=timeout)

            if response.status_code == 404:
                model = payload.get("model", "unknown")
                raise ModelNotFoundError(model, "ollama")

            if response.status_code != 200:
                error_text = response.text[:200]
                raise LLMUnavailableError("ollama", f"HTTP {response.status_code}: {error_text}")

            return response.json()

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

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        if stop:
            payload["options"]["stop"] = stop

        async def _do_generate():
            start_time = time.time()
            result = await self._make_request("api/generate", payload)
            elapsed = time.time() - start_time

            response_text = result.get("response", "")
            if not response_text.strip():
                raise LLMResponseError(
                    f"Empty response (done_reason={result.get('done_reason')})",
                    response_text,
                )

            logger.info(
                "ollama_generate",
                model=self.model,
                prompt_len=len(prompt),
                response_len=len(response_text),
                elapsed_ms=int(elapsed * 1000),
            )

            return LLMResponse(
                text=response_text,
                model=self.model,
                done=result.get("done", True),
                done_reason=result.get("done_reason"),
            )

        return await self._with_resilience(_do_generate)

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

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        if system_prompt:
            payload["system"] = system_prompt

        url = f"{self.host}/api/generate"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    raise LLMUnavailableError("ollama", f"HTTP {response.status_code}")

                async for line in response.aiter_lines():
                    if line:
                        try:
                            import json

                            data = json.loads(line)
                            if "response" in data:
                                yield data["response"]
                        except json.JSONDecodeError:
                            continue

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = None,
        max_tokens: int = None,
    ) -> LLMResponse:
        """Chat completion with message history."""
        temperature = temperature if temperature is not None else self.temperature
        max_tokens = max_tokens or self.max_tokens

        # Convert to Ollama chat format
        ollama_messages = []
        for msg in messages:
            ollama_messages.append(
                {
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                }
            )

        payload = {
            "model": self.model,
            "messages": ollama_messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }

        async def _do_chat():
            start_time = time.time()
            result = await self._make_request("api/chat", payload)
            elapsed = time.time() - start_time

            message = result.get("message", {})
            response_text = message.get("content", "")

            if not response_text.strip():
                raise LLMResponseError("Empty chat response", response_text)

            logger.info(
                "ollama_chat",
                model=self.model,
                messages=len(messages),
                response_len=len(response_text),
                elapsed_ms=int(elapsed * 1000),
            )

            return LLMResponse(
                text=response_text,
                model=self.model,
                done=result.get("done", True),
            )

        return await self._with_resilience(_do_chat)

    async def check_health(self) -> HealthStatus:
        """Check if Ollama is available."""
        start_time = time.time()

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                # Check if Ollama is running
                response = await client.get(f"{self.host}/api/tags")

                if response.status_code != 200:
                    status = HealthStatus(
                        available=False,
                        provider="ollama",
                        error=f"HTTP {response.status_code}",
                    )
                    self._update_health_cache(status)
                    return status

                # Check if model is available
                data = response.json()
                models = [m.get("name", "") for m in data.get("models", [])]

                if self.model not in models and not any(self.model in m for m in models):
                    status = HealthStatus(
                        available=False,
                        provider="ollama",
                        model=self.model,
                        error=f"Model '{self.model}' not installed. Run: ollama pull {self.model}",
                    )
                    self._update_health_cache(status)
                    return status

                elapsed = (time.time() - start_time) * 1000
                status = HealthStatus(
                    available=True,
                    provider="ollama",
                    model=self.model,
                    response_time_ms=elapsed,
                )
                self._update_health_cache(status)
                return status

        except httpx.ConnectError:
            status = HealthStatus(
                available=False,
                provider="ollama",
                error=f"Cannot connect to Ollama at {self.host}. Is 'ollama serve' running?",
            )
            self._update_health_cache(status)
            return status

        except Exception as e:
            status = HealthStatus(
                available=False,
                provider="ollama",
                error=str(e),
            )
            self._update_health_cache(status)
            return status

    # Vision provider methods

    async def analyze_image(
        self,
        image_path: str,
        prompt: str,
        max_tokens: int = 2048,
    ) -> VisionResponse:
        """Analyze an image with a text prompt."""
        path = Path(image_path)
        if not path.exists():
            return VisionResponse(
                text="",
                model=self.vision_model,
                error=f"Image file not found: {image_path}",
            )

        # Read and encode image
        with open(path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")

        return await self.analyze_image_base64(image_data, prompt, max_tokens)

    async def analyze_image_base64(
        self,
        image_data: str,
        prompt: str,
        max_tokens: int = 2048,
    ) -> VisionResponse:
        """Analyze a base64-encoded image."""
        payload = {
            "model": self.vision_model,
            "prompt": prompt,
            "images": [image_data],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
            },
        }

        async def _do_vision():
            start_time = time.time()
            result = await self._make_request("api/generate", payload, timeout=180)
            elapsed = time.time() - start_time

            response_text = result.get("response", "")

            logger.info(
                "ollama_vision",
                model=self.vision_model,
                prompt_len=len(prompt),
                response_len=len(response_text),
                elapsed_ms=int(elapsed * 1000),
            )

            return VisionResponse(
                text=response_text,
                model=self.vision_model,
            )

        try:
            return await self._with_resilience(_do_vision)
        except Exception as e:
            return VisionResponse(
                text="",
                model=self.vision_model,
                error=str(e),
            )


# Singleton
_ollama_provider: OllamaProvider | None = None


def get_ollama_provider() -> OllamaProvider:
    """Get or create the Ollama provider singleton."""
    global _ollama_provider
    if _ollama_provider is None:
        _ollama_provider = OllamaProvider()
    return _ollama_provider
