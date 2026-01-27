"""
LLM provider factory.

Creates appropriate provider based on configuration.
"""

from typing import Any

from src.config import get_logger, get_settings
from src.core.interfaces import ILLMProvider, IVisionProvider

logger = get_logger(__name__)


def get_llm_provider(
    provider_type: str | None = None,
    model_path: str | None = None,
) -> ILLMProvider:
    """
    Get an LLM provider instance.

    Args:
        provider_type: "ollama" or "llama_cpp" (default from settings)
        model_path: Optional model path for llama_cpp

    Returns:
        ILLMProvider instance
    """
    settings = get_settings()
    provider_type = provider_type or settings.llm.provider

    if provider_type == "ollama":
        from src.infrastructure.llm.ollama import get_ollama_provider

        return get_ollama_provider()

    elif provider_type == "llama_cpp":
        from src.infrastructure.llm.llama_cpp import get_llama_cpp_provider

        return get_llama_cpp_provider(model_path)

    else:
        raise ValueError(f"Unknown LLM provider: {provider_type}")


def get_vision_provider() -> IVisionProvider:
    """
    Get a vision provider instance.

    Currently only Ollama supports vision.
    """
    settings = get_settings()

    if settings.llm.provider == "ollama":
        from src.infrastructure.llm.ollama import get_ollama_provider

        return get_ollama_provider()

    # Fallback to Ollama for vision even if using llama_cpp for text
    from src.infrastructure.llm.ollama import get_ollama_provider

    return get_ollama_provider()


async def check_llm_health() -> dict[str, Any]:
    """
    Check health of all configured LLM providers.

    Returns:
        Dict with health status for each provider
    """
    results = {}

    settings = get_settings()

    # Check configured provider
    try:
        provider = get_llm_provider()
        health = await provider.check_health()
        results["primary"] = health.__dict__
    except Exception as e:
        results["primary"] = {
            "available": False,
            "provider": settings.llm.provider,
            "error": str(e),
        }

    # Check vision provider if different
    if settings.llm.provider != "ollama":
        try:
            vision = get_vision_provider()
            health = await vision.check_health()
            results["vision"] = health.__dict__
        except Exception as e:
            results["vision"] = {
                "available": False,
                "provider": "ollama",
                "error": str(e),
            }

    return results
