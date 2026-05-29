import re
from typing import Any

from app.catalog.media_types import media_type_for_kind
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import NormalizedCredit


def provider_link_url_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _looks_like_api_url(value: str) -> bool:
    lowered = value.casefold()
    return "/api/" in lowered or "api." in lowered


def _provider_link_urls_from_value(value: Any) -> tuple[str | None, str | None]:
    site_url: str | None = None
    api_url: str | None = None
    if isinstance(value, dict):
        site_url = provider_link_url_text(
            value.get("site_detail_url")
            or value.get("site_url")
            or value.get("html_url")
            or value.get("web_url")
            or value.get("external_url")
            or value.get("permalink")
        )
        api_url = provider_link_url_text(value.get("api_detail_url") or value.get("api_url"))
        fallback_url = provider_link_url_text(value.get("url") or value.get("source_url"))
        if fallback_url:
            if api_url is None and _looks_like_api_url(fallback_url):
                api_url = fallback_url
            elif site_url is None:
                site_url = fallback_url
        return site_url, api_url
    fallback_url = provider_link_url_text(value)
    if fallback_url is None:
        return None, None
    if _looks_like_api_url(fallback_url):
        return None, fallback_url
    return fallback_url, None


def provider_link_urls_for_provider(
    provider: ExternalProvider,
    provider_ids: dict[str, str],
    raw_value: Any,
) -> dict[str, dict[str, str | None]] | None:
    provider_item_id = provider_ids.get(provider.value)
    if not provider_item_id:
        return None
    site_url, api_url = _provider_link_urls_from_value(raw_value)
    if site_url is None and api_url is None:
        return None
    return {provider.value: {"site_url": site_url, "api_url": api_url}}


def credit_provider_urls(credit: NormalizedCredit) -> dict[str, str | None] | None:
    if credit.site_detail_url is None and credit.api_detail_url is None:
        return None
    return {
        "site_url": credit.site_detail_url,
        "api_url": credit.api_detail_url,
    }


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


def comicvine_credit_provider_id(
    credit: NormalizedCredit,
    *,
    resource: str,
) -> str | None:
    for url in (credit.api_detail_url, credit.site_detail_url):
        if not url:
            continue
        match = re.search(rf"/{resource}/(?P<id>\d+-\d+)(?:/|$)", url)
        if match:
            return match.group("id")
    return None


def sort_key(kind: ItemKind, title: str, item_number: str | None) -> str:
    media_type = media_type_for_kind(kind)
    padding = media_type.item_number_sort_padding if media_type else None
    normalized_number = item_number or ""
    if padding and normalized_number:
        normalized_number = normalized_number.zfill(padding)
    return f"{slug(value=title)}-{normalized_number}".strip("-")


def slug(value: str) -> str:
    return "-".join("".join(char.lower() if char.isalnum() else " " for char in value).split())