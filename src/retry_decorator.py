"""
Retry decorator with exponential backoff for resilient API operations.

This module provides a decorator factory that wraps functions with automatic
retry logic, implementing exponential backoff to handle transient failures
such as network timeouts, rate limiting, or temporary service unavailability.

Architecture Decision - Why Exponential Backoff?
    Exponential backoff prevents thundering herd problems when multiple
    clients retry simultaneously. It also respects API rate limits by
    gradually increasing delays between retry attempts.

Example:
    >>> from src.retry_decorator import retry
    >>>
    >>> @retry(max_attempts=3, delay=1, backoff=2)
    ... def fetch_data():
    ...     return api.get("/data")  # Retries on failure
    >>>
    >>> # First failure: wait 1s, second: wait 2s, third: raise exception

Type Parameters:
    F: Callable type that the decorator wraps.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable, TypeVar, cast

logger = logging.getLogger(__name__)

# Type variable for preserving the signature of decorated functions
F = TypeVar("F", bound=Callable[..., Any])


def retry(
    max_attempts: int = 3,
    delay: float = 5.0,
    backoff: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[F], F]:
    """
    Decorator factory that adds retry logic with exponential backoff to functions.

    This decorator wraps a function so that if it raises an exception, it will
    be retried up to `max_attempts` times with exponentially increasing delays
    between attempts. This is particularly useful for network operations that
    may fail transiently.

    Args:
        max_attempts: Maximum number of times to attempt the function call.
            After this many failures, the last exception is re-raised.
            Default: 3 (initial attempt + 2 retries).
        delay: Initial delay in seconds between retry attempts.
            Default: 5.0 seconds.
        backoff: Multiplier applied to delay after each failed attempt.
            For example, with delay=5 and backoff=2:
            - 1st retry: wait 5s
            - 2nd retry: wait 10s
            - 3rd retry: wait 20s
            Default: 2.0 (exponential).
        exceptions: Tuple of exception types to catch and retry on.
            Other exceptions will propagate immediately.
            Default: (Exception,) - catches all exceptions.

    Returns:
        A decorator function that wraps the target function with retry logic.

    Raises:
        Exception: The last exception raised by the wrapped function after
            all retry attempts are exhausted.

    Example:
        >>> @retry(max_attempts=3, delay=1, backoff=2)
        ... def unstable_api_call() -> dict:
        ...     # This will retry up to 3 times on failure
        ...     response = requests.get("https://api.example.com/data")
        ...     response.raise_for_status()
        ...     return response.json()

        >>> # Only retry on specific exceptions
        >>> @retry(exceptions=(ConnectionError, TimeoutError))
        ... def fetch_url(url: str) -> str:
        ...     return requests.get(url).text

    Note:
        The decorated function preserves the original function's signature,
        docstring, and name via functools.wraps.

    Warning:
        Be cautious with non-idempotent operations (e.g., creating resources).
        Retrying such operations may cause duplicates or unintended side effects.
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            attempt: int = 0
            current_delay: float = delay
            last_exception: Exception | None = None

            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    attempt += 1

                    if attempt >= max_attempts:
                        logger.error(f"All {max_attempts} attempts failed for {func.__name__}: {e}")
                        raise

                    logger.warning(
                        f"Attempt {attempt}/{max_attempts} failed for {func.__name__}: {e}. "
                        f"Retrying in {current_delay:.1f}s..."
                    )
                    time.sleep(current_delay)
                    current_delay *= backoff

            # This should never be reached due to the raise above,
            # but satisfies type checkers
            if last_exception:
                raise last_exception
            return None  # type: ignore[return-value]

        return cast(F, wrapper)

    return decorator
