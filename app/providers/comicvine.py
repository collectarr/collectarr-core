import asyncio
import logging
import re
from dataclasses import dataclass
from datetime import date
from html import unescape
from typing import Any, Mapping

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedCredit,
    NormalizedItem,
    NormalizedVariantCover,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


_TAG_RE = re.compile(r"<[^>]+>")
_RESOURCE_ID_RE = re.compile(r"/(issue|volume)/(\d+-\d+)/?")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
_VARIANT_STOP_WORDS = {
    "a",
    "an",
    "and",
    "by",
    "cover",
    "edition",
    "for",
    "of",
    "the",
    "variant",
}
_DISTINCTIVE_VARIANT_TERMS = {
    "black",
    "blank",
    "foil",
    "incentive",
    "nycc",
    "ratio",
    "printing",
    "sketch",
    "virgin",
    "white",
}
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ComicVineIssueCover:
    provider_item_id: str
    image_url: str
    site_detail_url: str | None = None


class ComicVineProvider:
    name = "comicvine"
    capabilities = ProviderCapabilities(
        kind=ItemKind.comic,
        kinds=(ItemKind.comic, ItemKind.manga),
        display_name="Comic Vine",
        requires_user_key=True,
        non_commercial_only=True,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="Comic Vine API Terms",
        terms_url="https://comicvine.gamespot.com/api/",
        attribution_url="https://comicvine.gamespot.com/",
        rate_limit="200 requests per resource per hour, plus velocity detection.",
        cache_policy="Cache per instance to reduce duplicate API calls; do not redistribute.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        target_kind = self._target_kind(kind)
        if not self._is_configured:
            return [
                ProviderSearchResult(
                    provider=self.name,
                    provider_item_id=f"stub-{target_kind.value}-{self._slug(normalized_query)}",
                    title=f"{normalized_query} (ComicVine stub)",
                    kind=target_kind,
                    summary="Set COMICVINE_API_KEY to enable live ComicVine metadata.",
                )
            ]

        payload = await self._request(
            "search/",
            {
                "query": normalized_query,
                "resources": "issue",
                "limit": self.settings.comicvine_search_limit,
                "field_list": ",".join(
                    [
                        "id",
                        "api_detail_url",
                        "name",
                        "issue_number",
                        "deck",
                        "description",
                        "image",
                        "volume",
                    ]
                ),
            },
        )
        results = payload.get("results") or []
        if not isinstance(results, list):
            return []

        normalized_results = []
        for result in results:
            if not isinstance(result, Mapping):
                continue
            search_result = self._search_result(result, target_kind)
            if search_result.provider_item_id:
                normalized_results.append(search_result)
        return normalized_results

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        target_kind, _ = self._kind_and_resource_id(provider_item_id)
        if not self._is_configured:
            stub_prefix = f"stub-{target_kind.value}-"
            title = provider_item_id.removeprefix(stub_prefix).replace("-", " ").title()
            return ProviderItem(
                provider=self.name,
                provider_item_id=provider_item_id,
                raw={
                    "id": provider_item_id,
                    "name": title,
                    "issue_number": None,
                    "media_type": target_kind.value,
                },
            )

        canonical_id = self._issue_resource_id(provider_item_id)
        payload = await self._request(
            f"issue/{canonical_id}/",
            {
                "field_list": ",".join(
                    [
                        "id",
                        "api_detail_url",
                        "site_detail_url",
                        "name",
                        "issue_number",
                        "deck",
                        "description",
                        "cover_date",
                        "store_date",
                        "number_of_pages",
                        "person_credits",
                        "character_credits",
                        "story_arc_credits",
                        "image",
                        "associated_images",
                        "volume",
                    ]
                )
            },
        )
        raw = payload.get("results") or {}
        if not isinstance(raw, Mapping):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="comicvine_invalid_item",
                detail="Invalid ComicVine item",
            )

        raw = dict(raw)
        raw["media_type"] = target_kind.value
        return ProviderItem(
            provider=self.name,
            provider_item_id=self._provider_item_id(target_kind, canonical_id),
            raw=raw,
        )

    async def find_issue_cover(
        self,
        *,
        series_title: str,
        issue_number: str,
        start_year: int | None = None,
        variant_hint: str | None = None,
        require_variant_match: bool = False,
    ) -> ComicVineIssueCover | None:
        normalized_series = " ".join(series_title.split())
        normalized_issue = " ".join(issue_number.split())
        if not normalized_series or not normalized_issue or not self._is_configured:
            return None

        volume = await self._find_volume(normalized_series, start_year)
        if volume is None:
            return None

        volume_id = self._numeric_resource_id(volume, "volume")
        if volume_id is None:
            return None

        payload = await self._request(
            "issues/",
            {
                "filter": f"volume:{volume_id},issue_number:{normalized_issue}",
                "limit": 5,
                "field_list": ",".join(
                    [
                        "id",
                        "api_detail_url",
                        "site_detail_url",
                        "name",
                        "issue_number",
                        "deck",
                        "description",
                        "image",
                        "associated_images",
                    ]
                ),
            },
        )
        issues = payload.get("results") or []
        if not isinstance(issues, list):
            return None

        candidates: list[tuple[int, int, int, int, str, str, str | None]] = []
        for index, issue in enumerate(issues):
            if not isinstance(issue, Mapping):
                continue
            if str(issue.get("issue_number") or "").strip() != normalized_issue:
                continue
            provider_item_id = self._resource_id(issue, "issue")
            if not provider_item_id:
                continue
            for image_index, image_candidate in enumerate(self._issue_image_candidates(issue)):
                image_url = image_candidate["url"]
                image_haystack = image_candidate["haystack"]
                variant_score = self._variant_cover_score(image_haystack, variant_hint)
                if require_variant_match:
                    haystack_terms = self._variant_haystack_terms(image_haystack)
                    if not self._has_required_variant_terms(variant_hint, haystack_terms):
                        continue
                    if variant_score < self._min_variant_cover_score(variant_hint):
                        continue
                candidates.append(
                    (
                        variant_score,
                        image_candidate["priority"],
                        -index,
                        -image_index,
                        provider_item_id,
                        image_url,
                        self._optional_text(issue.get("site_detail_url")),
                    )
                )
        if not candidates:
            return None

        _, _, _, _, provider_item_id, image_url, site_detail_url = max(candidates)
        return ComicVineIssueCover(
            provider_item_id=provider_item_id,
            image_url=image_url,
            site_detail_url=site_detail_url,
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        kind = self._kind_from_raw(data)
        provider_item_id = self._resource_id(data, "issue") or str(data.get("id") or "")
        if provider_item_id and provider_item_id.isdigit():
            provider_item_id = f"4000-{provider_item_id}"
        provider_item_id = self._provider_item_id(kind, provider_item_id)

        volume = data.get("volume") if isinstance(data.get("volume"), Mapping) else {}
        volume_name = str(volume.get("name") or "").strip() or None
        volume_id = self._provider_item_id(kind, self._resource_id(volume, "volume"))

        issue_name = str(data.get("name") or "").strip()
        issue_number = str(data.get("issue_number") or "").strip() or None
        title = volume_name or issue_name or f"Unknown {kind.value}"
        edition_title = issue_name or "Standard Edition"

        return NormalizedItem(
            kind=kind,
            title=title,
            item_number=issue_number,
            synopsis=self._clean_text(data.get("description") or data.get("deck")),
            series_title=volume_name,
            volume_name=volume_name,
            volume_start_year=self._year(data.get("cover_date") or data.get("store_date")),
            page_count=self._int_value(data.get("number_of_pages")),
            edition_title=edition_title,
            edition_format="Single Issue" if kind == ItemKind.comic else "Manga Issue",
            publisher=self._publisher(volume),
            release_date=self._date(data.get("cover_date") or data.get("store_date")),
            cover_image_url=self._image_url(data.get("image")),
            variant_covers=self._associated_variant_covers(data),
            creators=self._credits(data.get("person_credits"), default_role="Creator"),
            characters=self._credits(data.get("character_credits")),
            story_arcs=self._credits(data.get("story_arc_credits")),
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            volume_provider_ids={self.name: volume_id} if volume_id else {},
        )

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        request_params = {
            "api_key": self.settings.comicvine_api_key.strip()
            if self.settings.comicvine_api_key
            else "",
            "format": "json",
            **params,
        }
        headers = {"User-Agent": self.settings.comicvine_user_agent}
        url = f"{self.settings.comicvine_base_url.rstrip('/')}/{path.lstrip('/')}"
        attempts = max(1, self.settings.comicvine_retry_attempts + 1)
        last_error: Exception | None = None
        payload: Any = None
        async with httpx.AsyncClient(
            timeout=self.settings.comicvine_timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(url, params=request_params)
                    if response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                        await self._backoff(response, attempt)
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    break
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if (
                        exc.response.status_code in {429, 500, 502, 503, 504}
                        and attempt < attempts - 1
                    ):
                        await self._backoff(exc.response, attempt)
                        continue
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code="comicvine_http_error",
                        detail=f"ComicVine returned HTTP {exc.response.status_code}",
                    ) from exc
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt < attempts - 1:
                        await self._backoff(None, attempt)
                        continue
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code="comicvine_request_failed",
                        detail="ComicVine request failed",
                    ) from exc
            else:
                logger.warning("ComicVine request exhausted retries for %s", path)
                raise ApiHTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    code="comicvine_request_failed",
                    detail="ComicVine request failed",
                ) from last_error

        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="comicvine_invalid_response",
                detail="Invalid ComicVine response",
            )
        if payload.get("status_code") not in {1, "1"}:
            error = payload.get("error") or "ComicVine API error"
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="comicvine_api_error",
                detail=str(error),
            )
        return payload

    @property
    def is_configured(self) -> bool:
        return self._is_configured

    @property
    def status_message(self) -> str:
        return (
            "ComicVine API key configured."
            if self._is_configured
            else "Set COMICVINE_API_KEY to enable live ComicVine metadata."
        )

    @property
    def _is_configured(self) -> bool:
        return bool(self.settings.comicvine_api_key and self.settings.comicvine_api_key.strip())

    async def _backoff(self, response: httpx.Response | None, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        delay = self._retry_after_seconds(retry_after) or min(0.5 * (2**attempt), 3.0)
        await asyncio.sleep(delay)

    def _search_result(
        self,
        result: Mapping[str, Any],
        kind: ItemKind | None = None,
    ) -> ProviderSearchResult:
        target_kind = self._target_kind(kind)
        volume = result.get("volume") if isinstance(result.get("volume"), Mapping) else {}
        volume_name = str(volume.get("name") or "").strip()
        issue_name = str(result.get("name") or "").strip()
        issue_number = str(result.get("issue_number") or "").strip()
        title_parts = [
            part
            for part in [volume_name, f"#{issue_number}" if issue_number else "", issue_name]
            if part
        ]
        title = " ".join(title_parts) or issue_name or volume_name or "Unknown ComicVine issue"
        resource_id = self._resource_id(result, "issue") or str(result.get("id") or "")
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=self._provider_item_id(target_kind, resource_id),
            title=title,
            kind=target_kind,
            summary=self._clean_text(result.get("deck") or result.get("description")),
            image_url=self._image_url(result.get("image")),
        )

    def _issue_resource_id(self, provider_item_id: str) -> str:
        _, resource_id = self._kind_and_resource_id(provider_item_id)
        if re.fullmatch(r"\d+-\d+", resource_id):
            return resource_id
        if resource_id.isdigit():
            return f"4000-{resource_id}"
        return resource_id

    def _target_kind(self, kind: ItemKind | None) -> ItemKind:
        return kind if kind in self.capabilities.supported_kinds else ItemKind.comic

    def _kind_from_raw(self, data: Mapping[str, Any]) -> ItemKind:
        media_type = str(data.get("media_type") or data.get("kind") or "").strip().lower()
        return ItemKind.manga if media_type == ItemKind.manga.value else ItemKind.comic

    def _kind_and_resource_id(self, provider_item_id: str) -> tuple[ItemKind, str]:
        text = str(provider_item_id or "").strip()
        normalized = text.lower()
        for kind in (ItemKind.manga, ItemKind.comic):
            for separator in (":", "-"):
                prefix = f"{kind.value}{separator}"
                if normalized.startswith(prefix):
                    return kind, text[len(prefix) :]
        if normalized.startswith("stub-manga-"):
            return ItemKind.manga, text
        return ItemKind.comic, text

    def _provider_item_id(self, kind: ItemKind, resource_id: str | None) -> str:
        if not resource_id:
            return ""
        _, stripped = self._kind_and_resource_id(resource_id)
        if stripped.startswith("stub-") or kind == ItemKind.comic:
            return stripped
        return f"{kind.value}:{stripped}"

    def _slug(self, value: str) -> str:
        slug = _SLUG_RE.sub("-", value.lower()).strip("-")
        return slug or "untitled"

    def _retry_after_seconds(self, value: str | None) -> float | None:
        if value is None:
            return None
        try:
            return min(max(float(value), 0.0), 10.0)
        except ValueError:
            return None

    def _resource_id(self, data: Mapping[str, Any], resource: str) -> str | None:
        api_detail_url = str(data.get("api_detail_url") or "")
        match = _RESOURCE_ID_RE.search(api_detail_url)
        if match and match.group(1) == resource:
            return match.group(2)
        raw_id = data.get("id")
        if raw_id is None:
            return None
        prefix = "4000" if resource == "issue" else "4050"
        raw_id_text = str(raw_id)
        return raw_id_text if "-" in raw_id_text else f"{prefix}-{raw_id_text}"

    async def _find_volume(
        self, series_title: str, start_year: int | None
    ) -> Mapping[str, Any] | None:
        payload = await self._request(
            "search/",
            {
                "query": series_title,
                "resources": "volume",
                "limit": 10,
                "field_list": "id,api_detail_url,name,start_year,site_detail_url",
            },
        )
        results = payload.get("results") or []
        if not isinstance(results, list):
            return None

        volumes = [result for result in results if isinstance(result, Mapping)]
        exact = [
            volume
            for volume in volumes
            if self._normalize_title(volume.get("name")) == self._normalize_title(series_title)
        ]
        if start_year is not None:
            year_match = [
                volume
                for volume in exact
                if self._int_value(volume.get("start_year")) == start_year
            ]
            if year_match:
                return year_match[0]
        if exact:
            return exact[0]
        return volumes[0] if volumes else None

    def _numeric_resource_id(self, data: Mapping[str, Any], resource: str) -> str | None:
        resource_id = self._resource_id(data, resource)
        if not resource_id:
            return None
        return resource_id.split("-", 1)[-1]

    def _normalize_title(self, value: Any) -> str:
        return " ".join(str(value or "").casefold().split())

    def _variant_cover_score(self, haystack_source: Any, variant_hint: str | None) -> int:
        hint_terms = self._variant_terms(variant_hint)
        if not hint_terms:
            return 0
        haystack, haystack_terms = self._variant_haystack_terms(haystack_source)
        score = 0
        normalized_hint = " ".join(hint_terms)
        if normalized_hint and normalized_hint in haystack:
            score += 100
        for term in hint_terms:
            if term in haystack_terms or term in haystack:
                score += 1
        return score

    def _min_variant_cover_score(self, variant_hint: str | None) -> int:
        hint_terms = set(self._variant_terms(variant_hint))
        if not hint_terms:
            return 0
        return min(2, len(hint_terms))

    def _has_required_variant_terms(
        self, variant_hint: str | None, haystack: tuple[str, set[str]]
    ) -> bool:
        hint_terms = set(self._variant_terms(variant_hint))
        required_terms = hint_terms & _DISTINCTIVE_VARIANT_TERMS
        if not required_terms:
            return True
        haystack_text, haystack_terms = haystack
        return all(term in haystack_terms or term in haystack_text for term in required_terms)

    def _variant_haystack_terms(self, source: Any) -> tuple[str, set[str]]:
        if isinstance(source, Mapping):
            haystack_values = [
                source.get("name"),
                source.get("deck"),
                source.get("description"),
                source.get("site_detail_url"),
                source.get("caption"),
                source.get("image_tags"),
                source.get("url"),
                source.get("original_url"),
            ]
            haystack = self._normalize_title(
                " ".join(self._clean_text(value) or "" for value in haystack_values)
            )
        else:
            haystack = self._normalize_title(self._clean_text(source) or "")
        return haystack, set(self._variant_terms(haystack))

    def _variant_terms(self, value: Any) -> list[str]:
        normalized = _SLUG_RE.sub(" ", str(value or "").casefold())
        return [
            term for term in normalized.split() if len(term) > 1 and term not in _VARIANT_STOP_WORDS
        ]

    def _clean_text(self, value: Any) -> str | None:
        if value is None:
            return None
        cleaned = _TAG_RE.sub(" ", unescape(str(value)))
        cleaned = " ".join(cleaned.split())
        return cleaned or None

    def _image_url(self, value: Any) -> str | None:
        if not isinstance(value, Mapping):
            return None
        for key in ("super_url", "screen_url", "medium_url", "small_url", "thumb_url"):
            image_url = value.get(key)
            if image_url:
                return str(image_url)
        return None

    def _image_urls(self, value: Any) -> set[str]:
        if not isinstance(value, Mapping):
            return set()
        urls = set()
        for key in (
            "super_url",
            "screen_url",
            "medium_url",
            "small_url",
            "thumb_url",
            "original_url",
        ):
            image_url = value.get(key)
            if image_url:
                urls.add(str(image_url))
        return urls

    def _issue_image_candidates(self, issue: Mapping[str, Any]) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        primary_url = self._image_url(issue.get("image"))
        if primary_url:
            candidates.append(
                {
                    "url": primary_url,
                    "haystack": issue,
                    "priority": 1,
                }
            )
        for image in self._associated_images(issue):
            image_url = self._associated_image_url(image)
            if not image_url:
                continue
            haystack = {
                "name": issue.get("name"),
                "deck": issue.get("deck"),
                "description": issue.get("description"),
                "site_detail_url": issue.get("site_detail_url"),
                "caption": image.get("caption"),
                "image_tags": image.get("image_tags"),
                "url": image_url,
                "original_url": image.get("original_url"),
            }
            candidates.append(
                {
                    "url": image_url,
                    "haystack": haystack,
                    "priority": 0,
                }
            )
        return candidates

    def _associated_variant_covers(
        self,
        data: Mapping[str, Any],
    ) -> list[NormalizedVariantCover]:
        associated_images = self._associated_images(data)
        if not associated_images:
            return []
        primary_urls = self._image_urls(data.get("image"))
        provider_item_id = self._resource_id(data, "issue") or str(data.get("id") or "") or None
        covers: list[NormalizedVariantCover] = []
        seen = set(primary_urls)
        for image in associated_images:
            image_url = self._associated_image_url(image)
            if not image_url or image_url in seen:
                continue
            seen.add(image_url)
            cover_index = len(covers) + 1
            covers.append(
                NormalizedVariantCover(
                    name=self._associated_variant_name(image, cover_index),
                    cover_image_url=image_url,
                    provider_item_id=provider_item_id,
                    source_id=self._optional_text(image.get("id")),
                    caption=self._optional_text(image.get("caption")),
                )
            )
        return covers

    def _associated_images(self, data: Mapping[str, Any]) -> list[Mapping[str, Any]]:
        images = data.get("associated_images")
        if not isinstance(images, list):
            return []
        return [image for image in images if isinstance(image, Mapping)]

    def _associated_image_url(self, image: Mapping[str, Any]) -> str | None:
        for key in (
            "original_url",
            "super_url",
            "screen_large_url",
            "screen_url",
            "medium_url",
            "small_url",
            "thumb_url",
        ):
            image_url = image.get(key)
            if image_url:
                return str(image_url)
        return None

    def _associated_variant_name(self, image: Mapping[str, Any], index: int) -> str:
        caption = self._clean_text(image.get("caption"))
        if caption and caption.casefold() not in {"all images", "cover"}:
            return caption[:255]
        return f"Variant cover {index}"

    def _date(self, value: Any) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(str(value)[:10])
        except ValueError:
            return None

    def _year(self, value: Any) -> int | None:
        parsed = self._date(value)
        return parsed.year if parsed else None

    def _publisher(self, volume: Mapping[str, Any]) -> str | None:
        publisher = volume.get("publisher")
        if isinstance(publisher, Mapping) and publisher.get("name"):
            return str(publisher["name"])
        return None

    def _credits(self, values: Any, *, default_role: str | None = None) -> list[NormalizedCredit]:
        if not isinstance(values, list):
            return []
        credits: list[NormalizedCredit] = []
        seen: set[tuple[str, str | None]] = set()
        for value in values:
            if not isinstance(value, Mapping):
                continue
            name = str(value.get("name") or "").strip()
            if not name:
                continue
            role = value.get("role") or value.get("roles") or default_role
            if isinstance(role, list):
                role = ", ".join(str(item).strip() for item in role if str(item).strip())
            role_text = str(role).strip() if role else None
            key = (name.casefold(), role_text.casefold() if role_text else None)
            if key in seen:
                continue
            seen.add(key)
            credits.append(
                NormalizedCredit(
                    name=name,
                    role=role_text,
                    api_detail_url=self._optional_text(value.get("api_detail_url")),
                    site_detail_url=self._optional_text(value.get("site_detail_url")),
                )
            )
        return credits

    def _int_value(self, value: Any) -> int | None:
        if value is None or value == "":
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
