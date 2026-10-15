"""Automatic sort titles for catalog items.

A leading English article moves to the end ("The Wall" -> "Wall, The") so
titles sort by their first significant word. Titles without an article sort
as written. Explicit sort titles always win; automatic ones follow the title.
"""

import re

_LEADING_ARTICLE = re.compile(r"^(the|a|an)\s+(?=\S)", re.IGNORECASE)


def automatic_sort_title(title: str) -> str:
    match = _LEADING_ARTICLE.match(title)
    if match is None:
        return title
    return f"{title[match.end():]}, {match.group(1)}"


def resolve_sort_title(title: str, explicit: str | None) -> str:
    """Return the explicit sort title, or derive one from the title."""
    return explicit if explicit else automatic_sort_title(title)


def follow_title_change(old_title: str, new_title: str, current: str | None) -> str | None:
    """Keep an automatic sort title in step with a corrected title.

    A sort title that a person entered (one that differs from the automatic
    value of the old title) is preserved.
    """
    if current is None or current == automatic_sort_title(old_title):
        return automatic_sort_title(new_title)
    return current
