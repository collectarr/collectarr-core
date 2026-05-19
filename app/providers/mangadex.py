from datetime import date
from typing import Any, Mapping

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedCredit,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    NormalizedEpisode,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


class MangaDexProvider:
    name = "mangadex"
    capabilities = ProviderCapabilities(
        kind=ItemKind.manga,
        kinds=(ItemKind.manga,),
        display_name="MangaDex",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=False,
        non_commercial_only=False,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="MangaDex API Terms",
        terms_url="https://api.mangadex.org/docs/",
        attribution_url="https://mangadex.org/",
        rate_limit="5 req/s global; respect Retry-After headers.",
        cache_policy="Cache manga detail and chapter feeds to minimize API calls.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def status_message(self) -> str:
        return "MangaDex public API is available without authentication."

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        data = await self._request(
            "manga",
            {
                "title": normalized_query,
                "limit": self.settings.mangadex_search_limit,
                "includes[]": ["cover_art", "author"],
                "order[relevance]": "desc",
                "contentRating[]": ["safe", "suggestive", "erotica"],
            },
        )
        results_list = data.get("data") or []
        if not isinstance(results_list, list):
            return []
        return [
            self._search_result(item)
            for item in results_list
            if isinstance(item, Mapping)
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        manga_id = provider_item_id.strip()
        if not manga_id:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="mangadex_invalid_id",
                detail="Invalid MangaDex manga id",
            )
        data = await self._request(
            f"manga/{manga_id}",
            {"includes[]": ["cover_art", "author", "artist"]},
        )
        manga = data.get("data")
        if not isinstance(manga, Mapping):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="mangadex_not_found",
                detail="MangaDex manga not found",
            )
        return ProviderItem(
            provider=self.name,
            provider_item_id=manga_id,
            raw=dict(manga),
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        attrs = data.get("attributes") or {}
        title = self._title(attrs)
        manga_id = self._optional_text(data.get("id"))

        authors = self._authors(data.get("relationships"))
        genres = self._tags(attrs.get("tags"))
        start_date = self._date(attrs.get("year"))
        cover_url = self._cover_url(manga_id, data.get("relationships"))

        return NormalizedItem(
            kind=ItemKind.manga,
            title=title,
            synopsis=self._description(attrs.get("description")),
            series_title=title,
            volume_name=title,
            volume_start_year=attrs.get("year"),
            edition_title=title,
            edition_format="Manga",
            release_date=start_date,
            cover_image_url=cover_url,
            creators=authors,
            story_arcs=[NormalizedCredit(name=g) for g in genres],
            provider_ids={self.name: manga_id} if manga_id else {},
            volume_provider_ids={self.name: manga_id} if manga_id else {},
            relations=self._relations(data.get("relationships")),
        )

    async def get_volumes(self, provider_item_id: str) -> list[NormalizedSeason]:
        """Fetch chapter feed and group into volumes (NormalizedSeason = volume, NormalizedEpisode = chapter)."""
        manga_id = provider_item_id.strip()
        if not manga_id:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="mangadex_invalid_id",
                detail="Invalid MangaDex manga id",
            )
        chapters = await self._fetch_all_chapters(manga_id)
        return self._group_chapters_into_volumes(chapters)

    async def _fetch_all_chapters(self, manga_id: str) -> list[Mapping[str, Any]]:
        all_chapters: list[Mapping[str, Any]] = []
        offset = 0
        limit = self.settings.mangadex_feed_limit
        while True:
            data = await self._request(
                f"manga/{manga_id}/feed",
                {
                    "translatedLanguage[]": ["en"],
                    "order[volume]": "asc",
                    "order[chapter]": "asc",
                    "limit": limit,
                    "offset": offset,
                    "includes[]": ["scanlation_group"],
                },
            )
            batch = data.get("data") or []
            if not isinstance(batch, list):
                break
            all_chapters.extend(batch)
            total = data.get("total") or 0
            offset += limit
            if offset >= total:
                break
        return all_chapters

    def _group_chapters_into_volumes(
        self, chapters: list[Mapping[str, Any]]
    ) -> list[NormalizedSeason]:
        volume_map: dict[str, list[NormalizedEpisode]] = {}
        for ch in chapters:
            if not isinstance(ch, Mapping):
                continue
            attrs = ch.get("attributes") or {}
            vol = self._optional_text(attrs.get("volume")) or "0"
            ch_num = self._optional_text(attrs.get("chapter"))
            ch_title = self._optional_text(attrs.get("title")) or ""
            if ch_num is None:
                continue
            try:
                episode_number = int(float(ch_num))
            except (ValueError, TypeError):
                continue
            air_date = self._date_str(attrs.get("publishAt") or attrs.get("readableAt"))
            display_title = ch_title or f"Chapter {ch_num}"
            episode = NormalizedEpisode(
                episode_number=episode_number,
                title=display_title,
                overview=None,
                air_date=air_date,
                runtime_minutes=attrs.get("pages"),
                still_url=None,
            )
            volume_map.setdefault(vol, []).append(episode)

        seasons: list[NormalizedSeason] = []
        for vol_key in sorted(volume_map, key=lambda v: (float(v) if v.replace(".", "").isdigit() else 999)):
            try:
                vol_num = int(float(vol_key))
            except (ValueError, TypeError):
                vol_num = 0
            episodes = volume_map[vol_key]
            title = f"Volume {vol_key}" if vol_key != "0" else "Uncollected Chapters"
            seasons.append(
                NormalizedSeason(
                    season_number=vol_num,
                    title=title,
                    overview=None,
                    air_date=episodes[0].air_date if episodes else None,
                    episode_count=len(episodes),
                    poster_url=None,
                    episodes=episodes,
                )
            )
        return seasons

    async def _request(
        self, path: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        url = f"{self.settings.mangadex_base_url.rstrip('/')}/{path}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.mangadex_timeout_seconds,
                headers={
                    "User-Agent": self.settings.mangadex_user_agent,
                    "Accept": "application/json",
                },
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="mangadex_http_error",
                detail=f"MangaDex returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="mangadex_request_failed",
                detail="MangaDex request failed",
            ) from exc

    def _search_result(self, item: Mapping[str, Any]) -> ProviderSearchResult:
        attrs = item.get("attributes") or {}
        title = self._title(attrs)
        manga_id = self._optional_text(item.get("id")) or ""
        status_text = self._optional_text(attrs.get("status"))
        year = attrs.get("year")
        summary_parts = [
            self._optional_text(attrs.get("publicationDemographic")),
            status_text,
            str(year) if year else None,
        ]
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=manga_id,
            title=title,
            kind=ItemKind.manga,
            summary=" · ".join(p for p in summary_parts if p),
            image_url=self._cover_url(manga_id, item.get("relationships")),
        )

    def _title(self, attrs: Mapping[str, Any]) -> str:
        title_map = attrs.get("title") or {}
        if isinstance(title_map, Mapping):
            return (
                self._optional_text(title_map.get("en"))
                or self._optional_text(title_map.get("ja-ro"))
                or self._optional_text(title_map.get("ja"))
                or next((v for v in title_map.values() if v), None)
                or "Unknown"
            )
        return "Unknown"

    def _description(self, value: Any) -> str | None:
        if not isinstance(value, Mapping):
            return None
        return self._optional_text(value.get("en")) or next(
            (v for v in value.values() if v), None
        )

    def _cover_url(self, manga_id: str | None, relationships: Any) -> str | None:
        if not manga_id or not isinstance(relationships, list):
            return None
        for rel in relationships:
            if not isinstance(rel, Mapping):
                continue
            if rel.get("type") == "cover_art":
                attrs = rel.get("attributes") or {}
                filename = self._optional_text(attrs.get("fileName"))
                if filename:
                    return f"https://uploads.mangadex.org/covers/{manga_id}/{filename}.256.jpg"
        return None

    def _authors(self, relationships: Any) -> list[NormalizedCredit]:
        if not isinstance(relationships, list):
            return []
        credits: list[NormalizedCredit] = []
        for rel in relationships:
            if not isinstance(rel, Mapping):
                continue
            rel_type = rel.get("type")
            if rel_type not in ("author", "artist"):
                continue
            attrs = rel.get("attributes") or {}
            name = self._optional_text(attrs.get("name"))
            if name:
                role = "Author" if rel_type == "author" else "Artist"
                credits.append(NormalizedCredit(name=name, role=role))
        return credits

    def _tags(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        tags: list[str] = []
        for tag in value:
            if not isinstance(tag, Mapping):
                continue
            attrs = tag.get("attributes") or {}
            name_map = attrs.get("name") or {}
            if isinstance(name_map, Mapping):
                name = self._optional_text(name_map.get("en"))
                if name:
                    tags.append(name)
        return tags

    def _relations(self, relationships: Any) -> list[NormalizedRelation]:
        if not isinstance(relationships, list):
            return []
        relations: list[NormalizedRelation] = []
        relation_map = {
            "prequel": "prequel",
            "sequel": "sequel",
            "spin_off": "spin_off",
            "adapted_from": "adaptation",
            "side_story": "side_story",
            "alternate_story": "alternative",
            "alternate_version": "alternative",
        }
        for rel in relationships:
            if not isinstance(rel, Mapping):
                continue
            if rel.get("type") != "manga":
                continue
            related = self._optional_text(rel.get("related"))
            if not related or related not in relation_map:
                continue
            attrs = rel.get("attributes") or {}
            title_map = attrs.get("title") or {}
            title = "Unknown"
            if isinstance(title_map, Mapping):
                title = (
                    self._optional_text(title_map.get("en"))
                    or self._optional_text(title_map.get("ja-ro"))
                    or next((v for v in title_map.values() if v), "Unknown")
                )
            relations.append(
                NormalizedRelation(
                    relation_type=relation_map[related],
                    title=title,
                    provider=self.name,
                    provider_id=self._optional_text(rel.get("id")),
                    kind=ItemKind.manga,
                )
            )
        return relations

    def _date(self, year: Any) -> date | None:
        if year is None:
            return None
        try:
            return date(int(year), 1, 1)
        except (ValueError, TypeError):
            return None

    def _date_str(self, value: Any) -> date | None:
        text = self._optional_text(value)
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
