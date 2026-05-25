from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import hashlib
import json
import logging
from threading import RLock
from time import monotonic
from typing import Final

from app.core.config import get_settings
from app.core.redis import redis_client
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedBundleMember,
    NormalizedBundleRelease,
    NormalizedCredit,
    NormalizedItem,
    NormalizedRelation,
    NormalizedTrack,
    NormalizedVariantCover,
    ProviderItem,
)


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HydratedProviderPreview:
    provider_item: ProviderItem
    normalized: NormalizedItem


@dataclass(frozen=True)
class _ProviderPreviewCacheEntry:
    value: HydratedProviderPreview
    expires_at: float


class _ProviderPreviewStats:
    def __init__(self) -> None:
        self.hits = 0
        self.misses = 0
        self.writes = 0


_PROVIDER_PREVIEW_CACHE: Final[dict[tuple[str, str], _ProviderPreviewCacheEntry]] = {}
_PROVIDER_PREVIEW_CACHE_LOCK = RLock()
_PROVIDER_PREVIEW_CACHE_PREFIX = "collectarr:provider-preview:cache"
_PROVIDER_PREVIEW_STATS = _ProviderPreviewStats()


def clear_provider_preview_cache() -> None:
    with _PROVIDER_PREVIEW_CACHE_LOCK:
        _PROVIDER_PREVIEW_CACHE.clear()


def reset_provider_preview_state() -> None:
    with _PROVIDER_PREVIEW_CACHE_LOCK:
        _PROVIDER_PREVIEW_CACHE.clear()
        _PROVIDER_PREVIEW_STATS.hits = 0
        _PROVIDER_PREVIEW_STATS.misses = 0
        _PROVIDER_PREVIEW_STATS.writes = 0


class ProviderPreviewState:
    def __init__(self) -> None:
        self.settings = get_settings()

    async def cached(self, provider: str, provider_item_id: str) -> HydratedProviderPreview | None:
        ttl = self.settings.provider_preview_cache_ttl_seconds
        if ttl <= 0:
            return None
        redis_value = await self._cached_redis(provider, provider_item_id)
        if redis_value is not None:
            self._record_hit()
            return redis_value
        key = (provider, provider_item_id)
        now = monotonic()
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            entry = _PROVIDER_PREVIEW_CACHE.get(key)
            if entry is None:
                _PROVIDER_PREVIEW_STATS.misses += 1
                return None
            if entry.expires_at <= now:
                _PROVIDER_PREVIEW_CACHE.pop(key, None)
                _PROVIDER_PREVIEW_STATS.misses += 1
                return None
            _PROVIDER_PREVIEW_STATS.hits += 1
            return entry.value

    async def store(
        self,
        provider: str,
        requested_provider_item_id: str,
        value: HydratedProviderPreview,
    ) -> None:
        ttl = self.settings.provider_preview_cache_ttl_seconds
        max_entries = self.settings.provider_preview_cache_max_entries
        if ttl <= 0 or max_entries <= 0:
            return
        if await self._store_redis(provider, requested_provider_item_id, value, ttl):
            self._record_write()
            return

        self._evict_expired()
        entry = _ProviderPreviewCacheEntry(
            value=value,
            expires_at=monotonic() + ttl,
        )
        keys = {
            (provider, requested_provider_item_id),
            (provider, value.provider_item.provider_item_id),
        }
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            _PROVIDER_PREVIEW_STATS.writes += 1
            for key in keys:
                _PROVIDER_PREVIEW_CACHE[key] = entry
            while len(_PROVIDER_PREVIEW_CACHE) > max_entries:
                oldest_key = min(
                    _PROVIDER_PREVIEW_CACHE,
                    key=lambda item_key: _PROVIDER_PREVIEW_CACHE[item_key].expires_at,
                )
                _PROVIDER_PREVIEW_CACHE.pop(oldest_key, None)

    async def invalidate(self, provider: str, *provider_item_ids: str | None) -> None:
        keys = {
            (provider, provider_item_id)
            for provider_item_id in provider_item_ids
            if isinstance(provider_item_id, str) and provider_item_id.strip()
        }
        if not keys:
            return
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            for key in keys:
                _PROVIDER_PREVIEW_CACHE.pop(key, None)
        await self._invalidate_redis(keys)

    async def clear(self) -> None:
        clear_provider_preview_cache()
        await self._clear_redis()

    async def stats(self) -> dict[str, int]:
        redis_entries = await self._redis_entry_count()
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            local_entries = len(_PROVIDER_PREVIEW_CACHE)
            return {
                "hits": _PROVIDER_PREVIEW_STATS.hits,
                "misses": _PROVIDER_PREVIEW_STATS.misses,
                "writes": _PROVIDER_PREVIEW_STATS.writes,
                "entries": max(local_entries, redis_entries),
                "backoffs": 0,
                "local_entries": local_entries,
                "redis_entries": redis_entries,
                "local_backoffs": 0,
                "redis_backoffs": 0,
            }

    def _record_hit(self) -> None:
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            _PROVIDER_PREVIEW_STATS.hits += 1

    def _record_write(self) -> None:
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            _PROVIDER_PREVIEW_STATS.writes += 1

    def _evict_expired(self) -> None:
        now = monotonic()
        with _PROVIDER_PREVIEW_CACHE_LOCK:
            expired = [
                key for key, entry in _PROVIDER_PREVIEW_CACHE.items() if entry.expires_at <= now
            ]
            for key in expired:
                _PROVIDER_PREVIEW_CACHE.pop(key, None)

    async def _cached_redis(
        self,
        provider: str,
        provider_item_id: str,
    ) -> HydratedProviderPreview | None:
        try:
            async with redis_client() as client:
                if client is None:
                    return None
                raw = await client.get(self._redis_cache_key(provider, provider_item_id))
        except Exception:
            logger.warning(
                "Redis provider preview cache unavailable; using in-memory fallback",
                exc_info=True,
            )
            return None
        if raw is None:
            return None
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return None
            return self._hydrated_preview_from_payload(payload)
        except (KeyError, TypeError, ValueError):
            logger.warning("Invalid Redis provider preview cache payload", exc_info=True)
            return None

    async def _store_redis(
        self,
        provider: str,
        requested_provider_item_id: str,
        value: HydratedProviderPreview,
        ttl: int,
    ) -> bool:
        try:
            payload = json.dumps(self._hydrated_preview_payload(value), separators=(",", ":"))
            async with redis_client() as client:
                if client is None:
                    return False
                keys = {
                    self._redis_cache_key(provider, requested_provider_item_id),
                    self._redis_cache_key(provider, value.provider_item.provider_item_id),
                }
                for key in keys:
                    await client.setex(key, ttl, payload)
            return True
        except Exception:
            logger.warning(
                "Redis provider preview cache store failed; using in-memory fallback",
                exc_info=True,
            )
            return False

    async def _clear_redis(self) -> None:
        try:
            async with redis_client() as client:
                if client is None:
                    return
                keys: list[str] = []
                async for key in client.scan_iter(match=f"{_PROVIDER_PREVIEW_CACHE_PREFIX}:*"):
                    keys.append(key)
                if keys:
                    await client.delete(*keys)
        except Exception:
            logger.warning("Redis provider preview cache clear failed", exc_info=True)

    async def _invalidate_redis(self, keys: set[tuple[str, str]]) -> None:
        try:
            async with redis_client() as client:
                if client is None:
                    return
                redis_keys = [
                    self._redis_cache_key(provider, provider_item_id)
                    for provider, provider_item_id in keys
                ]
                if redis_keys:
                    await client.delete(*redis_keys)
        except Exception:
            logger.warning("Redis provider preview cache invalidate failed", exc_info=True)

    async def _redis_entry_count(self) -> int:
        try:
            async with redis_client() as client:
                if client is None:
                    return 0
                count = 0
                async for _ in client.scan_iter(match=f"{_PROVIDER_PREVIEW_CACHE_PREFIX}:*"):
                    count += 1
                return count
        except Exception:
            logger.warning(
                "Redis provider preview cache stats unavailable; using in-memory fallback",
                exc_info=True,
            )
            return 0

    def _redis_cache_key(self, provider: str, provider_item_id: str) -> str:
        digest = hashlib.sha256(f"{provider}|{provider_item_id}".encode("utf-8")).hexdigest()
        return f"{_PROVIDER_PREVIEW_CACHE_PREFIX}:{digest}"

    def _hydrated_preview_payload(self, value: HydratedProviderPreview) -> dict[str, object]:
        return {
            "provider_item": {
                "provider": value.provider_item.provider,
                "provider_item_id": value.provider_item.provider_item_id,
                "raw": value.provider_item.raw,
            },
            "normalized": self._normalized_item_payload(value.normalized),
        }

    def _hydrated_preview_from_payload(self, payload: dict[str, object]) -> HydratedProviderPreview:
        provider_item_payload = payload["provider_item"]
        normalized_payload = payload["normalized"]
        if not isinstance(provider_item_payload, dict) or not isinstance(normalized_payload, dict):
            raise ValueError("Invalid hydrated preview payload")
        return HydratedProviderPreview(
            provider_item=ProviderItem(
                provider=str(provider_item_payload["provider"]),
                provider_item_id=str(provider_item_payload["provider_item_id"]),
                raw=provider_item_payload.get("raw"),
            ),
            normalized=self._normalized_item_from_payload(normalized_payload),
        )

    def _normalized_item_payload(self, value: NormalizedItem) -> dict[str, object]:
        return {
            "kind": value.kind.value,
            "title": value.title,
            "item_number": value.item_number,
            "synopsis": value.synopsis,
            "series_title": value.series_title,
            "volume_name": value.volume_name,
            "volume_number": value.volume_number,
            "volume_start_year": value.volume_start_year,
            "runtime_minutes": value.runtime_minutes,
            "page_count": value.page_count,
            "edition_title": value.edition_title,
            "edition_format": value.edition_format,
            "physical_format": value.physical_format,
            "publisher": value.publisher,
            "imprint": value.imprint,
            "release_date": self._date_payload(value.release_date),
            "isbn": value.isbn,
            "barcode": value.barcode,
            "cover_price_cents": value.cover_price_cents,
            "currency": value.currency,
            "variant_name": value.variant_name,
            "variant_type": value.variant_type,
            "cover_image_url": value.cover_image_url,
            "creators": [self._credit_payload(item) for item in value.creators],
            "characters": [self._credit_payload(item) for item in value.characters],
            "story_arcs": [self._credit_payload(item) for item in value.story_arcs],
            "provider_ids": dict(value.provider_ids),
            "volume_provider_ids": dict(value.volume_provider_ids),
            "variant_covers": [self._variant_cover_payload(item) for item in value.variant_covers],
            "relations": [self._relation_payload(item) for item in value.relations],
            "tracks": [self._track_payload(item) for item in value.tracks],
            "track_count": value.track_count,
            "catalog_number": value.catalog_number,
            "country": value.country,
            "release_status": value.release_status,
            "platforms": list(value.platforms),
            "genres": list(value.genres),
            "language": value.language,
            "age_rating": value.age_rating,
            "subtitle": value.subtitle,
            "series_group": value.series_group,
            "bundle_release": self._bundle_release_payload(value.bundle_release),
        }

    def _normalized_item_from_payload(self, payload: dict[str, object]) -> NormalizedItem:
        return NormalizedItem(
            kind=ItemKind(str(payload["kind"])),
            title=str(payload["title"]),
            item_number=self._optional_text(payload.get("item_number")),
            synopsis=self._optional_text(payload.get("synopsis")),
            series_title=self._optional_text(payload.get("series_title")),
            volume_name=self._optional_text(payload.get("volume_name")),
            volume_number=self._optional_int(payload.get("volume_number")),
            volume_start_year=self._optional_int(payload.get("volume_start_year")),
            runtime_minutes=self._optional_int(payload.get("runtime_minutes")),
            page_count=self._optional_int(payload.get("page_count")),
            edition_title=self._optional_text(payload.get("edition_title")),
            edition_format=self._optional_text(payload.get("edition_format")),
            physical_format=self._optional_text(payload.get("physical_format")),
            publisher=self._optional_text(payload.get("publisher")),
            imprint=self._optional_text(payload.get("imprint")),
            release_date=self._optional_date(payload.get("release_date")),
            isbn=self._optional_text(payload.get("isbn")),
            barcode=self._optional_text(payload.get("barcode")),
            cover_price_cents=self._optional_int(payload.get("cover_price_cents")),
            currency=self._optional_text(payload.get("currency")),
            variant_name=self._optional_text(payload.get("variant_name")),
            variant_type=self._optional_text(payload.get("variant_type")),
            cover_image_url=self._optional_text(payload.get("cover_image_url")),
            creators=self._credit_list_from_payload(payload.get("creators")),
            characters=self._credit_list_from_payload(payload.get("characters")),
            story_arcs=self._credit_list_from_payload(payload.get("story_arcs")),
            provider_ids=self._text_dict(payload.get("provider_ids")),
            volume_provider_ids=self._text_dict(payload.get("volume_provider_ids")),
            variant_covers=self._variant_cover_list_from_payload(payload.get("variant_covers")),
            relations=self._relation_list_from_payload(payload.get("relations")),
            tracks=self._track_list_from_payload(payload.get("tracks")),
            track_count=self._optional_int(payload.get("track_count")),
            catalog_number=self._optional_text(payload.get("catalog_number")),
            country=self._optional_text(payload.get("country")),
            release_status=self._optional_text(payload.get("release_status")),
            platforms=self._text_list(payload.get("platforms")),
            genres=self._text_list(payload.get("genres")),
            language=self._optional_text(payload.get("language")),
            age_rating=self._optional_text(payload.get("age_rating")),
            subtitle=self._optional_text(payload.get("subtitle")),
            series_group=self._optional_text(payload.get("series_group")),
            bundle_release=self._bundle_release_from_payload(payload.get("bundle_release")),
        )

    def _credit_payload(self, value: NormalizedCredit) -> dict[str, object]:
        return {
            "name": value.name,
            "role": value.role,
            "api_detail_url": value.api_detail_url,
            "site_detail_url": value.site_detail_url,
            "image_url": value.image_url,
        }

    def _credit_from_payload(self, payload: dict[str, object]) -> NormalizedCredit:
        return NormalizedCredit(
            name=str(payload["name"]),
            role=self._optional_text(payload.get("role")),
            api_detail_url=self._optional_text(payload.get("api_detail_url")),
            site_detail_url=self._optional_text(payload.get("site_detail_url")),
            image_url=self._optional_text(payload.get("image_url")),
        )

    def _credit_list_from_payload(self, payload: object) -> list[NormalizedCredit]:
        if not isinstance(payload, list):
            return []
        return [self._credit_from_payload(item) for item in payload if isinstance(item, dict)]

    def _variant_cover_payload(self, value: NormalizedVariantCover) -> dict[str, object]:
        return {
            "name": value.name,
            "cover_image_url": value.cover_image_url,
            "thumbnail_image_url": value.thumbnail_image_url,
            "provider_item_id": value.provider_item_id,
            "source_id": value.source_id,
            "caption": value.caption,
        }

    def _variant_cover_from_payload(self, payload: dict[str, object]) -> NormalizedVariantCover:
        return NormalizedVariantCover(
            name=str(payload["name"]),
            cover_image_url=str(payload["cover_image_url"]),
            thumbnail_image_url=self._optional_text(payload.get("thumbnail_image_url")),
            provider_item_id=self._optional_text(payload.get("provider_item_id")),
            source_id=self._optional_text(payload.get("source_id")),
            caption=self._optional_text(payload.get("caption")),
        )

    def _variant_cover_list_from_payload(self, payload: object) -> list[NormalizedVariantCover]:
        if not isinstance(payload, list):
            return []
        return [self._variant_cover_from_payload(item) for item in payload if isinstance(item, dict)]

    def _relation_payload(self, value: NormalizedRelation) -> dict[str, object]:
        return {
            "relation_type": value.relation_type,
            "title": value.title,
            "provider": value.provider,
            "provider_id": value.provider_id,
            "kind": value.kind.value if value.kind is not None else None,
            "start_year": value.start_year,
            "image_url": value.image_url,
        }

    def _relation_from_payload(self, payload: dict[str, object]) -> NormalizedRelation:
        kind = self._optional_text(payload.get("kind"))
        return NormalizedRelation(
            relation_type=str(payload["relation_type"]),
            title=str(payload["title"]),
            provider=self._optional_text(payload.get("provider")),
            provider_id=self._optional_text(payload.get("provider_id")),
            kind=ItemKind(kind) if kind is not None else None,
            start_year=self._optional_int(payload.get("start_year")),
            image_url=self._optional_text(payload.get("image_url")),
        )

    def _relation_list_from_payload(self, payload: object) -> list[NormalizedRelation]:
        if not isinstance(payload, list):
            return []
        return [self._relation_from_payload(item) for item in payload if isinstance(item, dict)]

    def _track_payload(self, value: NormalizedTrack) -> dict[str, object]:
        return {
            "position": value.position,
            "title": value.title,
            "duration_seconds": value.duration_seconds,
            "artist": value.artist,
            "disc_number": value.disc_number,
        }

    def _track_from_payload(self, payload: dict[str, object]) -> NormalizedTrack:
        return NormalizedTrack(
            position=int(payload["position"]),
            title=str(payload["title"]),
            duration_seconds=self._optional_int(payload.get("duration_seconds")),
            artist=self._optional_text(payload.get("artist")),
            disc_number=self._optional_int(payload.get("disc_number")),
        )

    def _track_list_from_payload(self, payload: object) -> list[NormalizedTrack]:
        if not isinstance(payload, list):
            return []
        return [self._track_from_payload(item) for item in payload if isinstance(item, dict)]

    def _bundle_release_payload(
        self,
        value: NormalizedBundleRelease | None,
    ) -> dict[str, object] | None:
        if value is None:
            return None
        return {
            "title": value.title,
            "bundle_type": value.bundle_type,
            "format": value.format,
            "variant_type": value.variant_type,
            "packaging_type": value.packaging_type,
            "region": value.region,
            "language": value.language,
            "publisher": value.publisher,
            "sku": value.sku,
            "barcode": value.barcode,
            "release_date": self._date_payload(value.release_date),
            "cover_image_url": value.cover_image_url,
            "provider_ids": dict(value.provider_ids),
            "members": [self._bundle_member_payload(item) for item in value.members],
        }

    def _bundle_release_from_payload(self, payload: object) -> NormalizedBundleRelease | None:
        if not isinstance(payload, dict):
            return None
        return NormalizedBundleRelease(
            title=str(payload["title"]),
            bundle_type=self._optional_text(payload.get("bundle_type")),
            format=self._optional_text(payload.get("format")),
            variant_type=self._optional_text(payload.get("variant_type")),
            packaging_type=self._optional_text(payload.get("packaging_type")),
            region=self._optional_text(payload.get("region")),
            language=self._optional_text(payload.get("language")),
            publisher=self._optional_text(payload.get("publisher")),
            sku=self._optional_text(payload.get("sku")),
            barcode=self._optional_text(payload.get("barcode")),
            release_date=self._optional_date(payload.get("release_date")),
            cover_image_url=self._optional_text(payload.get("cover_image_url")),
            provider_ids=self._text_dict(payload.get("provider_ids")),
            members=self._bundle_member_list_from_payload(payload.get("members")),
        )

    def _bundle_member_payload(self, value: NormalizedBundleMember) -> dict[str, object]:
        return {
            "item": self._normalized_item_payload(value.item),
            "role": value.role,
            "sequence_number": value.sequence_number,
            "disc_number": value.disc_number,
            "disc_label": value.disc_label,
            "quantity": value.quantity,
            "is_primary": value.is_primary,
            "metadata": value.metadata,
        }

    def _bundle_member_from_payload(self, payload: dict[str, object]) -> NormalizedBundleMember:
        item_payload = payload.get("item")
        if not isinstance(item_payload, dict):
            raise ValueError("Invalid bundle member payload")
        metadata = payload.get("metadata")
        return NormalizedBundleMember(
            item=self._normalized_item_from_payload(item_payload),
            role=self._optional_text(payload.get("role")) or "primary",
            sequence_number=self._optional_int(payload.get("sequence_number")),
            disc_number=self._optional_int(payload.get("disc_number")),
            disc_label=self._optional_text(payload.get("disc_label")),
            quantity=self._optional_int(payload.get("quantity")) or 1,
            is_primary=self._optional_bool(payload.get("is_primary")) or False,
            metadata=metadata if isinstance(metadata, dict) else {},
        )

    def _bundle_member_list_from_payload(self, payload: object) -> list[NormalizedBundleMember]:
        if not isinstance(payload, list):
            return []
        return [self._bundle_member_from_payload(item) for item in payload if isinstance(item, dict)]

    def _date_payload(self, value: date | None) -> str | None:
        return value.isoformat() if value is not None else None

    def _optional_date(self, value: object) -> date | None:
        text = self._optional_text(value)
        if text is None:
            return None
        return date.fromisoformat(text)

    def _optional_text(self, value: object) -> str | None:
        if value is None:
            return None
        text = str(value)
        return text or None

    def _optional_int(self, value: object) -> int | None:
        if value is None or value == "":
            return None
        return int(value)

    def _optional_bool(self, value: object) -> bool | None:
        if value is None:
            return None
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.casefold()
            if lowered in {"true", "1", "yes"}:
                return True
            if lowered in {"false", "0", "no"}:
                return False
        return bool(value)

    def _text_list(self, value: object) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := self._optional_text(item)) is not None]

    def _text_dict(self, value: object) -> dict[str, str]:
        if not isinstance(value, dict):
            return {}
        result: dict[str, str] = {}
        for key, item in value.items():
            text = self._optional_text(item)
            if text is not None:
                result[str(key)] = text
        return result