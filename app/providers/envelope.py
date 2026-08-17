"""Normalized provider envelope (v1) cross-repo contract."""

from __future__ import annotations

import dataclasses
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from typing import Any

from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderCapabilities


@dataclass(frozen=True)
class ProviderImageRef:
    provider: str
    url: str
    kind: str = "cover"
    thumbnail_url: str | None = None
    image_id: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    cache_policy: str | None = None
    mirror_policy: str | None = None
    attribution: str | None = None
    expires_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "url": self.url,
            "kind": self.kind,
            "thumbnail_url": self.thumbnail_url,
            "image_id": self.image_id,
            "headers": self.headers,
            "cache_policy": self.cache_policy,
            "mirror_policy": self.mirror_policy,
            "attribution": self.attribution,
            "expires_at": self.expires_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderImageRef:
        return cls(
            provider=data["provider"],
            url=data["url"],
            kind=data.get("kind", "cover"),
            thumbnail_url=data.get("thumbnail_url"),
            image_id=data.get("image_id"),
            headers=dict(data.get("headers") or {}),
            cache_policy=data.get("cache_policy"),
            mirror_policy=data.get("mirror_policy"),
            attribution=data.get("attribution"),
            expires_at=data.get("expires_at"),
        )


@dataclass(frozen=True)
class ProviderProvenance:
    fetched_at: str
    source_url: str | None = None
    raw_payload_hash: str | None = None
    provider_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "fetched_at": self.fetched_at,
            "source_url": self.source_url,
            "raw_payload_hash": self.raw_payload_hash,
            "provider_version": self.provider_version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderProvenance:
        return cls(
            fetched_at=data["fetched_at"],
            source_url=data.get("source_url"),
            raw_payload_hash=data.get("raw_payload_hash"),
            provider_version=data.get("provider_version"),
        )


@dataclass(frozen=True)
class ProviderAttribution:
    required: bool
    text: str | None = None
    url: str | None = None
    license_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "required": self.required,
            "text": self.text,
            "url": self.url,
            "license_name": self.license_name,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ProviderAttribution:
        return cls(
            required=bool(data.get("required", False)),
            text=data.get("text"),
            url=data.get("url"),
            license_name=data.get("license_name"),
        )


def _serialize_value(val: Any) -> Any:
    if isinstance(val, (datetime, date)):
        return val.isoformat()
    if isinstance(val, ItemKind):
        return val.value
    if dataclasses.is_dataclass(val) and not isinstance(val, type):
        return _serialize_dict(asdict(val))
    if isinstance(val, dict):
        return _serialize_dict(val)
    if isinstance(val, (list, tuple, set, frozenset)):
        return [_serialize_value(v) for v in val]
    return val


def _serialize_dict(d: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for k, v in d.items():
        if v is not None:
            result[k] = _serialize_value(v)
    return result


@dataclass(frozen=True)
class NormalizedProviderEnvelopeV1:
    schema_version: str
    provider: str
    provider_item_id: str
    kind: str
    normalized: dict[str, Any]
    provenance: ProviderProvenance
    images: list[ProviderImageRef]
    attribution: ProviderAttribution

    @classmethod
    def create(
        cls,
        *,
        provider: str,
        provider_item_id: str,
        kind: str | ItemKind,
        normalized: NormalizedItem | dict[str, Any],
        capabilities: ProviderCapabilities | None = None,
        source_url: str | None = None,
        raw_payload_hash: str | None = None,
        provider_version: str | None = None,
        fetched_at: str | None = None,
        extra_images: list[ProviderImageRef] | None = None,
    ) -> NormalizedProviderEnvelopeV1:
        kind_str = kind.value if isinstance(kind, ItemKind) else str(kind)
        norm_dict = (
            _serialize_dict(asdict(normalized))
            if dataclasses.is_dataclass(normalized) and not isinstance(normalized, type)
            else _serialize_dict(dict(normalized))  # type: ignore[arg-type]
        )

        # Build images from NormalizedItem if available
        images: list[ProviderImageRef] = []
        cover_url = norm_dict.get("cover_image_url")
        if cover_url:
            images.append(
                ProviderImageRef(
                    provider=provider,
                    url=cover_url,
                    kind="cover",
                    cache_policy=capabilities.cache_policy if capabilities else None,
                    attribution=capabilities.display_name if capabilities and capabilities.requires_attribution else None,
                )
            )

        variant_covers = norm_dict.get("variant_covers") or []
        for vc in variant_covers:
            if isinstance(vc, dict) and vc.get("cover_image_url"):
                images.append(
                    ProviderImageRef(
                        provider=provider,
                        url=vc["cover_image_url"],
                        kind="variant_cover",
                        thumbnail_url=vc.get("thumbnail_image_url"),
                        cache_policy=capabilities.cache_policy if capabilities else None,
                        attribution=capabilities.display_name if capabilities and capabilities.requires_attribution else None,
                    )
                )

        if extra_images:
            images.extend(extra_images)

        provenance = ProviderProvenance(
            fetched_at=fetched_at or datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            source_url=source_url or (capabilities.attribution_url if capabilities else None),
            raw_payload_hash=raw_payload_hash,
            provider_version=provider_version,
        )

        attribution = ProviderAttribution(
            required=capabilities.requires_attribution if capabilities else False,
            text=f"Data provided by {capabilities.display_name}" if capabilities and capabilities.requires_attribution else None,
            url=capabilities.attribution_url if capabilities else None,
            license_name=capabilities.license_name if capabilities else None,
        )

        return cls(
            schema_version="v1",
            provider=provider,
            provider_item_id=str(provider_item_id),
            kind=kind_str,
            normalized=norm_dict,
            provenance=provenance,
            images=images,
            attribution=attribution,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "provider": self.provider,
            "provider_item_id": self.provider_item_id,
            "kind": self.kind,
            "normalized": self.normalized,
            "provenance": self.provenance.to_dict(),
            "images": [img.to_dict() for img in self.images],
            "attribution": self.attribution.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NormalizedProviderEnvelopeV1:
        return cls(
            schema_version=data.get("schema_version", "v1"),
            provider=data["provider"],
            provider_item_id=str(data["provider_item_id"]),
            kind=data["kind"],
            normalized=dict(data.get("normalized") or {}),
            provenance=ProviderProvenance.from_dict(data.get("provenance") or {"fetched_at": ""}),
            images=[ProviderImageRef.from_dict(img) for img in (data.get("images") or [])],
            attribution=ProviderAttribution.from_dict(data.get("attribution") or {}),
        )
