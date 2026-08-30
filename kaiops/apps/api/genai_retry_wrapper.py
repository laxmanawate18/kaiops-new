"""
Retry wrapper for Google GenAI calls.

Provides `with_genai_retry`, a decorator that transparently retries transient
GenAI API failures (429 RESOURCE_EXHAUSTED / "overload", 503 UNAVAILABLE) with
exponential backoff. Non-transient exceptions are re-raised immediately.
"""

import asyncio
import functools
import logging
import random
from typing import Any, Awaitable, Callable

logger = logging.getLogger(__name__)

# Transient error markers worth retrying.
_TRANSIENT_MARKERS = (
    "429",
    "resource_exhausted",
    "resourceexhausted",
    "overload",
    "overloaded",
    "503",
    "unavailable",
    "internal error",
    "deadline exceeded",
    "connection reset",
    "connection aborted",
    "eof occurred",
    "timed out",
)

# Default retry policy
_MAX_RETRIES = 3
_BASE_DELAY = 2.0  # seconds
_MAX_DELAY = 30.0  # seconds


def _is_transient(exc: BaseException) -> bool:
    """Heuristically decide whether an exception is a transient GenAI failure."""
    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
        return True

    # google.genai / google.api_core errors expose code/status attributes
    status_code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if status_code in (429, 500, 503, 504):
        return True
    grpc_status = getattr(exc, "status", None)
    if grpc_status is not None:
        name = getattr(grpc_status, "name", str(grpc_status)).lower()
        if name in ("resource_exhausted", "unavailable", "deadline_exceeded", "internal"):
            return True

    text = str(exc).lower()
    return any(marker in text for marker in _TRANSIENT_MARKERS)


def with_genai_retry(func=None, *, max_retries: int = _MAX_RETRIES, base_delay: float = _BASE_DELAY, max_delay: float = _MAX_DELAY):
    """
    Decorator for async functions that call the GenAI backend.

    Supports both usages:
        @with_genai_retry
        async def fn(...): ...

        @with_genai_retry(max_retries=5)
        async def fn(...): ...

    Retries the wrapped coroutine on transient errors (rate limits, overload,
    unavailability) using exponential backoff with jitter.
    """

    def decorator(fn: Callable[..., Awaitable[Any]]) -> Callable[..., Awaitable[Any]]:
        @functools.wraps(fn)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exc: BaseException | None = None
            for attempt in range(max_retries + 1):
                try:
                    return await fn(*args, **kwargs)
                except Exception as exc:
                    last_exc = exc
                    if attempt >= max_retries or not _is_transient(exc):
                        raise
                    delay = min(max_delay, base_delay * (2**attempt)) + random.uniform(0, 1)
                    logger.warning(
                        "[RETRY] Transient GenAI error on %s (attempt %d/%d): %s — retrying in %.1fs",
                        getattr(fn, "__name__", fn),
                        attempt + 1,
                        max_retries + 1,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
            raise last_exc  # pragma: no cover - defensive

        return wrapper

    if func is not None and callable(func):
        # Used as a bare decorator: @with_genai_retry
        return decorator(func)

    return decorator
