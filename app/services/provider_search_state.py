import hashlib
import json
import logging
from threading import RLock
from time import monotonic

from fastapi import status

from app.core.config import Settings
from app.core.errors import ApiHTTPException
from app.core.redis import redis_client
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import ProviderSearchResult


logger = logging.getLogger(__name__)

_PROVIDER_SEARCH_CACHE: dict[tuple[str, str, str], "_ProviderSearchCacheEntry"] = {}
_PROVIDER_SEARCH_BACKOFFS: dict[str, "_ProviderSearchBackoff"] = {}
_PROVIDER_SEARCH_LOCK = RLock()
_PROVIDER_SEARCH_CACHE_PREFIX = "collectarr:provider-search:cache"
_PROVIDER_SEARCH_BACKOFF_PREFIX = "collectarr:provider-search:backoff"


class _ProviderSearchCacheEntry:
    def __init__(self, results: list[ProviderSearchResult], expires_at: float) -> None:
        self.results = tuple(results)
        self.expires_at = expires_at


class _ProviderSearchBackoff:
    def __init__(
        self,
        *,
        expires_at: float,
        provider_name: str,
        reason: str,
    ) -> None:
        self.expires_at = expires_at
        self.provider_name = provider_name
        self.reason = reason


def reset_provider_search_state() -> None:
    with _PROVIDER_SEARCH_LOCK:
        _PROVIDER_SEARCH_CACHE.clear()
        _PROVIDER_SEARCH_BACKOFFS.clear()


class ProviderSearchState:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def cached(
        self,
        key: tuple[str, str, str],
    ) -> list[ProviderSearchResult] | None:
        ttl = self.settings.provider_search_cache_ttl_seconds
        if ttl <= 0:
            return None
        redis_results = await self._cached_redis(key)
        if redis_results is not None:
            return redis_results
        now = monotonic()
        with _PROVIDER_SEARCH_LOCK:
            entry = _PROVIDER_SEARCH_CACHE.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del _PROVIDER_SEARCH_CACHE[key]
                return None
            return list(entry.results)

    async def store(
        self,
        key: tuple[str, str, str],
        results: list[ProviderSearchResult],
    ) -> None:
        ttl = self.settings.provider_search_cache_ttl_seconds
        max_entries = self.settings.provider_search_cache_max_entries
        if ttl <= 0 or max_entries <= 0:
            return
        if await self._store_redis(key, results, ttl):
            return
        now = monotonic()
        with _PROVIDER_SEARCH_LOCK:
            _PROVIDER_SEARCH_CACHE[key] = _ProviderSearchCacheEntry(
                results,
                expires_at=now + ttl,
            )
            while len(_PROVIDER_SEARCH_CACHE) > max_entries:
                oldest_key = min(
                    _PROVIDER_SEARCH_CACHE,
                    key=lambda item: _PROVIDER_SEARCH_CACHE[item].expires_at,
                )
                del _PROVIDER_SEARCH_CACHE[oldest_key]

    async def raise_if_backoff(
        self,
        provider_name: ExternalProvider,
    ) -> None:
        if await self._raise_if_backoff_redis(provider_name):
            return
        now = monotonic()
        with _PROVIDER_SEARCH_LOCK:
            backoff = _PROVIDER_SEARCH_BACKOFFS.get(provider_name.value)
            if backoff is None:
                return
            if backoff.expires_at <= now:
                del _PROVIDER_SEARCH_BACKOFFS[provider_name.value]
                return
            retry_after = max(1, int(backoff.expires_at - now))
        raise ApiHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="provider_search_backoff",
            detail=(
                f"{backoff.provider_name} search is cooling down after "
                f"{backoff.reason}. Try again in {retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    async def record_backoff(
        self,
        provider_name: ExternalProvider,
        *,
        seconds: int,
        provider_label: str,
        reason: str,
    ) -> None:
        if seconds <= 0:
            return
        if await self._record_backoff_redis(
            provider_name,
            seconds=seconds,
            provider_label=provider_label,
            reason=reason,
        ):
            return
        with _PROVIDER_SEARCH_LOCK:
            _PROVIDER_SEARCH_BACKOFFS[provider_name.value] = _ProviderSearchBackoff(
                expires_at=monotonic() + seconds,
                provider_name=provider_label,
                reason=reason,
            )

    async def _cached_redis(
        self,
        key: tuple[str, str, str],
    ) -> list[ProviderSearchResult] | None:
        try:
            async with redis_client() as client:
                if client is None:
                    return None
                raw = await client.get(self._redis_cache_key(key))
        except Exception:
            logger.warning(
                "Redis provider search cache unavailable; using in-memory fallback",
                exc_info=True,
            )
            return None
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            if not isinstance(payload, list):
                return None
            return [self._result_from_payload(item) for item in payload if isinstance(item, dict)]
        except (KeyError, TypeError, ValueError):
            logger.warning("Invalid Redis provider search cache payload", exc_info=True)
            return None

    async def _store_redis(
        self,
        key: tuple[str, str, str],
        results: list[ProviderSearchResult],
        ttl: int,
    ) -> bool:
        try:
            payload = json.dumps(
                [self._result_payload(result) for result in results],
                separators=(",", ":"),
            )
            async with redis_client() as client:
                if client is None:
                    return False
                await client.setex(self._redis_cache_key(key), ttl, payload)
            return True
        except Exception:
            logger.warning(
                "Redis provider search cache store failed; using in-memory fallback",
                exc_info=True,
            )
            return False

    async def _raise_if_backoff_redis(
        self,
        provider_name: ExternalProvider,
    ) -> bool:
        try:
            async with redis_client() as client:
                if client is None:
                    return False
                key = self._redis_backoff_key(provider_name)
                raw = await client.get(key)
                if raw is None:
                    return False
                ttl = await client.ttl(key)
        except Exception:
            logger.warning(
                "Redis provider search backoff unavailable; using in-memory fallback",
                exc_info=True,
            )
            return False
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return False
            provider_label = str(payload.get("provider_name") or provider_name.value)
            reason = str(payload.get("reason") or "upstream error")
        except (TypeError, ValueError):
            return False
        retry_after = max(
            1,
            int(ttl if ttl and ttl > 0 else self.settings.provider_search_backoff_seconds),
        )
        raise ApiHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="provider_search_backoff",
            detail=(
                f"{provider_label} search is cooling down after "
                f"{reason}. Try again in {retry_after}s."
            ),
            headers={"Retry-After": str(retry_after)},
        )

    async def _record_backoff_redis(
        self,
        provider_name: ExternalProvider,
        *,
        seconds: int,
        provider_label: str,
        reason: str,
    ) -> bool:
        try:
            payload = json.dumps(
                {"provider_name": provider_label, "reason": reason},
                separators=(",", ":"),
            )
            async with redis_client() as client:
                if client is None:
                    return False
                await client.setex(
                    self._redis_backoff_key(provider_name),
                    seconds,
                    payload,
                )
            return True
        except Exception:
            logger.warning(
                "Redis provider search backoff store failed; using in-memory fallback",
                exc_info=True,
            )
            return False

    def _redis_cache_key(self, key: tuple[str, str, str]) -> str:
        digest = hashlib.sha256("|".join(key).encode("utf-8")).hexdigest()
        return f"{_PROVIDER_SEARCH_CACHE_PREFIX}:{digest}"

    def _redis_backoff_key(self, provider_name: ExternalProvider) -> str:
        return f"{_PROVIDER_SEARCH_BACKOFF_PREFIX}:{provider_name.value}"

    def _result_payload(self, result: ProviderSearchResult) -> dict[str, object]:
        return {
            "provider": result.provider,
            "provider_item_id": result.provider_item_id,
            "title": result.title,
            "kind": result.kind.value,
            "summary": result.summary,
            "image_url": result.image_url,
            "candidate_type": result.candidate_type,
            "series_title": result.series_title,
            "issue_number": result.issue_number,
            "volume_start_year": result.volume_start_year,
            "variant_name": result.variant_name,
            "is_variant": result.is_variant,
        }

    def _result_from_payload(self, payload: dict) -> ProviderSearchResult:
        return ProviderSearchResult(
            provider=str(payload["provider"]),
            provider_item_id=str(payload["provider_item_id"]),
            title=str(payload["title"]),
            kind=ItemKind(str(payload["kind"])),
            summary=self._optional_text(payload.get("summary")),
            image_url=self._optional_text(payload.get("image_url")),
            candidate_type=self._optional_text(payload.get("candidate_type")),
            series_title=self._optional_text(payload.get("series_title")),
            issue_number=self._optional_text(payload.get("issue_number")),
            volume_start_year=self._optional_int(payload.get("volume_start_year")),
            variant_name=self._optional_text(payload.get("variant_name")),
            is_variant=self._optional_bool(payload.get("is_variant")),
        )

    def _optional_text(self, value) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text or None

    def _optional_int(self, value) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_bool(self, value) -> bool | None:
        if isinstance(value, bool):
            return value
        if value is None or value == "":
            return None
        return str(value).strip().lower() in {"1", "true", "yes"}
