from collections.abc import Mapping
from datetime import date
from typing import Any

from fastapi import status

from app.core.config import get_settings, provider_stub_data_enabled
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
from app.providers.http_base import BaseHttpProvider


class TMDbProvider(BaseHttpProvider):
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
            if not provider_stub_data_enabled():
                return []
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
                "append_to_response": "credits,external_ids,recommendations,release_dates,videos",
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
        external_ids = self._external_ids(data, kind)
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
            age_rating=self._age_rating(data),
            distributor=self._distributor(data),
            subtitle=self._optional_text(data.get("tagline")),
            external_ids=external_ids,
            trailer_urls=self._trailer_urls(data, kind),
            external_links=self._external_links(data, kind, external_ids),
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
        return await self._request_json(
            "tmdb",
            url,
            params=request_params,
            headers=headers,
            timeout=self.settings.tmdb_timeout_seconds,
        )

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

    def _age_rating(self, data: Mapping[str, Any]) -> str | None:
        """Extract age rating (certification) from TMDB release_dates."""
        release_dates = data.get("release_dates")
        if not isinstance(release_dates, list):
            return None
        # Look for US release first, then any release with a certification
        for entry in release_dates:
            if not isinstance(entry, Mapping):
                continue
            if entry.get("iso_3166_1") != "US":
                continue
            cert = self._age_rating_from_release_entry(entry)
            if cert:
                return cert
        # Fallback to first release with certification
        for entry in release_dates:
            if not isinstance(entry, Mapping):
                continue
            cert = self._age_rating_from_release_entry(entry)
            if cert:
                return cert
        return None

    def _age_rating_from_release_entry(self, entry: Mapping[str, Any]) -> str | None:
        cert = self._optional_text(entry.get("certification"))
        if cert:
            return cert
        releases = entry.get("release_dates")
        if not isinstance(releases, list):
            return None
        for release in releases:
            if not isinstance(release, Mapping):
                continue
            cert = self._optional_text(release.get("certification"))
            if cert:
                return cert
        return None

    def _distributor(self, data: Mapping[str, Any]) -> str | None:
        """Extract distributor from TMDB production_companies."""
        companies = data.get("production_companies")
        if not isinstance(companies, list):
            return None
        # Return the first production company (usually the main distributor)
        for company in companies:
            if isinstance(company, Mapping):
                name = self._optional_text(company.get("name"))
                if name:
                    return name
        return None


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

    def _external_ids(self, data: Mapping[str, Any], kind: ItemKind) -> dict[str, str]:
        external_ids = data.get("external_ids")
        if not isinstance(external_ids, Mapping):
            return {}
        result: dict[str, str] = {}
        tmdb_id = self._id(data.get("id"))
        if tmdb_id is not None:
            result["tmdb_id"] = str(tmdb_id)
        imdb_id = self._optional_text(external_ids.get("imdb_id"))
        if imdb_id:
            result["imdb_id"] = imdb_id
        return result

    def _trailer_urls(self, data: Mapping[str, Any], kind: ItemKind) -> list[dict[str, str]]:
        videos = data.get("videos")
        if not isinstance(videos, Mapping):
            return []
        results = videos.get("results")
        if not isinstance(results, list):
            return []
        links: list[dict[str, str]] = []
        for entry in results:
            if not isinstance(entry, Mapping):
                continue
            site = self._optional_text(entry.get("site"))
            video_type = self._optional_text(entry.get("type"))
            key = self._optional_text(entry.get("key"))
            if site != "YouTube" or not key:
                continue
            if video_type and video_type.casefold() not in {"trailer", "teaser"}:
                continue
            name = self._optional_text(entry.get("name")) or "Trailer"
            links.append(
                {
                    "url": f"https://www.youtube.com/watch?v={key}",
                    "site": "YouTube",
                    "kind": (video_type or "trailer").casefold(),
                    "name": name,
                    "description": "TMDb video",
                }
            )
            if len(links) >= 3:
                break
        return links

    def _external_links(
        self,
        data: Mapping[str, Any],
        kind: ItemKind,
        external_ids: dict[str, str],
    ) -> list[dict[str, str]]:
        links: list[dict[str, str]] = []
        tmdb_id = external_ids.get("tmdb_id") or self._optional_text(data.get("id"))
        tmdb_path = "movie" if kind == ItemKind.movie else "tv"
        if tmdb_id:
            links.append(
                {
                    "url": f"https://www.themoviedb.org/{tmdb_path}/{tmdb_id}",
                    "site": "TMDb",
                    "kind": "tmdb",
                    "name": "TMDb page",
                    "description": "TMDb title page",
                }
            )
        imdb_id = external_ids.get("imdb_id")
        if imdb_id:
            links.append(
                {
                    "url": f"https://www.imdb.com/title/{imdb_id}/",
                    "site": "IMDb",
                    "kind": "imdb",
                    "name": "IMDb page",
                    "description": "IMDb title page",
                }
            )
        return links

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
            season_number = self._id(raw.get("season_number"))
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
                ep_num = self._id(ep.get("episode_number"))
                if ep_num is None:
                    continue
                ep_title = self._optional_text(ep.get("name")) or f"Episode {ep_num}"
                episodes.append(
                    NormalizedEpisode(
                        episode_number=ep_num,
                        title=ep_title,
                        provider_item_id=f"tv:{tmdb_id}:season:{season_number}:episode:{ep_num}",
                        overview=self._optional_text(ep.get("overview")),
                        air_date=self._date(ep.get("air_date")),
                        runtime_minutes=self._id(ep.get("runtime")),
                        still_url=self._image_url(ep.get("still_path")),
                    )
                )
            seasons.append(
                NormalizedSeason(
                    season_number=season_number,
                    title=self._optional_text(raw.get("name")) or f"Season {season_number}",
                    provider_item_id=f"tv:{tmdb_id}:season:{season_number}",
                    overview=self._optional_text(raw.get("overview")),
                    air_date=self._date(raw.get("air_date")),
                    episode_count=self._id(raw.get("episode_count")),
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
