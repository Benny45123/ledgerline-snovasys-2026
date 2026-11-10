"""
How this works / why it is safe:
This module implements distributed sliding-window rate limiting using Redis sorted sets (ZADD/ZCARD).
Every request timestamp is recorded with sub-second precision; entries outside the rolling window are pruned.
If Redis is down, unreachable, or disabled, it seamlessly falls back to a thread-safe in-memory sliding window,
ensuring zero outage for legitimate financial operations (Threat P12 mitigation).
Rate limiting protects against Sybil registration spam, brute force attacks, and endpoint flooding.
"""

import threading
import time
import uuid
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response

from app.config import settings
from app.errors import RateLimitedError
from app.logging import logger

# Global in-memory fallback state: {key: [timestamp1, timestamp2, ...]}
_memory_store: dict[str, list[float]] = defaultdict(list)
_memory_lock = threading.Lock()

# Global Redis client connection pool
_redis_client: Any = None
_redis_init_lock = threading.Lock()


def get_redis_client() -> Any:
    """Return lazy-initialized Redis connection or None if disabled/unavailable."""
    global _redis_client
    if not settings.REDIS_ENABLED:
        return None

    if _redis_client is not None:
        return _redis_client

    with _redis_init_lock:
        if _redis_client is not None:
            return _redis_client
        try:
            import redis

            client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=1.0,
                socket_timeout=1.0,
            )
            client.ping()
            _redis_client = client
            logger.info("redis_rate_limiter_connected", url=settings.REDIS_URL.split("@")[-1])
            return _redis_client
        except Exception as e:
            logger.warning("redis_connection_failed_fallback_to_memory", error=str(e))
            _redis_client = None
            return None


def check_redis_health() -> bool:
    """Check whether Redis is responding for readiness probes."""
    if not settings.REDIS_ENABLED:
        return True
    client = get_redis_client()
    if client is None:
        return False
    try:
        return bool(client.ping())
    except Exception:
        return False


def apply_rate_limit(
    identifier: str,
    scope: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> tuple[bool, int, int]:
    """
    Apply sliding window rate limit.
    Returns: (is_allowed, remaining_requests, reset_after_seconds)
    """
    now = time.time()
    key = f"ratelimit:{scope}:{identifier}"
    window_start = now - window_seconds

    # Attempt Redis first
    client = get_redis_client()
    if client is not None:
        try:
            pipe = client.pipeline(transaction=True)
            pipe.zremrangebyscore(key, 0, window_start)
            pipe.zcard(key)
            pipe.zadd(key, {str(uuid.uuid4()): now})
            pipe.expire(key, window_seconds + 5)
            results = pipe.execute()

            current_count = int(results[1])
            if current_count >= max_requests:
                # Remove the over-limit entry we just added
                client.zremrangebyscore(key, now, now)
                return False, 0, window_seconds

            remaining = max(0, max_requests - current_count - 1)
            return True, remaining, window_seconds
        except Exception as e:
            logger.warning("redis_pipeline_failed_using_memory_fallback", error=str(e))

    # Thread-safe in-memory fallback
    with _memory_lock:
        timestamps = _memory_store[key]
        # Prune expired
        _memory_store[key] = [ts for ts in timestamps if ts > window_start]
        current_count = len(_memory_store[key])

        if current_count >= max_requests:
            return False, 0, window_seconds

        _memory_store[key].append(now)
        remaining = max_requests - current_count - 1
        return True, remaining, window_seconds


def rate_limit_dependency(
    scope: str,
    max_requests: int = 60,
    window_seconds: int = 60,
) -> Callable[..., None]:
    """FastAPI route dependency enforcing rate limits per client IP or session user."""

    def dependency(request: Request, response: Response) -> None:
        # Determine client identifier: authenticated user ID or client IP
        auth_header = request.headers.get("authorization", "")
        identifier = auth_header[:32] if auth_header else (request.client.host if request.client else "127.0.0.1")

        allowed, remaining, reset_time = apply_rate_limit(
            identifier=identifier,
            scope=scope,
            max_requests=max_requests,
            window_seconds=window_seconds,
        )

        response.headers["X-RateLimit-Limit"] = str(max_requests)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(reset_time)

        if not allowed:
            response.headers["Retry-After"] = str(reset_time)
            raise RateLimitedError(
                f"Rate limit exceeded for {scope}. Limit: {max_requests} req/{window_seconds}s.",
                details={"retry_after": reset_time},
            )

    return dependency
