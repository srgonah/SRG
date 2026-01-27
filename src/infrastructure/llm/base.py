"""
Base LLM provider with retry and circuit breaker patterns.

Provides resilience patterns for all LLM implementations.
"""

import time
from abc import ABC
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar, cast

from tenacity import (
    RetryCallState,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import get_logger, get_settings
from src.core.exceptions import (
    CircuitBreakerOpenError,
    LLMTimeoutError,
    LLMUnavailableError,
)
from src.core.interfaces import HealthStatus, ILLMProvider

logger = get_logger(__name__)

T = TypeVar("T")


@dataclass
class CircuitBreakerState:
    """State for circuit breaker pattern."""

    failures: int = 0
    last_failure_time: float = 0.0
    is_open: bool = False
    cooldown_seconds: int = 60
    failure_threshold: int = 3

    def record_failure(self) -> None:
        """Record a failure and potentially open the circuit."""
        self.failures += 1
        self.last_failure_time = time.time()

        if self.failures >= self.failure_threshold:
            self.is_open = True
            logger.warning(
                "circuit_breaker_opened",
                failures=self.failures,
                cooldown=self.cooldown_seconds,
            )

    def record_success(self) -> None:
        """Record a success and reset the circuit."""
        if self.is_open:
            logger.info("circuit_breaker_closed")
        self.failures = 0
        self.is_open = False

    def check(self) -> None:
        """
        Check if circuit allows requests.

        Raises CircuitBreakerOpenError if circuit is open and cooldown not elapsed.
        """
        if not self.is_open:
            return

        elapsed = time.time() - self.last_failure_time
        remaining = int(self.cooldown_seconds - elapsed)

        if elapsed < self.cooldown_seconds:
            raise CircuitBreakerOpenError("llm", remaining)

        # Cooldown elapsed, allow one request (half-open state)
        logger.info("circuit_breaker_half_open")

    @property
    def cooldown_remaining(self) -> int:
        """Seconds remaining in cooldown."""
        if not self.is_open:
            return 0
        elapsed = time.time() - self.last_failure_time
        return max(0, int(self.cooldown_seconds - elapsed))


class BaseLLMProvider(ILLMProvider, ABC):
    """
    Base class for LLM providers with resilience patterns.

    Provides:
    - Automatic retries with exponential backoff
    - Circuit breaker for cascading failure prevention
    - Health check caching
    """

    def __init__(self) -> None:
        settings = get_settings()
        self.circuit_breaker = CircuitBreakerState(
            failure_threshold=settings.llm.failure_threshold,
            cooldown_seconds=settings.llm.cooldown_seconds,
        )
        self._health_cache: HealthStatus | None = None
        self._health_cache_time: float = 0.0
        self._health_cache_ttl: float = 30.0  # Cache health for 30s

    def _get_retry_decorator(self) -> Any:
        """Get tenacity retry decorator with current settings."""
        settings = get_settings()
        return retry(
            stop=stop_after_attempt(settings.llm.max_retries),
            wait=wait_exponential(
                multiplier=settings.llm.retry_delay,
                min=settings.llm.retry_delay,
                max=settings.llm.retry_delay * (settings.llm.retry_multiplier**3),
            ),
            retry=retry_if_exception_type((TimeoutError, ConnectionError)),
            before_sleep=self._log_retry,
        )

    @staticmethod
    def _log_retry(retry_state: RetryCallState) -> None:
        """Log retry attempts."""
        logger.warning(
            "llm_retry",
            attempt=retry_state.attempt_number,
            error=str(retry_state.outcome.exception()) if retry_state.outcome else None,
        )

    async def _with_resilience(
        self,
        operation: Callable[..., Awaitable[T]],
        *args: Any,
        **kwargs: Any,
    ) -> T:
        """
        Execute operation with retry and circuit breaker.

        Args:
            operation: Async callable to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result of operation

        Raises:
            CircuitBreakerOpenError: If circuit is open
            LLMTimeoutError: If operation times out
            LLMUnavailableError: If provider is unavailable
        """
        # Check circuit breaker
        self.circuit_breaker.check()

        try:
            # Execute with retry
            retry_decorator = self._get_retry_decorator()
            result = await retry_decorator(operation)(*args, **kwargs)

            # Success - reset circuit
            self.circuit_breaker.record_success()
            return cast(T, result)

        except TimeoutError:
            self.circuit_breaker.record_failure()
            settings = get_settings()
            raise LLMTimeoutError(settings.llm.timeout)

        except (ConnectionError, OSError) as e:
            self.circuit_breaker.record_failure()
            raise LLMUnavailableError(self.__class__.__name__, str(e))

        except Exception as e:
            # Don't trip circuit for other errors (e.g., invalid response)
            logger.error("llm_error", error=str(e), error_type=type(e).__name__)
            raise

    def is_available(self) -> bool:
        """
        Synchronous availability check with caching.

        Uses cached health status to avoid blocking calls.
        """
        if self.circuit_breaker.is_open:
            return False

        # Check cache
        now = time.time()
        if self._health_cache and (now - self._health_cache_time) < self._health_cache_ttl:
            return self._health_cache.available

        return True  # Optimistic - actual check happens async

    def _update_health_cache(self, status: HealthStatus) -> None:
        """Update the health cache."""
        self._health_cache = status
        self._health_cache_time = time.time()


def format_chat_messages(messages: list[dict[str, str]]) -> str:
    """
    Format chat messages into a single prompt string.

    Args:
        messages: List of {"role": "user"|"assistant"|"system", "content": "..."}

    Returns:
        Formatted prompt string
    """
    parts = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "system":
            parts.append(f"System: {content}\n")
        elif role == "user":
            parts.append(f"User: {content}\n")
        elif role == "assistant":
            parts.append(f"Assistant: {content}\n")

    return "\n".join(parts)
