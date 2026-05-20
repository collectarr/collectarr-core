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

# Person-name normalization
_EDITOR_TITLE_RE = re.compile(
    r"\s*\("
    r"(?:editor|ed\.?|group\s+editor|executive\s+editor|associate\s+editor|assistant\s+editor)"
    r"\)\s*$",
    flags=re.IGNORECASE,
)
_NAME_SUFFIX_RE = re.compile(
    r",?\s+(?:Jr\.?|Sr\.?|III|II|IV|Esq\.?)\s*$",
    flags=re.IGNORECASE,
)

# GCD role → canonical role mapping
_GCD_ROLE_MAP: dict[str, str] = {
    "script": "writer",
    "pencils": "penciller",
    "inks": "inker",
    "colors": "colorist",
    "letters": "letterer",
    "editing": "editor",
}


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


def normalize_person_name(name: str) -> str:
    """Normalize a person name for cross-provider deduplication.

    Strips editor titles in parentheses, common suffixes (Jr., Sr., etc.),
    handles ``Last, First`` → ``First Last`` reordering, and collapses
    whitespace.
    """
    text = name.strip()
    if not text:
        return ""
    text = _EDITOR_TITLE_RE.sub("", text).strip()
    text = _NAME_SUFFIX_RE.sub("", text).strip()
    # "Last, First" → "First Last"
    parts = text.split(",", 1)
    if len(parts) == 2 and parts[1].strip():
        text = f"{parts[1].strip()} {parts[0].strip()}"
    return " ".join(text.split())


def canonical_credit_role(role: str | None) -> str | None:
    """Map a provider-specific credit role to a canonical name.

    GCD uses field names (``script``, ``pencils``, etc.) while ComicVine uses
    descriptive roles (``Writer``, ``Artist``).  This maps GCD-style names to
    canonical equivalents; unknown roles are returned as-is.
    """
    if not role or not role.strip():
        return None
    key = role.strip().casefold()
    return _GCD_ROLE_MAP.get(key, role.strip())


def normalize_arc_title(title: str) -> str:
    """Normalize a story-arc title for cross-provider matching.

    Strips trailing ``Part N`` / ``Chapter N`` markers and applies the same
    normalization as :func:`normalize_title`.
    """
    text = re.sub(
        r",?\s+(?:Part|Chapter|Pt\.?|Ch\.?)\s+\w+\s*$",
        "",
        title.strip(),
        flags=re.IGNORECASE,
    )
    return normalize_title(text)


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
