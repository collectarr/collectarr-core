"""Canonical normalization helpers used after the provider boundary."""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.providers.base import NormalizedCredit, NormalizedItem, NormalizedVariantCover
from app.storage.images import MirroredImage
from app.types import JsonObject

_PUNCTUATION_RE = re.compile(r"[-–—”:;,.]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_THE_PREFIX_RE = re.compile(r"^the\s+", flags=re.IGNORECASE)
_AND_WORD_RE = re.compile(r"\band\b", flags=re.IGNORECASE)
_ISSUE_NUM_RE = re.compile(r"^(?P<number>\d+(?:\.\d+)?)\s*(?P<suffix>[A-Za-z]*)$")
_EDITOR_TITLE_RE = re.compile(
    r"\s*\((?:editor|ed\.?|group\s+editor|executive\s+editor|associate\s+editor|assistant\s+editor)\)\s*$",
    flags=re.IGNORECASE,
)
_NAME_SUFFIX_RE = re.compile(
    r",?\s+(?:Jr\.?|Sr\.?|III|II|IV|Esq\.?)\s*$",
    flags=re.IGNORECASE,
)

_CANONICAL_CREDIT_ROLES = {
    "script": "writer",
    "pencils": "penciller",
    "inks": "inker",
    "colors": "colorist",
    "letters": "letterer",
    "editing": "editor",
}


def normalize_title(value: str | None) -> str:
    """Normalize a title for comparison and lookup."""
    text = unicodedata.normalize("NFD", str(value or ""))
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = _PUNCTUATION_RE.sub(" ", text.casefold())
    return " ".join(_NON_ALNUM_RE.sub("", text).split())


def title_aliases(title: str) -> list[str]:
    """Return up to five deduplicated search-friendly title aliases."""
    normalized = " ".join(title.split())
    aliases = [normalized]

    without_the = _THE_PREFIX_RE.sub("", normalized).strip()
    if without_the and without_the != normalized:
        aliases.append(without_the)
    elif normalized:
        aliases.append(f"The {normalized}")

    if "&" in normalized:
        aliases.append(normalized.replace("&", "and"))
    if " and " in normalized.casefold():
        aliases.append(_AND_WORD_RE.sub("&", normalized))

    spaced = _PUNCTUATION_RE.sub(" ", normalized).strip()
    if spaced:
        aliases.append(" ".join(spaced.split()))

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = normalize_title(alias)
        if key and key not in seen:
            seen.add(key)
            deduped.append(alias)
    return deduped[:5]


def preview_names(credits: Sequence[NormalizedCredit]) -> list[str]:
    """Return up to three unique display names from credits."""
    names: list[str] = []
    seen: set[str] = set()
    for credit in credits:
        name = credit.name.strip()
        if not name or name.casefold() in seen:
            continue
        seen.add(name.casefold())
        names.append(name)
        if len(names) == 3:
            break
    return names


def normalize_person_name(name: str) -> str:
    """Normalize a person name for canonical deduplication."""
    text = name.strip()
    if not text:
        return ""
    text = _EDITOR_TITLE_RE.sub("", text).strip()
    text = _NAME_SUFFIX_RE.sub("", text).strip()
    parts = text.split(",", 1)
    if len(parts) == 2 and parts[1].strip():
        text = f"{parts[1].strip()} {parts[0].strip()}"
    return " ".join(text.split())


def canonical_credit_role(role: str | None) -> str | None:
    """Map known provider role labels to canonical credit roles."""
    if not role or not role.strip():
        return None
    value = role.strip()
    return _CANONICAL_CREDIT_ROLES.get(value.casefold(), value)


def normalize_arc_title(title: str) -> str:
    """Normalize a story arc title while removing trailing part markers."""
    text = re.sub(
        r",?\s+(?:Part|Chapter|Pt\.?|Ch\.?)\s+\w+\s*$",
        "",
        title.strip(),
        flags=re.IGNORECASE,
    )
    return normalize_title(text)


def issue_sort_key(value: str | None) -> tuple[int, float, str, str]:
    """Sort numeric issue numbers before alphanumeric values."""
    text = (value or "").strip()
    if not text:
        return (2, 0.0, "", "")
    match = _ISSUE_NUM_RE.match(text)
    if match:
        return (0, float(match.group("number")), match.group("suffix").upper(), text)
    return (1, 0.0, "", text.casefold())


def physical_format_for_normalized(normalized: NormalizedItem) -> PhysicalFormatConfig | None:
    if not is_video_item_kind(normalized.kind):
        return None
    candidate = normalized.physical_format or normalized.edition_format
    return physical_format_for_id(candidate) if candidate else None


def variant_cover_name(cover: NormalizedVariantCover, index: int) -> str:
    name = cover.name.strip() if cover.name else ""
    return name[:255] if name else f"Variant cover {index}"


def cover_metadata(source_url: str | None, mirrored_cover: MirroredImage | None) -> JsonObject:
    if mirrored_cover is not None:
        return {
            "cover_status": "mirrored",
            "cover_source_url": source_url,
            "cover_delivery_url": mirrored_cover.url,
            "cover_storage": "object_storage",
            "cover_policy": "minio_mirror",
        }
    if source_url:
        return {
            "cover_status": "external_url",
            "cover_source_url": source_url,
            "cover_delivery_url": source_url,
            "cover_storage": "provider_external_url",
            "cover_policy": "external_url_default",
        }
    return {
        "cover_status": "missing",
        "cover_source_url": None,
        "cover_delivery_url": None,
        "cover_storage": "generated_client_fallback",
        "cover_policy": "generated_cover_fallback",
    }


def normalized_release_status(value: str | None) -> str | None:
    text = " ".join(str(value or "").split()).strip().lower()
    return text or None


def normalized_language(value: str | None) -> str | None:
    text = " ".join(str(value or "").split()).strip().lower()
    return text if text and re.fullmatch(r"[a-z]{2,3}(?:-[a-z0-9]{2,8})*", text) else None


def normalized_region(value: str | None) -> str | None:
    text = " ".join(str(value or "").split()).strip().upper()
    return text if text and re.fullmatch(r"[A-Z]{2}(?:-[A-Z0-9]{1,3})?", text) else None


def normalized_identifier(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value).strip().lower())


def book_identifier_type(base_type: str, value: str) -> str:
    normalized = normalized_identifier(value)
    if base_type == "isbn":
        return "isbn10" if len(normalized) == 10 else "isbn13"
    if base_type == "upc":
        return "ean" if len(normalized) == 13 else "upc"
    return base_type


def comic_identifier_type(base_type: str, value: str) -> str:
    return book_identifier_type(base_type, value)
