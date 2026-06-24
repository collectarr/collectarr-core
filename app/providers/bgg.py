import asyncio
import re
from collections.abc import Mapping
from datetime import date
from html import unescape
from typing import Any
from xml.etree import ElementTree

import httpx
from fastapi import status

from app.core.config import get_settings, provider_stub_data_enabled
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedCredit,
    NormalizedItem,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)
from app.providers.http_base import BaseHttpProvider

_BGG_ID_RE = re.compile(r"^\d+$")


class BGGProvider(BaseHttpProvider):
    name = "bgg"
    capabilities = ProviderCapabilities(
        kind=ItemKind.boardgame,
        display_name="BoardGameGeek",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=True,
        non_commercial_only=True,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="BoardGameGeek XML API Terms",
        terms_url="https://boardgamegeek.com/wiki/page/BGG_XML_API2",
        attribution_url="https://boardgamegeek.com/",
        rate_limit="BGG recommends keeping request volume low; roughly one request every 5 seconds.",
        cache_policy="Cache per instance to minimize XML API calls; do not redistribute as a competing database.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self.settings.bgg_api_token and self.settings.bgg_api_token.strip())

    @property
    def status_message(self) -> str:
        return (
            "BoardGameGeek API token configured."
            if self.is_configured
            else "Set BGG_API_TOKEN to enable live BoardGameGeek metadata."
        )

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        if not self.is_configured:
            if not provider_stub_data_enabled():
                return []
            return [
                ProviderSearchResult(
                    provider=self.name,
                    provider_item_id=f"stub-boardgame-{self._slug(normalized_query)}",
                    title=f"{normalized_query} (BoardGameGeek stub)",
                    kind=ItemKind.boardgame,
                    summary="Set BGG_API_TOKEN to enable live BoardGameGeek metadata.",
                )
            ]

        root = await self._request_xml(
            "search",
            {
                "query": normalized_query,
                "type": "boardgame",
            },
        )
        results: list[ProviderSearchResult] = []
        for item in root.findall("item")[: self.settings.bgg_search_limit]:
            search_result = self._search_result(item)
            if search_result.provider_item_id:
                results.append(search_result)
        return results

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        if not _BGG_ID_RE.fullmatch(provider_item_id):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="bgg_invalid_item_id",
                detail="Invalid BoardGameGeek item id",
            )
        root = await self._request_xml(
            "thing",
            {
                "id": provider_item_id,
                "type": "boardgame",
                "stats": "1",
            },
        )
        item = root.find("item")
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="bgg_item_not_found",
                detail="BoardGameGeek item not found",
            )
        return ProviderItem(
            provider=self.name,
            provider_item_id=provider_item_id,
            raw=self._thing_item_raw(item),
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        provider_item_id = self._optional_text(data.get("id"))
        title = self._primary_name(data) or "Unknown board game"
        year = self._int(data.get("yearpublished"))
        links = data.get("links") if isinstance(data.get("links"), list) else []
        publishers = self._link_values(links, "boardgamepublisher")
        designers = self._link_values(links, "boardgamedesigner")
        categories = self._link_values(links, "boardgamecategory")
        families = self._link_values(links, "boardgamefamily")

        minage = self._int(data.get("minage"))

        return NormalizedItem(
            kind=ItemKind.boardgame,
            title=title,
            synopsis=self._optional_text(data.get("description")),
            series_title=None,
            volume_name=title,
            volume_start_year=year,
            edition_title=title,
            edition_format="Board Game",
            publisher=publishers[0] if publishers else None,
            release_date=date(year, 1, 1) if year else None,
            cover_image_url=self._optional_text(data.get("image"))
            or self._optional_text(data.get("thumbnail")),
            creators=[NormalizedCredit(name=name, role="Designer") for name in designers],
            characters=[NormalizedCredit(name=name) for name in categories],
            story_arcs=[NormalizedCredit(name=name) for name in families],
            genres=[*categories, *[name for name in families if name not in categories]],
            series_group=families[0] if families else None,
            age_rating=f"Ages {minage}+" if minage else None,
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            volume_provider_ids={self.name: provider_item_id} if provider_item_id else {},
        )

    async def _request_xml(self, path: str, params: dict[str, Any]) -> ElementTree.Element:
        url = f"{self.settings.bgg_base_url.rstrip('/')}/{path.lstrip('/')}"
        headers = {
            "User-Agent": self.settings.bgg_user_agent,
            "Accept": "application/xml",
        }
        if self.settings.bgg_api_token:
            headers["Authorization"] = f"Bearer {self.settings.bgg_api_token.strip()}"

        attempts = max(1, self.settings.bgg_retry_attempts + 1)
        last_error: Exception | None = None
        async with httpx.AsyncClient(
            timeout=self.settings.bgg_timeout_seconds,
            headers=headers,
            follow_redirects=True,
        ) as client:
            for attempt in range(attempts):
                try:
                    response = await client.get(url, params=params)
                    if response.status_code in {202, 429, 500, 502, 503, 504}:
                        last_error = ApiHTTPException(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            code="bgg_request_pending",
                            detail="BoardGameGeek request is not ready yet",
                        )
                        if attempt < attempts - 1:
                            await asyncio.sleep(min(5.0, 1.0 + attempt))
                            continue
                    response.raise_for_status()
                    return ElementTree.fromstring(response.text)
                except httpx.HTTPStatusError as exc:
                    last_error = exc
                    if (
                        exc.response.status_code in {429, 500, 502, 503, 504}
                        and attempt < attempts - 1
                    ):
                        await asyncio.sleep(min(5.0, 1.0 + attempt))
                        continue
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code="bgg_http_error",
                        detail=f"BoardGameGeek returned HTTP {exc.response.status_code}",
                    ) from exc
                except (httpx.HTTPError, ElementTree.ParseError) as exc:
                    last_error = exc
                    if attempt < attempts - 1:
                        await asyncio.sleep(min(5.0, 1.0 + attempt))
                        continue
                    raise ApiHTTPException(
                        status_code=status.HTTP_502_BAD_GATEWAY,
                        code="bgg_request_failed",
                        detail="BoardGameGeek request failed",
                    ) from exc

        raise ApiHTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            code="bgg_request_pending",
            detail="BoardGameGeek request is not ready yet",
        ) from last_error

    def _search_result(self, item: ElementTree.Element) -> ProviderSearchResult:
        provider_item_id = item.attrib.get("id", "")
        title = self._element_value(item.find("name")) or "Unknown BoardGameGeek item"
        year = self._element_value(item.find("yearpublished"))
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=provider_item_id,
            title=title,
            kind=ItemKind.boardgame,
            summary=year,
        )

    def _thing_item_raw(self, item: ElementTree.Element) -> dict[str, Any]:
        links = [
            {
                "type": link.attrib.get("type"),
                "id": link.attrib.get("id"),
                "value": link.attrib.get("value"),
            }
            for link in item.findall("link")
        ]
        return {
            "id": item.attrib.get("id"),
            "type": item.attrib.get("type"),
            "names": [
                {
                    "type": name.attrib.get("type"),
                    "sortindex": name.attrib.get("sortindex"),
                    "value": name.attrib.get("value"),
                }
                for name in item.findall("name")
            ],
            "description": self._element_text(item.find("description")),
            "yearpublished": self._element_value(item.find("yearpublished")),
            "minplayers": self._element_value(item.find("minplayers")),
            "maxplayers": self._element_value(item.find("maxplayers")),
            "playingtime": self._element_value(item.find("playingtime")),
            "minplaytime": self._element_value(item.find("minplaytime")),
            "maxplaytime": self._element_value(item.find("maxplaytime")),
            "minage": self._element_value(item.find("minage")),
            "image": self._element_text(item.find("image")),
            "thumbnail": self._element_text(item.find("thumbnail")),
            "links": links,
        }

    def _primary_name(self, data: Mapping[str, Any]) -> str | None:
        names = data.get("names")
        if not isinstance(names, list):
            return None
        primary = next(
            (
                name
                for name in names
                if isinstance(name, Mapping) and name.get("type") == "primary"
            ),
            None,
        )
        if primary is None:
            primary = next((name for name in names if isinstance(name, Mapping)), None)
        return self._optional_text(primary.get("value") if primary else None)

    def _link_values(self, links: list[Any], link_type: str) -> list[str]:
        values: list[str] = []
        for link in links:
            if not isinstance(link, Mapping) or link.get("type") != link_type:
                continue
            value = self._optional_text(link.get("value"))
            if value:
                values.append(value)
        return values

    def _element_value(self, element: ElementTree.Element | None) -> str | None:
        return self._optional_text(element.attrib.get("value") if element is not None else None)

    def _element_text(self, element: ElementTree.Element | None) -> str | None:
        if element is None:
            return None
        return self._optional_text(unescape(element.text or ""))

    def _int(self, value: Any) -> int | None:
        try:
            number = int(str(value))
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
