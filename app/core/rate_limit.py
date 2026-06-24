import hashlib
import logging
from collections import deque
from collections.abc import Callable
from threading import RLock
from time import monotonic, time
from uuid import uuid4

from fastapi import Request, status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.core.redis import redis_client

logger = logging.getLogger(__name__)


_BUCKETS: dict[tuple[str, str], deque[float]] = {}
_BUCKETS_LOCK = RLock()
_CLEANUP_EVERY_REQUESTS = 128
_REQUEST_COUNT = 0
_REDIS_RATE_LIMIT_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
  local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
  return {0, oldest[2] or ARGV[2]}
end
redis.call('ZADD', KEYS[1], ARGV[2], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[5])
return {1, 0}
"""


def reset_rate_limits() -> None:
    global _REQUEST_COUNT
    with _BUCKETS_LOCK:
        _BUCKETS.clear()
        _REQUEST_COUNT = 0


def rate_limit_bucket_count() -> int:
    with _BUCKETS_LOCK:
        return len(_BUCKETS)


def cleanup_rate_limits() -> None:
    _cleanup_expired(monotonic(), get_settings())


async def auth_rate_limit(request: Request) -> None:
    settings = get_settings()
    await _check_rate_limit(
        request,
        bucket="auth",
        limit=settings.auth_rate_limit_requests,
        window_seconds=settings.auth_rate_limit_window_seconds,
    )


async def admin_provider_rate_limit(request: Request) -> None:
    settings = get_settings()
    await _check_rate_limit(
        request,
        bucket="admin_provider",
        limit=settings.admin_provider_rate_limit_requests,
        window_seconds=settings.admin_provider_rate_limit_window_seconds,
    )


async def provider_search_rate_limit(request: Request) -> None:
    settings = get_settings()
    await _check_rate_limit(
        request,
        bucket="provider_search",
        limit=settings.provider_search_rate_limit_requests,
        window_seconds=settings.provider_search_rate_limit_window_seconds,
    )


async def image_upload_rate_limit(request: Request) -> None:
    settings = get_settings()
    await _check_rate_limit(
        request,
        bucket="image_upload",
        limit=settings.image_upload_rate_limit_requests,
        window_seconds=settings.image_upload_rate_limit_window_seconds,
    )


async def _check_rate_limit(
    request: Request,
    *,
    bucket: str,
    limit: int,
    window_seconds: int,
    key_func: Callable[[Request], str] | None = None,
) -> None:
    if limit <= 0 or window_seconds <= 0:
        return

    key = key_func(request) if key_func else _client_key(request)
    if await _check_rate_limit_redis(
        bucket=bucket,
        key=key,
        limit=limit,
        window_seconds=window_seconds,
    ):
        return

    _check_rate_limit_memory(
        bucket=bucket,
        key=key,
        limit=limit,
        window_seconds=window_seconds,
    )


async def _check_rate_limit_redis(
    *,
    bucket: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> bool:
    now_ms = int(time() * 1000)
    window_ms = window_seconds * 1000
    redis_key = _redis_rate_limit_key(bucket, key)
    try:
        async with redis_client() as client:
            if client is None:
                return False
            allowed, oldest_score = await client.eval(
                _REDIS_RATE_LIMIT_SCRIPT,
                1,
                redis_key,
                now_ms - window_ms,
                now_ms,
                limit,
                f"{now_ms}:{uuid4().hex}",
                window_seconds,
            )
    except ApiHTTPException:
        raise
    except Exception:
        logger.warning("Redis rate limit unavailable; using in-memory fallback", exc_info=True)
        return False

    if int(allowed) == 1:
        return True

    retry_after = _redis_retry_after_seconds(now_ms, window_ms, oldest_score)
    raise ApiHTTPException(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        code=f"{bucket}_rate_limited",
        detail="Too many requests",
        headers={"Retry-After": str(retry_after)},
    )


def _check_rate_limit_memory(
    *,
    bucket: str,
    key: str,
    limit: int,
    window_seconds: int,
) -> None:
    now = monotonic()
    settings = get_settings()
    with _BUCKETS_LOCK:
        global _REQUEST_COUNT
        _REQUEST_COUNT += 1
        if _REQUEST_COUNT % _CLEANUP_EVERY_REQUESTS == 0:
            _cleanup_expired(now, settings)

        entries = _BUCKETS.setdefault((bucket, key), deque())
        _prune(entries, now - window_seconds)

        if len(entries) >= limit:
            retry_after = max(1, int(window_seconds - (now - entries[0])))
            raise ApiHTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                code=f"{bucket}_rate_limited",
                detail="Too many requests",
                headers={"Retry-After": str(retry_after)},
            )

        entries.append(now)


def _redis_rate_limit_key(bucket: str, key: str) -> str:
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return f"collectarr:rate:{bucket}:{digest}"


def _redis_retry_after_seconds(now_ms: int, window_ms: int, oldest_score) -> int:
    try:
        oldest_ms = int(float(oldest_score))
    except (TypeError, ValueError):
        oldest_ms = now_ms
    return max(1, int((window_ms - (now_ms - oldest_ms)) / 1000))


def _cleanup_expired(now: float, settings) -> None:
    with _BUCKETS_LOCK:
        for key, entries in list(_BUCKETS.items()):
            bucket, _ = key
            cutoff = now - _bucket_window_seconds(settings, bucket)
            _prune(entries, cutoff)
            if not entries:
                del _BUCKETS[key]


def _bucket_window_seconds(settings, bucket: str) -> int:
    if bucket == "auth":
        return settings.auth_rate_limit_window_seconds
    if bucket == "admin_provider":
        return settings.admin_provider_rate_limit_window_seconds
    if bucket == "provider_search":
        return settings.provider_search_rate_limit_window_seconds
    if bucket == "image_upload":
        return settings.image_upload_rate_limit_window_seconds
    return max(
        settings.auth_rate_limit_window_seconds,
        settings.admin_provider_rate_limit_window_seconds,
        settings.provider_search_rate_limit_window_seconds,
        settings.image_upload_rate_limit_window_seconds,
    )


def _prune(entries: deque[float], cutoff: float) -> None:
    while entries and entries[0] <= cutoff:
        entries.popleft()


def _client_key(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", 1)[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host
