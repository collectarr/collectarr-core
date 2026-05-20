"""Shared title and issue-number normalization for metadata providers."""

from __future__ import annotations

import re
import unicodedata

_PUNCTUATION_RE = re.compile(r"[-–—:;,]+")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9 ]+")
_THE_PREFIX_RE = re.compile(r"^the\s+", flags=re.IGNORECASE)
_AND_WORD_RE = re.compile(r"\band\b", flags=re.IGNORECASE)
_ISSUE_NUM_RE = re.compile(
    r"^(?P<number>\d+(?:\.\d+)?)\s*(?P<suffix>[A-Za-z]*)$"
)


def normalize_title(value: str | None) -> str:
    """Normalize a title for comparison: strip accents, casefold, collapse
    whitespace, and remove non-alphanumeric characters."""
    text = str(value or "")
    # Decompose unicode to strip combining marks (accents/diacritics)
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    text = text.casefold()
    # Replace punctuation with space before removing
    text = _PUNCTUATION_RE.sub(" ", text)
    text = _NON_ALNUM_RE.sub("", text)
    return " ".join(text.split())


def title_aliases(title: str) -> list[str]:
    """Generate search-friendly variations of a title.

    Returns up to 5 deduplicated aliases including the original.
    """
    normalized = " ".join(title.split())
    aliases = [normalized]

    # "The X" ↔ "X"
    without_the = _THE_PREFIX_RE.sub("", normalized).strip()
    if without_the and without_the != normalized:
        aliases.append(without_the)
    elif normalized:
        aliases.append(f"The {normalized}")

    # "&" ↔ "and"
    if "&" in normalized:
        aliases.append(normalized.replace("&", "and"))
    if " and " in normalized.casefold():
        aliases.append(_AND_WORD_RE.sub("&", normalized))

    # Hyphens/colons → spaces
    spaced = _PUNCTUATION_RE.sub(" ", normalized).strip()
    if spaced:
        aliases.append(" ".join(spaced.split()))

    deduped: list[str] = []
    seen: set[str] = set()
    for alias in aliases:
        key = normalize_title(alias)
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(alias)
    return deduped[:5]


def preview_names(credits: list) -> list[str]:
    """Return up to 3 unique display names from *credits* (case-insensitive dedup).

    Each element must have a ``.name`` attribute (e.g. ``NormalizedCredit``).
    """
    names: list[str] = []
    seen: set[str] = set()
    for credit in credits:
        name = credit.name.strip()
        if not name:
            continue
        key = name.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(name)
        if len(names) >= 3:
            break
    return names


def issue_sort_key(value: str | None) -> tuple[int, float, str, str]:
    """Return a sort key for an issue number that correctly orders numeric,
    decimal, and alphanumeric suffixes (e.g. 1, 1A, 1B, 2, 10, 10.1).

    Tuple: (has_number, numeric_part, suffix, original_text)
    - has_number: 0 if numeric, 1 if not → numbers sort first
    - numeric_part: float value for correct numeric ordering
    - suffix: uppercased letter suffix for sub-sorting
    - original_text: fallback for fully non-numeric values
    """
    text = (value or "").strip()
    if not text:
        return (2, 0.0, "", "")
    match = _ISSUE_NUM_RE.match(text)
    if match:
        number = float(match.group("number"))
        suffix = match.group("suffix").upper()
        return (0, number, suffix, text)
    return (1, 0.0, "", text.casefold())
