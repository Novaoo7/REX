# ==============================================================================
# utils/decorators.py   –  REX 4.0   Reusable Decorators
# ==============================================================================
# Design
#   • @retry – automatically retry a function on transient failures
#     (network, IO) with exponential backoff.
#   • @timed – measure and log execution time; optionally raise if it exceeds
#     a threshold.
#   • @requires_permission – declarative permission check; raises if the
#     active session does not have the specified Permission.
# ==============================================================================

from __future__ import annotations

import functools
import time
from typing import Any, Callable, Optional, Type

from core.logger import get_logger, LogCategory
from core.auth   import Permission, get_auth


# ─── retry ────────────────────────────────────────────────────────────────────


def retry(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0,
          exceptions: tuple = (Exception,)):
    """
    Retry a function on failure with exponential backoff.

    Parameters
    ----------
    max_attempts   How many times to try before giving up.
    delay          Initial delay in seconds before first retry.
    backoff        Multiplier for delay on each retry.
    exceptions     Tuple of exception types to catch (default: any Exception).

    Example
    -------
        @retry(max_attempts=3, delay=1.0)
        def flaky_network_call():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger      = get_logger()
            current_delay = delay
            last_exception = None

            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as exc:
                    last_exception = exc
                    if attempt == max_attempts:
                        break
                    logger.warning(LogCategory.ERROR,
                                   f"{func.__name__} attempt {attempt}/{max_attempts} failed: {exc}")
                    time.sleep(current_delay)
                    current_delay *= backoff

            # all retries exhausted
            logger.error(LogCategory.ERROR,
                         f"{func.__name__} failed after {max_attempts} attempts: {last_exception}")
            raise last_exception

        return wrapper
    return decorator


# ─── timed ────────────────────────────────────────────────────────────────────


def timed(threshold: Optional[float] = None, category: LogCategory = LogCategory.PERFORMANCE):
    """
    Measure and log execution time.  Optionally raise if it exceeds *threshold*.

    Parameters
    ----------
    threshold   If set, raise TimeoutError if the function takes longer than this (seconds).
    category    Log category to use.

    Example
    -------
        @timed(threshold=5.0)
        def slow_operation():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            logger = get_logger()
            start  = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start

            logger.log_performance(func.__name__, elapsed)

            if threshold and elapsed > threshold:
                raise TimeoutError(f"{func.__name__} took {elapsed:.2f}s (threshold: {threshold}s)")

            return result
        return wrapper
    return decorator


# ─── requires_permission ──────────────────────────────────────────────────────


def requires_permission(permission: Permission):
    """
    Declarative permission check.

    The decorated function must accept a keyword argument `session_token`.
    If the session does not have the required permission, PermissionError is raised.

    Example
    -------
        @requires_permission(Permission.SYSTEM_SHUTDOWN)
        def shutdown_computer(session_token: str):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            auth  = get_auth()
            token = kwargs.get("session_token")

            if token is None:
                raise ValueError(f"{func.__name__} requires 'session_token' keyword argument")

            if not auth.session_has_permission(token, permission):
                logger = get_logger()
                logger.warning(LogCategory.SECURITY,
                               f"Permission denied: {permission.value} for {func.__name__}")
                raise PermissionError(f"This action requires the '{permission.value}' permission")

            return func(*args, **kwargs)
        return wrapper
    return decorator


# ─── cached (simple in-memory cache) ──────────────────────────────────────────


def cached(ttl: int = 300):
    """
    Simple in-memory cache with TTL (seconds).

    The function's arguments are used as the cache key.  If the same arguments
    are seen within *ttl* seconds the cached result is returned immediately.

    Example
    -------
        @cached(ttl=60)
        def expensive_computation(x):
            ...
    """
    def decorator(func: Callable) -> Callable:
        cache: dict = {}

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # build key from args + kwargs
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()

            if key in cache:
                result, timestamp = cache[key]
                if now - timestamp < ttl:
                    return result

            result = func(*args, **kwargs)
            cache[key] = (result, now)
            return result

        wrapper.cache_clear = lambda: cache.clear()
        return wrapper
    return decorator