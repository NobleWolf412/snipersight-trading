"""
Shared retry logic for exchange adapters.

Provides a decorator for handling rate limits and network errors
with exponential backoff and jitter to prevent thundering herd.
"""

import time
import random
from functools import wraps
from typing import Callable, TypeVar, Any
import ccxt
from loguru import logger


# Default configuration
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF = 1.0
DEFAULT_JITTER_PCT = 0.25  # 25% random jitter


F = TypeVar('F', bound=Callable[..., Any])


def retry_on_rate_limit(
    max_retries: int = DEFAULT_MAX_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    jitter_pct: float = DEFAULT_JITTER_PCT
) -> Callable[[F], F]:
    """
    Decorator to retry function calls on rate limit and network errors.
    
    Uses exponential backoff with jitter to prevent thundering herd
    when multiple concurrent requests hit rate limits simultaneously.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        backoff: Initial backoff time in seconds, doubles each retry (default: 1.0)
        jitter_pct: Random jitter percentage (0-1) to add to backoff (default: 0.25)
    
    Returns:
        Decorated function with retry logic
    
    Example:
        @retry_on_rate_limit(max_retries=5, backoff=2.0, jitter_pct=0.3)
        def fetch_data():
            ...
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retries = 0
            current_backoff = backoff

            while retries < max_retries:
                try:
                    return func(*args, **kwargs)
                except ccxt.RateLimitExceeded as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Rate limit exceeded after {max_retries} retries")
                        raise
                    
                    # Add jitter to prevent thundering herd
                    jitter = current_backoff * jitter_pct * random.random()
                    sleep_time = current_backoff + jitter
                    
                    logger.warning(
                        f"Rate limit hit, retrying in {sleep_time:.2f}s "
                        f"(attempt {retries}/{max_retries})"
                    )
                    time.sleep(sleep_time)
                    current_backoff *= 2
                    
                except ccxt.NetworkError as e:
                    retries += 1
                    if retries >= max_retries:
                        logger.error(f"Network error after {max_retries} retries: {e}")
                        raise
                    
                    # Add jitter for network errors too
                    jitter = current_backoff * jitter_pct * random.random()
                    sleep_time = current_backoff + jitter
                    
                    logger.warning(f"Network error, retrying in {sleep_time:.2f}s: {e}")
                    time.sleep(sleep_time)
                    current_backoff *= 2
            
            # Final attempt without catching
            return func(*args, **kwargs)
        
        return wrapper  # type: ignore
    return decorator


# Backward compatibility alias
_retry_on_rate_limit = retry_on_rate_limit
