import asyncio
import logging
import re
from datetime import date
from html import unescape
from typing import Any, Mapping

import httpx
from fastapi import HTTPException, status

from app.core.config import get_settings
from app.models.base import ItemKind
from app.providers.base import NormalizedItem, ProviderItem, ProviderSearchResult


_TAG_RE = re.compile(r"<[^>]+>")
_RESOURCE_ID_RE = re.compile(r"/(issue|volume)/(\d+-\d+)/?")
_SLUG_RE = re.compile(r"[^a-z0-9]+")
logger = logging.getLogger(__name__)


class ComicVineProvider:
    name = "comicvine"

    def __init__(self) -> None:
        self.settings = get_settings()

    async def search(self, query: str) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        if not self._is_configured:
            return [
                ProviderSearchResult(
                    provider=self.name,
                    provider_item_id=f"stub-comic-{self._slug(normalized_query)}",
                    title=f"{normalized_query} (ComicVine stub)",
                    kind=ItemKind.comic,
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
            search_result = self._search_result(result)
            if search_result.provider_item_id:
                normalized_results.append(search_result)
        return normalized_results

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        if not self._is_configured:
            title = provider_item_id.removeprefix("stub-comic-").replace("-", " ").title()
            return ProviderItem(
                provider=self.name,
                provider_item_id=provider_item_id,
                raw={"id": provider_item_id, "name": title, "issue_number": None},
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
                        "image",
                        "volume",
                    ]
                )
            },
        )
        raw = payload.get("results") or {}
        if not isinstance(raw, Mapping):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid ComicVine item")

        return ProviderItem(provider=self.name, provider_item_id=canonical_id, raw=raw)

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        provider_item_id = self._resource_id(data, "issue") or str(data.get("id") or "")
        if provider_item_id and provider_item_id.isdigit():
            provider_item_id = f"4000-{provider_item_id}"

        volume = data.get("volume") if isinstance(data.get("volume"), Mapping) else {}
        volume_name = str(volume.get("name") or "").strip() or None
        volume_id = self._resource_id(volume, "volume")

        issue_name = str(data.get("name") or "").strip()
        issue_number = str(data.get("issue_number") or "").strip() or None
        title = volume_name or issue_name or "Unknown comic"
        edition_title = issue_name or "Standard Edition"

        return NormalizedItem(
            kind=ItemKind.comic,
            title=title,
            item_number=issue_number,
            synopsis=self._clean_text(data.get("description") or data.get("deck")),
            series_title=volume_name,
            volume_name=volume_name,
            volume_start_year=self._year(data.get("cover_date") or data.get("store_date")),
            edition_title=edition_title,
            edition_format="Single Issue",
            publisher=self._publisher(volume),
            release_date=self._date(data.get("cover_date") or data.get("store_date")),
            cover_image_url=self._image_url(data.get("image")),
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
                    if exc.response.status_code in {429, 500, 502, 503, 504} and attempt < attempts - 1:
                        await self._backoff(exc.response, attempt)
                        continue
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail=f"ComicVine returned HTTP {exc.response.status_code}",
                    ) from exc
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt < attempts - 1:
                        await self._backoff(None, attempt)
                        continue
                    raise HTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        detail="ComicVine request failed",
                    ) from exc
            else:
                logger.warning("ComicVine request exhausted retries for %s", path)
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="ComicVine request failed",
                ) from last_error

        if not isinstance(payload, dict):
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Invalid ComicVine response")
        if payload.get("status_code") not in {1, "1"}:
            error = payload.get("error") or "ComicVine API error"
            raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(error))
        return payload

    @property
    def _is_configured(self) -> bool:
        return bool(self.settings.comicvine_api_key and self.settings.comicvine_api_key.strip())

    async def _backoff(self, response: httpx.Response | None, attempt: int) -> None:
        retry_after = response.headers.get("Retry-After") if response is not None else None
        delay = self._retry_after_seconds(retry_after) or min(0.5 * (2**attempt), 3.0)
        await asyncio.sleep(delay)

    def _search_result(self, result: Mapping[str, Any]) -> ProviderSearchResult:
        volume = result.get("volume") if isinstance(result.get("volume"), Mapping) else {}
        volume_name = str(volume.get("name") or "").strip()
        issue_name = str(result.get("name") or "").strip()
        issue_number = str(result.get("issue_number") or "").strip()
        title_parts = [part for part in [volume_name, f"#{issue_number}" if issue_number else "", issue_name] if part]
        title = " ".join(title_parts) or issue_name or volume_name or "Unknown ComicVine issue"
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=self._resource_id(result, "issue") or str(result.get("id") or ""),
            title=title,
            kind=ItemKind.comic,
            summary=self._clean_text(result.get("deck") or result.get("description")),
            image_url=self._image_url(result.get("image")),
        )

    def _issue_resource_id(self, provider_item_id: str) -> str:
        if re.fullmatch(r"\d+-\d+", provider_item_id):
            return provider_item_id
        if provider_item_id.isdigit():
            return f"4000-{provider_item_id}"
        return provider_item_id

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
