from collections import deque
from collections.abc import Callable
from threading import RLock
from time import monotonic

from fastapi import Request, status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException


_BUCKETS: dict[tuple[str, str], deque[float]] = {}
_BUCKETS_LOCK = RLock()
_CLEANUP_EVERY_REQUESTS = 128
_REQUEST_COUNT = 0


def reset_rate_limits() -> None:
    global _REQUEST_COUNT
    with _BUCKETS_LOCK:
        _BUCKETS.clear()
        _REQUEST_COUNT = 0


def rate_limit_bucket_count() -> int:
    with _BUCKETS_LOCK:
        return len(_BUCKETS)


def cleanup_rate_limits() -> None:
    settings = get_settings()
    max_window_seconds = max(
        settings.auth_rate_limit_window_seconds,
        settings.admin_provider_rate_limit_window_seconds,
    )
    _cleanup_expired(monotonic(), max_window_seconds)


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
    now = monotonic()
    settings = get_settings()
    cleanup_window_seconds = max(
        window_seconds,
        settings.auth_rate_limit_window_seconds,
        settings.admin_provider_rate_limit_window_seconds,
    )
    with _BUCKETS_LOCK:
        global _REQUEST_COUNT
        _REQUEST_COUNT += 1
        if _REQUEST_COUNT % _CLEANUP_EVERY_REQUESTS == 0:
            _cleanup_expired(now, cleanup_window_seconds)

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


def _cleanup_expired(now: float, window_seconds: int) -> None:
    cutoff = now - window_seconds
    with _BUCKETS_LOCK:
        for key, entries in list(_BUCKETS.items()):
            _prune(entries, cutoff)
            if not entries:
                del _BUCKETS[key]


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
