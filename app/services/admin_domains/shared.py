from app.catalog.media_types import media_type_for_kind
from app.models.base import ItemKind


def character_appearance_role(source_role: str | None) -> str:
    normalized = (source_role or "").strip().casefold()
    if "cameo" in normalized or "guest" in normalized:
        return "cameo"
    if "support" in normalized:
        return "supporting"
    if "main" in normalized or "lead" in normalized or "protagonist" in normalized:
        return "main"
    return "main"


def character_role_rank(role: str) -> int:
    if role == "main":
        return 3
    if role == "supporting":
        return 2
    if role == "cameo":
        return 1
    return 0


def sort_key(kind: ItemKind, title: str, item_number: str | None) -> str:
    media_type = media_type_for_kind(kind)
    padding = media_type.item_number_sort_padding if media_type else None
    normalized_number = item_number or ""
    if padding and normalized_number:
        normalized_number = normalized_number.zfill(padding)
    return f"{slug(title)}-{normalized_number}".strip("-")


def slug(value: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())
