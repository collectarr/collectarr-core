import re
from datetime import date
from html import unescape
from typing import Any, Mapping

import httpx
from fastapi import status

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.providers.base import (
    NormalizedBundleMember,
    NormalizedBundleRelease,
    NormalizedCredit,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


_TAG_RE = re.compile(r"<[^>]+>")

_MEDIA_FIELDS = """
id
idMal
siteUrl
type
title {
  romaji
  english
  native
}
description(asHtml: false)
format
status
chapters
volumes
episodes
duration
startDate {
  year
  month
  day
}
coverImage {
  large
  medium
}
genres
staff(perPage: 10) {
  edges {
    role
    node {
      name {
        full
      }
      siteUrl
    }
  }
}
characters(perPage: 10) {
    edges {
        role
        node {
            name {
                full
            }
            siteUrl
            image {
                large
                medium
            }
        }
    }
}
relations {
  edges {
    relationType
    node {
      id
      type
      format
      title {
        romaji
        english
        native
      }
      startDate {
        year
      }
      coverImage {
        medium
      }
    }
  }
}
"""


class AniListProvider:
    name = "anilist"
    capabilities = ProviderCapabilities(
        kind=ItemKind.manga,
        kinds=(ItemKind.manga, ItemKind.anime),
        display_name="AniList",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=False,
        non_commercial_only=False,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="AniList API Terms",
        terms_url="https://anilist.gitbook.io/anilist-apiv2-docs/",
        attribution_url="https://anilist.co/",
        rate_limit="Public GraphQL API; keep request volume low and cache metadata.",
        cache_policy="Cache per instance to minimize GraphQL calls; preserve AniList attribution links.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def status_message(self) -> str:
        return "AniList public anime/manga metadata is available without OAuth."

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        target_kind = self._target_kind(kind)
        payload = await self._graphql(
            f"""
            query ($search: String, $perPage: Int) {{
              Page(page: 1, perPage: $perPage) {{
                media(search: $search, type: {self._anilist_type(target_kind)}) {{
                  id
                  type
                  title {{
                    romaji
                    english
                    native
                  }}
                  format
                  status
                  startDate {{
                    year
                  }}
                  coverImage {{
                    large
                    medium
                  }}
                                    characters(perPage: 3) {{
                                        edges {{
                                            node {{
                                                name {{
                                                    full
                                                }}
                                            }}
                                        }}
                                    }}
                }}
              }}
            }}
            """,
            {
                "search": normalized_query,
                "perPage": self.settings.anilist_search_limit,
            },
        )
        media = (((payload.get("data") or {}).get("Page") or {}).get("media") or [])
        if not isinstance(media, list):
            return []
        return [
            self._search_result(item, target_kind) for item in media if isinstance(item, Mapping)
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        kind, anilist_id = self._kind_and_media_id(provider_item_id)
        if anilist_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="anilist_invalid_media_id",
                detail="Invalid AniList media id",
            )
        payload = await self._graphql(
            f"""
            query ($id: Int) {{
              Media(id: $id, type: {self._anilist_type(kind)}) {{
                {_MEDIA_FIELDS}
              }}
            }}
            """,
            {"id": anilist_id},
        )
        media = (payload.get("data") or {}).get("Media")
        if not isinstance(media, Mapping):
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="anilist_media_not_found",
                detail="AniList media not found",
            )
        media = dict(media)
        media["media_type"] = kind.value
        return ProviderItem(
            provider=self.name,
            provider_item_id=self._provider_item_id(kind, anilist_id),
            raw=media,
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        kind = self._kind_from_raw(data)
        anilist_id = self._id(data.get("id"))
        provider_item_id = self._provider_item_id(kind, anilist_id) if anilist_id else ""
        title = self._title(data) or f"Unknown {kind.value}"
        start_date = self._date(data.get("startDate"))
        genres = self._list_text(data.get("genres"))
        bundle_release = self._bundle_release(
            data=data,
            kind=kind,
            provider_item_id=provider_item_id or None,
            title=title,
            start_date=start_date,
        )

        return NormalizedItem(
            kind=kind,
            title=title,
            synopsis=self._description(data.get("description")),
            series_title=title,
            volume_name=title,
            volume_start_year=start_date.year if start_date else None,
            runtime_minutes=self._int(data.get("duration")) if kind == ItemKind.anime else None,
            page_count=None,
            edition_title=title,
            edition_format=self._optional_text(data.get("format"))
            or ("Anime" if kind == ItemKind.anime else "Manga"),
            release_date=start_date,
            cover_image_url=self._cover_url(data),
            creators=self._staff(data.get("staff")),
            characters=self._characters(data.get("characters")),
            genres=genres,
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            volume_provider_ids={self.name: provider_item_id} if provider_item_id else {},
            relations=self._relations(data.get("relations"), kind),
            bundle_release=bundle_release,
        )

    async def _graphql(self, query: str, variables: dict[str, Any]) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.anilist_timeout_seconds,
                headers={
                    "User-Agent": self.settings.anilist_user_agent,
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                },
                follow_redirects=True,
            ) as client:
                response = await client.post(
                    self.settings.anilist_api_url,
                    json={"query": query, "variables": variables},
                )
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="anilist_http_error",
                detail=f"AniList returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="anilist_request_failed",
                detail="AniList request failed",
            ) from exc
        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="anilist_invalid_response",
                detail="Invalid AniList response",
            )
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            message = errors[0].get("message") if isinstance(errors[0], Mapping) else None
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="anilist_graphql_error",
                detail=str(message or "AniList GraphQL error"),
            )
        return payload

    def _search_result(
        self,
        item: Mapping[str, Any],
        kind: ItemKind | None = None,
    ) -> ProviderSearchResult:
        target_kind = self._target_kind(kind)
        title = self._title(item) or f"Unknown AniList {target_kind.value}"
        anilist_id = self._id(item.get("id"))
        provider_item_id = self._provider_item_id(target_kind, anilist_id) if anilist_id else ""
        start_date = item.get("startDate") if isinstance(item.get("startDate"), Mapping) else {}
        year = self._optional_text(start_date.get("year"))
        title_map = item.get("title") if isinstance(item.get("title"), Mapping) else {}
        romaji = self._optional_text(title_map.get("romaji"))
        english = self._optional_text(title_map.get("english"))
        alt_title = romaji if (english and romaji and romaji != english) else None
        summary_parts = [
            alt_title,
            self._optional_text(item.get("format")),
            self._optional_text(item.get("status")),
            year,
        ]
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=provider_item_id,
            title=title,
            kind=target_kind,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._cover_url(item),
            character_preview=self._character_preview(item.get("characters")),
        )

    def _target_kind(self, kind: ItemKind | None) -> ItemKind:
        return kind if kind in self.capabilities.supported_kinds else ItemKind.manga

    def _anilist_type(self, kind: ItemKind) -> str:
        return "ANIME" if kind == ItemKind.anime else "MANGA"

    def _kind_from_raw(self, data: Mapping[str, Any]) -> ItemKind:
        media_type = str(data.get("media_type") or "").strip().lower()
        anilist_type = str(data.get("type") or "").strip().upper()
        if media_type == "anime" or anilist_type == "ANIME":
            return ItemKind.anime
        return ItemKind.manga

    def _kind_and_media_id(self, value: Any) -> tuple[ItemKind, int | None]:
        text = str(value or "").strip()
        normalized = text.lower()
        for raw_prefix, mapped_kind in (("anime", ItemKind.anime), ("manga", ItemKind.manga)):
            for separator in (":", "-"):
                prefix = f"{raw_prefix}{separator}"
                if normalized.startswith(prefix):
                    return mapped_kind, self._id(text[len(prefix) :])
        return ItemKind.manga, self._id(text)

    def _provider_item_id(self, kind: ItemKind, anilist_id: int) -> str:
        if kind == ItemKind.manga:
            return str(anilist_id)
        return f"anime:{anilist_id}"

    def _title(self, data: Mapping[str, Any]) -> str | None:
        title = data.get("title") if isinstance(data.get("title"), Mapping) else {}
        return (
            self._optional_text(title.get("english"))
            or self._optional_text(title.get("romaji"))
            or self._optional_text(title.get("native"))
        )

    def _cover_url(self, data: Mapping[str, Any]) -> str | None:
        cover = data.get("coverImage") if isinstance(data.get("coverImage"), Mapping) else {}
        return self._optional_text(cover.get("large")) or self._optional_text(cover.get("medium"))

    def _staff(self, value: Any) -> list[NormalizedCredit]:
        if not isinstance(value, Mapping):
            return []
        edges = value.get("edges")
        if not isinstance(edges, list):
            return []
        credits: list[NormalizedCredit] = []
        for edge in edges:
            if not isinstance(edge, Mapping):
                continue
            node = edge.get("node") if isinstance(edge.get("node"), Mapping) else {}
            name = node.get("name") if isinstance(node.get("name"), Mapping) else {}
            full_name = self._optional_text(name.get("full"))
            if not full_name:
                continue
            credits.append(
                NormalizedCredit(
                    name=full_name,
                    role=self._optional_text(edge.get("role")) or "Staff",
                    site_detail_url=self._optional_text(node.get("siteUrl")),
                )
            )
        return credits

    def _characters(self, value: Any) -> list[NormalizedCredit]:
        if not isinstance(value, Mapping):
            return []
        edges = value.get("edges")
        if not isinstance(edges, list):
            return []
        credits: list[NormalizedCredit] = []
        for edge in edges:
            if not isinstance(edge, Mapping):
                continue
            node = edge.get("node") if isinstance(edge.get("node"), Mapping) else {}
            name = node.get("name") if isinstance(node.get("name"), Mapping) else {}
            full_name = self._optional_text(name.get("full"))
            if not full_name:
                continue
            image = node.get("image") if isinstance(node.get("image"), Mapping) else {}
            image_url = self._optional_text(image.get("large")) or self._optional_text(
                image.get("medium")
            )
            credits.append(
                NormalizedCredit(
                    name=full_name,
                    role=self._optional_text(edge.get("role")) or "Character",
                    site_detail_url=self._optional_text(node.get("siteUrl")),
                    image_url=image_url,
                )
            )
        return credits

    def _character_preview(self, value: Any) -> list[str]:
        characters = self._characters(value)
        return [character.name for character in characters[:3]]

    _ANILIST_RELATION_MAP: dict[str, str] = {
        "SEQUEL": "sequel",
        "PREQUEL": "prequel",
        "SIDE_STORY": "side_story",
        "PARENT": "parent",
        "SPIN_OFF": "spin_off",
        "ADAPTATION": "adaptation",
        "ALTERNATIVE": "alternative",
        "SUMMARY": "summary",
        "COMPILATION": "compilation",
        "CHARACTER": "other",
        "OTHER": "other",
    }

    def _relations(
        self,
        value: Any,
        parent_kind: ItemKind,
    ) -> list[NormalizedRelation]:
        if not isinstance(value, Mapping):
            return []
        edges = value.get("edges")
        if not isinstance(edges, list):
            return []
        relations: list[NormalizedRelation] = []
        for edge in edges:
            if not isinstance(edge, Mapping):
                continue
            relation_type_raw = self._optional_text(edge.get("relationType"))
            if not relation_type_raw:
                continue
            relation_type = self._ANILIST_RELATION_MAP.get(relation_type_raw, "other")
            node = edge.get("node") if isinstance(edge.get("node"), Mapping) else {}
            title = self._title(node)
            if not title:
                continue
            anilist_id = self._id(node.get("id"))
            node_type = str(node.get("type") or "").upper()
            if node_type == "ANIME":
                node_kind = ItemKind.anime
            elif node_type == "MANGA":
                node_kind = ItemKind.manga
            else:
                node_kind = parent_kind
            start_date = (
                node.get("startDate") if isinstance(node.get("startDate"), Mapping) else {}
            )
            start_year = self._int(start_date.get("year")) if start_date else None
            cover = node.get("coverImage") if isinstance(node.get("coverImage"), Mapping) else {}
            image_url = self._optional_text(cover.get("medium"))
            provider_id = (
                self._provider_item_id(node_kind, anilist_id) if anilist_id else None
            )
            relations.append(
                NormalizedRelation(
                    relation_type=relation_type,
                    title=title,
                    provider=self.name,
                    provider_id=provider_id,
                    kind=node_kind,
                    start_year=start_year,
                    image_url=image_url,
                )
            )
        return relations

    def _date(self, value: Any) -> date | None:
        if not isinstance(value, Mapping):
            return None
        year = self._int(value.get("year"))
        if year is None:
            return None
        month = self._int(value.get("month")) or 1
        day = self._int(value.get("day")) or 1
        return date(year, month, day)

    def _description(self, value: Any) -> str | None:
        text = self._optional_text(value)
        if not text:
            return None
        return self._optional_text(_TAG_RE.sub("", unescape(text)).replace("<br>", "\n"))

    def _list_text(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        return [text for item in value if (text := self._optional_text(item))]

    def _id(self, value: Any) -> int | None:
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

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

    def _bundle_release(
        self,
        *,
        data: Mapping[str, Any],
        kind: ItemKind,
        provider_item_id: str | None,
        title: str,
        start_date: date | None,
    ) -> NormalizedBundleRelease | None:
        if kind == ItemKind.anime:
            return self._anime_bundle_release(
                data=data,
                provider_item_id=provider_item_id,
                title=title,
                start_date=start_date,
            )
        if kind != ItemKind.manga:
            return None
        volume_count = self._int(data.get("volumes"))
        if volume_count is None or volume_count < 2:
            return None

        members = [
            NormalizedBundleMember(
                item=NormalizedItem(
                    kind=kind,
                    title=f"{title} Volume {index}",
                    series_title=title,
                    volume_name=f"Volume {index}",
                    volume_number=index,
                    volume_start_year=start_date.year if start_date else None,
                    edition_title=f"Volume {index}",
                    edition_format="Manga Volume",
                    release_date=start_date,
                    cover_image_url=self._cover_url(data),
                    creators=self._staff(data.get("staff")),
                    genres=self._list_text(data.get("genres")),
                    provider_ids=(
                        {self.name: f"{provider_item_id}#volume-{index}"}
                        if provider_item_id
                        else {}
                    ),
                ),
                role="primary" if index == 1 else "component",
                sequence_number=index,
                disc_number=index,
                disc_label=f"Volume {index}",
                is_primary=index == 1,
                metadata={"anilist_volume_number": index},
            )
            for index in range(1, volume_count + 1)
        ]

        return NormalizedBundleRelease(
            title=f"{title} Box Set",
            bundle_type="box_set",
            format="Manga Volume",
            packaging_type="box",
            release_date=start_date,
            cover_image_url=self._cover_url(data),
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            members=members,
        )

    def _anime_bundle_release(
        self,
        *,
        data: Mapping[str, Any],
        provider_item_id: str | None,
        title: str,
        start_date: date | None,
    ) -> NormalizedBundleRelease | None:
        candidates: list[tuple[str | None, str, date | None, str | None, str]] = [
            (provider_item_id, title, start_date, self._cover_url(data), "self")
        ]
        relations = data.get("relations") if isinstance(data.get("relations"), Mapping) else None
        edges = relations.get("edges") if isinstance(relations, Mapping) else None
        if isinstance(edges, list):
            for edge in edges:
                if not isinstance(edge, Mapping):
                    continue
                relation_type = self._optional_text(edge.get("relationType"))
                if relation_type not in {"PREQUEL", "SEQUEL"}:
                    continue
                node = edge.get("node") if isinstance(edge.get("node"), Mapping) else None
                if not isinstance(node, Mapping):
                    continue
                if str(node.get("type") or "").upper() != "ANIME":
                    continue
                node_title = self._title(node)
                node_id = self._id(node.get("id"))
                if not node_title or node_id is None:
                    continue
                candidates.append(
                    (
                        self._provider_item_id(ItemKind.anime, node_id),
                        node_title,
                        self._date(node.get("startDate")),
                        self._cover_url(node),
                        relation_type.lower(),
                    )
                )

        unique_candidates: list[tuple[str | None, str, date | None, str | None, str]] = []
        seen_provider_ids: set[str] = set()
        for candidate in candidates:
            candidate_provider_id = candidate[0]
            if candidate_provider_id and candidate_provider_id in seen_provider_ids:
                continue
            if candidate_provider_id:
                seen_provider_ids.add(candidate_provider_id)
            unique_candidates.append(candidate)

        if len(unique_candidates) < 2:
            return None

        relation_order = {"prequel": 0, "self": 1, "sequel": 2}
        unique_candidates.sort(
            key=lambda candidate: (
                candidate[2] or date.max,
                relation_order.get(candidate[4], 3),
                candidate[1].lower(),
            )
        )

        members = [
            NormalizedBundleMember(
                item=NormalizedItem(
                    kind=ItemKind.anime,
                    title=candidate_title,
                    series_title=title,
                    volume_name=candidate_title,
                    volume_number=index,
                    volume_start_year=candidate_date.year if candidate_date else None,
                    edition_title=candidate_title,
                    edition_format="Anime Season",
                    release_date=candidate_date,
                    cover_image_url=candidate_cover,
                    provider_ids={self.name: candidate_provider_id}
                    if candidate_provider_id
                    else {},
                ),
                role="primary" if candidate_provider_id == provider_item_id else "component",
                sequence_number=index,
                disc_number=index,
                disc_label=candidate_title,
                is_primary=candidate_provider_id == provider_item_id,
                metadata={"anilist_relation_type": candidate_relation_type},
            )
            for index, (
                candidate_provider_id,
                candidate_title,
                candidate_date,
                candidate_cover,
                candidate_relation_type,
            ) in enumerate(unique_candidates, start=1)
        ]

        return NormalizedBundleRelease(
            title=f"{title} Seasons",
            bundle_type="season_pack",
            format="Anime Season",
            packaging_type="digital",
            release_date=members[0].item.release_date,
            cover_image_url=self._cover_url(data),
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            members=members,
        )

    async def get_volumes(self, provider_item_id: str) -> list[NormalizedSeason]:
        """Seed volumes from AniList volume count. No per-chapter data available."""
        kind, anilist_id = self._kind_and_media_id(provider_item_id)
        if anilist_id is None or kind != ItemKind.manga:
            return []
        payload = await self._graphql(
            """
            query ($id: Int) {
              Media(id: $id, type: MANGA) {
                volumes
                chapters
              }
            }
            """,
            {"id": anilist_id},
        )
        media = (payload.get("data") or {}).get("Media")
        if not isinstance(media, Mapping):
            return []
        volume_count = self._int(media.get("volumes"))
        if not volume_count:
            return []
        return [
            NormalizedSeason(
                season_number=i,
                title=f"Volume {i}",
                overview=None,
                air_date=None,
                episode_count=None,
                poster_url=None,
                episodes=[],
            )
            for i in range(1, volume_count + 1)
        ]
