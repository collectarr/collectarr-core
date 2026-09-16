from __future__ import annotations

from typing import Any


def model_text(model: object, attr: str) -> str | None:
    value = getattr(model, attr, None)
    if isinstance(value, str):
        text = value.strip()
        if text:
            return text
    return None


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


def entity_link_values(rows: list[object], link_type: str) -> list[dict[str, Any]]:
    links: list[dict[str, Any]] = []
    for row in rows:
        if getattr(row, "link_type", None) != link_type:
            continue
        url = str(getattr(row, "url", "") or "").strip()
        if not url:
            continue
        links.append(
            {
                "url": url,
                "site": getattr(row, "site", None),
                "name": getattr(row, "name", None),
                "kind": getattr(row, "kind", None),
                "description": getattr(row, "description", None),
            }
        )
    return links
