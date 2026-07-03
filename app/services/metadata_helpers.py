from __future__ import annotations

from datetime import date
from typing import Any


def _metadata_text(metadata: dict[str, object] | None, key: str) -> str | None:
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _metadata_date(metadata: dict[str, object] | None, key: str) -> date | None:
    text = _metadata_text(metadata, key)
    if text is None:
        return None
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _model_text_or_metadata(model: object, attr: str, metadata_key: str | None = None) -> str | None:
    value = getattr(model, attr, None)
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    metadata = getattr(model, "metadata_json", None)
    return _metadata_text(metadata, metadata_key or attr)


def _loaded_rows(item: object, attr_name: str) -> list[object]:
    rows = getattr(item, "__dict__", {}).get(attr_name)
    if rows is None:
        return []
    return list(rows)


def _organization_name(item: object, role: str) -> str | None:
    rows = sorted(
        _loaded_rows(item, "organization_links"),
        key=lambda link: (
            str(getattr(link, "role", "") or "").casefold(),
            str(getattr(getattr(link, "organization", None), "name", "") or "").casefold(),
        ),
    )
    for link in rows:
        if getattr(link, "role", None) != role:
            continue
        organization = getattr(link, "organization", None)
        name = getattr(organization, "name", None)
        if name:
            return str(name)
    return None


def _metadata_list(metadata: dict[str, object] | None, key: str) -> list[str]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in value:
        text = str(raw or "").strip()
        if not text:
            continue
        normalized = text.casefold()
        if normalized in seen:
            continue
        seen.add(normalized)
        cleaned.append(text)
    return cleaned


def _metadata_links(metadata: dict[str, object] | None, key: str) -> list[dict[str, Any]]:
    if not isinstance(metadata, dict):
        return []
    value = metadata.get(key)
    if not isinstance(value, list):
        return []
    links: list[dict[str, Any]] = []
    for raw in value:
        if isinstance(raw, dict):
            link = dict(raw)
            if str(link.get("url") or "").strip():
                links.append(link)
    return links
