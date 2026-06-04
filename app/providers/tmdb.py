from datetime import date
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
    NormalizedEpisode,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


class TMDbProvider:
    name = "tmdb"
    capabilities = ProviderCapabilities(
        kind=ItemKind.movie,
        kinds=(ItemKind.movie, ItemKind.tv, ItemKind.anime, ItemKind.collection),
        display_name="TMDb",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=True,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="TMDb API Terms",
        terms_url="https://www.themoviedb.org/documentation/api/terms-of-use",
        attribution_url="https://www.themoviedb.org/",
        cache_policy=(
            "Use TMDb as movie/TV metadata source with attribution. Store provider "
            "IDs and public poster URLs; keep physical video releases as editions/variants."
        ),
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return bool(self._access_token() or self._api_key())

    @property
    def status_message(self) -> str:
        return (
            "TMDb credentials configured."
            if self.is_configured
            else "Set TMDB_API_READ_ACCESS_TOKEN or TMDB_API_KEY."
        )

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []

        target_kind = self._target_kind(kind)
        if not self.is_configured:
            return [
                ProviderSearchResult(
                    provider=self.name,
                    provider_item_id=f"stub-{target_kind.value}-{self._slug(normalized_query)}",
                    title=f"{normalized_query} (TMDb stub)",
                    kind=target_kind,
                    summary="Set TMDb credentials to enable live movie/TV/anime metadata.",
                )
            ]

        payload = await self._request(
            f"search/{self._tmdb_type(target_kind)}",
            {
                "query": normalized_query,
                "include_adult": "false",
                "language": self.settings.tmdb_language,
                "page": 1,
            },
        )
        results = payload.get("results") if isinstance(payload.get("results"), list) else []
        return [
            self._search_result(result, target_kind)
            for result in results[: self.settings.tmdb_search_limit]
            if isinstance(result, Mapping)
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        api_kind, tmdb_id = self._provider_id(provider_item_id)
        if tmdb_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="tmdb_invalid_id",
                detail="Invalid TMDb id",
            )
        payload = await self._request(
            f"{self._tmdb_type(api_kind)}/{tmdb_id}",
            {
                "append_to_response": "credits,external_ids,recommendations",
                "language": self.settings.tmdb_language,
            },
        )
        input_text = str(provider_item_id or "").strip()
        raw_prefix = input_text.split(":")[0].lower() if ":" in input_text else api_kind.value
        payload["media_type"] = raw_prefix
        canonical_kind = self._kind_from_raw(payload)
        return ProviderItem(
            provider=self.name,
            provider_item_id=self._provider_item_id(canonical_kind, tmdb_id),
            raw=payload,
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        kind = self._kind_from_raw(data)
        tmdb_id = self._id(data.get("id"))
        provider_item_id = self._provider_item_id(kind, tmdb_id) if tmdb_id else ""
        raw_media_type = str(data.get("media_type") or kind.value).strip().lower()
        provenance_id = f"{raw_media_type}:{tmdb_id}" if tmdb_id else ""
        release_date = self._date(
            data.get("release_date") if kind == ItemKind.movie and raw_media_type not in {"anime", "tv"} else data.get("first_air_date")
        )
        title = self._title(data, kind)
        runtime_minutes = self._runtime(data, kind)
        publisher = self._first_company(data.get("production_companies"))
        creators = self._creators(data, kind)
        genres = self._names(data.get("genres"))
        bundle_release = self._bundle_release(
            data=data,
            kind=kind,
            provider_item_id=provider_item_id or None,
            title=title,
            publisher=publisher,
        )

        return NormalizedItem(
            kind=kind,
            title=title,
            synopsis=self._optional_text(data.get("overview")),
            series_title=title,
            volume_name=title,
            volume_start_year=release_date.year if release_date else None,
            runtime_minutes=runtime_minutes,
            edition_title=title,
            edition_format=self._edition_format(kind),
            publisher=publisher,
            release_date=release_date,
            cover_image_url=self._poster_url(data),
            creators=creators,
            characters=self._cast(data.get("credits")),
            genres=genres,
            language=self._optional_text(data.get("original_language")),
            audience_rating=self._audience_rating(data.get("vote_average")),
            subtitle=self._optional_text(data.get("tagline")),
            provider_ids={self.name: provenance_id} if provenance_id else {},
            volume_provider_ids={self.name: provider_item_id} if provider_item_id else {},
            relations=self._relations(data, kind),
            bundle_release=bundle_release,
        )

    async def _request(
        self,
        path: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        token = self._access_token()
        api_key = self._api_key()
        if not token and not api_key:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="tmdb_not_configured",
                detail="TMDb credentials are not configured",
            )
        url = f"{self.settings.tmdb_base_url.rstrip('/')}/{path.lstrip('/')}"
        request_params = dict(params or {})
        if api_key and not token:
            request_params["api_key"] = api_key
        headers = {
            "User-Agent": self.settings.tmdb_user_agent,
            "Accept": "application/json",
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.tmdb_timeout_seconds,
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=request_params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == status.HTTP_404_NOT_FOUND:
                raise ApiHTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    code="tmdb_item_not_found",
                    detail="TMDb item not found",
                ) from exc
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="tmdb_http_error",
                detail=f"TMDb returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="tmdb_request_failed",
                detail="TMDb request failed",
            ) from exc
        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="tmdb_invalid_response",
                detail="Invalid TMDb response",
            )
        return payload

    def _search_result(self, data: Mapping[str, Any], kind: ItemKind) -> ProviderSearchResult:
        tmdb_id = self._id(data.get("id"))
        if kind == ItemKind.collection:
            release_date = None
        else:
            release_date = self._date(
                data.get("release_date") if kind == ItemKind.movie else data.get("first_air_date")
            )
        summary_parts = [
            release_date.isoformat() if release_date else None,
            self._optional_text(data.get("original_language")) if kind != ItemKind.collection else None,
        ]
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=self._provider_item_id(kind, tmdb_id) if tmdb_id else "",
            title=self._title(data, kind),
            kind=kind,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._poster_url(data),
        )

    def _provider_id(self, value: Any) -> tuple[ItemKind, int | None]:
        text = str(value or "").strip()
        if not text:
            return ItemKind.movie, None
        normalized = text.lower()
        # Handle "anime:" prefix by routing to the TV endpoint with anime item kind.
        for prefix_str in ("anime:", "anime-"):
            if normalized.startswith(prefix_str):
                return ItemKind.anime, self._id(text[len(prefix_str):])
        for kind in self.capabilities.supported_kinds:
            prefix = f"{kind.value}:"
            dash_prefix = f"{kind.value}-"
            if normalized.startswith(prefix):
                return kind, self._id(text[len(prefix) :])
            if normalized.startswith(dash_prefix):
                return kind, self._id(text[len(dash_prefix) :])
        return ItemKind.movie, self._id(text)

    def _provider_item_id(self, kind: ItemKind, tmdb_id: int) -> str:
        return f"{kind.value}:{tmdb_id}"

    def _tmdb_type(self, kind: ItemKind) -> str:
        if kind == ItemKind.collection:
            return "collection"
        return "tv" if kind in {ItemKind.tv, ItemKind.anime} else "movie"

    def _kind_from_raw(self, data: Mapping[str, Any]) -> ItemKind:
        media_type = str(data.get("media_type") or "").strip().lower()
        if media_type == ItemKind.tv.value:
            return ItemKind.tv
        if media_type == "anime":
            return ItemKind.anime
        return ItemKind.movie

    def _target_kind(self, kind: ItemKind | None) -> ItemKind:
        return kind if kind in self.capabilities.supported_kinds else ItemKind.movie

    def _title(self, data: Mapping[str, Any], kind: ItemKind) -> str:
        raw_media_type = str(data.get("media_type") or "").strip().lower()
        use_title = kind == ItemKind.movie and raw_media_type not in {"anime", "tv"}
        return (
            self._optional_text(data.get("title" if use_title else "name"))
            or self._optional_text(
                data.get("original_title" if use_title else "original_name")
            )
            or "Unknown TMDb title"
        )

    def _poster_url(self, data: Mapping[str, Any]) -> str | None:
        poster_path = self._optional_text(data.get("poster_path"))
        if not poster_path:
            return None
        return f"{self.settings.tmdb_image_base_url.rstrip('/')}/w500/{poster_path.lstrip('/')}"

    def _audience_rating(self, value: Any) -> str | None:
        if value is None:
            return None
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        if numeric <= 0:
            return None
        return f"{numeric:.1f}".rstrip("0").rstrip(".")

    def _runtime(self, data: Mapping[str, Any], kind: ItemKind) -> int | None:
        raw_media_type = str(data.get("media_type") or "").strip().lower()
        if kind == ItemKind.movie and raw_media_type not in {"anime", "tv"}:
            return self._id(data.get("runtime"))
        runtimes = data.get("episode_run_time")
        if not isinstance(runtimes, list) or not runtimes:
            return self._id(data.get("runtime"))
        return self._id(runtimes[0])

    def _edition_format(self, kind: ItemKind) -> str:
        if kind == ItemKind.movie:
            return "Movie"
        if kind == ItemKind.anime:
            return "Anime Series"
        return "TV Series"

    def _creators(self, data: Mapping[str, Any], kind: ItemKind) -> list[NormalizedCredit]:
        raw_media_type = str(data.get("media_type") or "").strip().lower()
        if kind == ItemKind.tv or raw_media_type in {"anime", "tv"}:
            return [
                NormalizedCredit(name=name, role="Creator")
                for name in self._names(data.get("created_by"))
            ]
        credits = data.get("credits") if isinstance(data.get("credits"), Mapping) else {}
        crew = credits.get("crew") if isinstance(credits.get("crew"), list) else []
        creators: list[NormalizedCredit] = []
        for entry in crew:
            if not isinstance(entry, Mapping):
                continue
            job = self._optional_text(entry.get("job"))
            if job not in {"Director", "Writer", "Screenplay"}:
                continue
            name = self._optional_text(entry.get("name"))
            if name:
                creators.append(NormalizedCredit(name=name, role=job))
        return creators

    def _cast(self, credits: Any) -> list[NormalizedCredit]:
        if not isinstance(credits, Mapping):
            return []
        cast = credits.get("cast") if isinstance(credits.get("cast"), list) else []
        characters: list[NormalizedCredit] = []
        for entry in cast[:10]:
            if not isinstance(entry, Mapping):
                continue
            name = self._optional_text(entry.get("name"))
            if name:
                characters.append(
                    NormalizedCredit(
                        name=name,
                        role=self._optional_text(entry.get("character")),
                    )
                )
        return characters

    def _relations(self, data: Mapping[str, Any], kind: ItemKind) -> list[NormalizedRelation]:
        relations: list[NormalizedRelation] = []
        collection = data.get("belongs_to_collection")
        if isinstance(collection, Mapping):
            name = self._optional_text(collection.get("name"))
            if name:
                poster = self._optional_text(collection.get("poster_path"))
                relations.append(
                    NormalizedRelation(
                        relation_type="compilation",
                        title=name,
                        provider=self.name,
                        provider_id=None,
                        kind=kind,
                        start_year=None,
                        image_url=(
                            f"{self.settings.tmdb_image_base_url.rstrip('/')}/w500/{poster.lstrip('/')}"
                            if poster
                            else None
                        ),
                    )
                )
        recommendations = data.get("recommendations")
        if isinstance(recommendations, Mapping):
            results = recommendations.get("results")
            if isinstance(results, list):
                for entry in results[:5]:
                    if not isinstance(entry, Mapping):
                        continue
                    title = self._title(entry, kind)
                    tmdb_id = self._id(entry.get("id"))
                    release_date = self._date(
                        entry.get("release_date")
                        if kind == ItemKind.movie
                        else entry.get("first_air_date")
                    )
                    relations.append(
                        NormalizedRelation(
                            relation_type="other",
                            title=title,
                            provider=self.name,
                            provider_id=(
                                self._provider_item_id(kind, tmdb_id) if tmdb_id else None
                            ),
                            kind=kind,
                            start_year=release_date.year if release_date else None,
                            image_url=self._poster_url(entry),
                        )
                    )
        return relations

    def _bundle_release(
        self,
        *,
        data: Mapping[str, Any],
        kind: ItemKind,
        provider_item_id: str | None,
        title: str,
        publisher: str | None,
    ) -> NormalizedBundleRelease | None:
        if kind != ItemKind.tv:
            return None
        raw_seasons = data.get("seasons")
        if not isinstance(raw_seasons, list):
            return None

        members: list[NormalizedBundleMember] = []
        for raw_season in raw_seasons:
            if not isinstance(raw_season, Mapping):
                continue
            season_number = self._id(raw_season.get("season_number"))
            if season_number is None or season_number <= 0:
                continue
            season_title = self._optional_text(raw_season.get("name")) or f"Season {season_number}"
            season_release_date = self._date(raw_season.get("air_date"))
            season_provider_id = (
                f"{provider_item_id}#season-{season_number}" if provider_item_id else None
            )
            member_item = NormalizedItem(
                kind=kind,
                title=season_title,
                synopsis=self._optional_text(raw_season.get("overview")),
                series_title=title,
                volume_name=season_title,
                volume_number=season_number,
                volume_start_year=season_release_date.year if season_release_date else None,
                edition_title=season_title,
                edition_format="TV Season",
                publisher=publisher,
                release_date=season_release_date,
                cover_image_url=self._image_url(raw_season.get("poster_path")),
                provider_ids={self.name: season_provider_id} if season_provider_id else {},
            )
            members.append(
                NormalizedBundleMember(
                    item=member_item,
                    role="primary" if not members else "component",
                    sequence_number=len(members) + 1,
                    disc_number=season_number,
                    disc_label=season_title,
                    is_primary=not members,
                    metadata={
                        "tmdb_season_number": season_number,
                        "tmdb_episode_count": self._id(raw_season.get("episode_count")),
                    },
                )
            )

        if len(members) < 2:
            return None

        return NormalizedBundleRelease(
            title=title,
            bundle_type="season_pack",
            format="TV Season",
            packaging_type="digital",
            language=self._optional_text(data.get("original_language")),
            publisher=publisher,
            release_date=self._date(data.get("first_air_date")),
            cover_image_url=self._poster_url(data),
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            members=members,
        )

    def _first_company(self, value: Any) -> str | None:
        names = self._names(value)
        return names[0] if names else None

    def _names(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        names: list[str] = []
        for entry in value:
            if isinstance(entry, Mapping):
                name = self._optional_text(entry.get("name"))
                if name:
                    names.append(name)
        return names

    def _date(self, value: Any) -> date | None:
        text = self._optional_text(value)
        if not text:
            return None
        try:
            return date.fromisoformat(text[:10])
        except ValueError:
            return None

    def _id(self, value: Any) -> int | None:
        text = str(value or "").strip()
        if ":" in text:
            text = text.rsplit(":", 1)[-1]
        elif "-" in text:
            prefix, suffix = text.split("-", 1)
            if prefix.lower() in {"movie", "tv", "anime"}:
                text = suffix
        try:
            number = int(text)
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def _access_token(self) -> str | None:
        return self._optional_text(self.settings.tmdb_api_read_access_token)

    def _api_key(self) -> str | None:
        return self._optional_text(self.settings.tmdb_api_key)

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _slug(self, value: str) -> str:
        return "-".join(
            "".join(char.lower() if char.isalnum() else " " for char in value).split()
        )

    async def get_seasons(self, provider_item_id: str) -> list[NormalizedSeason]:
        kind, tmdb_id = self._provider_id(provider_item_id)
        if tmdb_id is None or kind != ItemKind.tv:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="tmdb_invalid_id",
                detail="Invalid TMDb id or unsupported kind for seasons",
            )
        show = await self._request(
            f"tv/{tmdb_id}",
            {"language": "en-US"},
        )
        raw_seasons = show.get("seasons") or []
        if not isinstance(raw_seasons, list):
            return []

        seasons: list[NormalizedSeason] = []
        for raw in raw_seasons:
            if not isinstance(raw, Mapping):
                continue
            season_number = raw.get("season_number")
            if season_number is None:
                continue
            season_detail = await self._request(
                f"tv/{tmdb_id}/season/{season_number}",
                {"language": "en-US"},
            )
            episodes: list[NormalizedEpisode] = []
            for ep in season_detail.get("episodes") or []:
                if not isinstance(ep, Mapping):
                    continue
                ep_num = ep.get("episode_number")
                ep_title = self._optional_text(ep.get("name")) or f"Episode {ep_num}"
                episodes.append(
                    NormalizedEpisode(
                        episode_number=ep_num,
                        title=ep_title,
                        overview=self._optional_text(ep.get("overview")),
                        air_date=self._date(ep.get("air_date")),
                        runtime_minutes=ep.get("runtime"),
                        still_url=self._image_url(ep.get("still_path")),
                    )
                )
            seasons.append(
                NormalizedSeason(
                    season_number=season_number,
                    title=self._optional_text(raw.get("name")) or f"Season {season_number}",
                    overview=self._optional_text(raw.get("overview")),
                    air_date=self._date(raw.get("air_date")),
                    episode_count=raw.get("episode_count"),
                    poster_url=self._image_url(raw.get("poster_path")),
                    episodes=episodes,
                )
            )
        return seasons

    def _image_url(self, path: Any) -> str | None:
        text = self._optional_text(path)
        if not text:
            return None
        return f"{self.settings.tmdb_image_base_url.rstrip('/')}/w500/{text.lstrip('/')}"
