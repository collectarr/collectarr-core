import re
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
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


_MBID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


class MusicBrainzProvider:
    name = "musicbrainz"
    capabilities = ProviderCapabilities(
        kind=ItemKind.music,
        display_name="MusicBrainz",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=False,
        non_commercial_only=False,
        allows_redistribution=True,
        requires_attribution=True,
        license_name="MusicBrainz Data Licenses",
        terms_url="https://musicbrainz.org/doc/MusicBrainz_Database",
        attribution_url="https://musicbrainz.org/",
        rate_limit="Public web service; identify the app with User-Agent and keep request volume low.",
        cache_policy="Cache MusicBrainz metadata with attribution; cover art references use Cover Art Archive URLs.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def is_configured(self) -> bool:
        return True

    @property
    def status_message(self) -> str:
        return "MusicBrainz release metadata is available without an API key."

    async def search(
        self,
        query: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        payload = await self._request(
            "release",
            {
                "query": normalized_query,
                "fmt": "json",
                "limit": self.settings.musicbrainz_search_limit,
            },
        )
        releases = payload.get("releases") or []
        if not isinstance(releases, list):
            return []
        return [self._search_result(release) for release in releases if isinstance(release, Mapping)]

    async def search_by_barcode(
        self,
        barcode: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        normalized = barcode.strip()
        if not normalized:
            return []
        return await self.search(f"barcode:{normalized}", kind)

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        if not _MBID_RE.fullmatch(provider_item_id):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="musicbrainz_invalid_release_id",
                detail="Invalid MusicBrainz release id",
            )
        raw = await self._request(
            f"release/{provider_item_id}",
            {
                "fmt": "json",
                "inc": "artist-credits+labels+release-groups+media",
            },
        )
        return ProviderItem(provider=self.name, provider_item_id=provider_item_id, raw=raw)

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        provider_item_id = self._optional_text(data.get("id"))
        title = self._optional_text(data.get("title")) or "Unknown release"
        release_group = data.get("release-group") if isinstance(data.get("release-group"), Mapping) else {}
        release_date = self._date(data.get("date"))
        artist_names = self._artist_names(data.get("artist-credit"))
        track_count, medium_formats = self._media_details(data.get("media"))
        catalog_number = self._catalog_number(data)

        return NormalizedItem(
            kind=ItemKind.music,
            title=title,
            synopsis=self._optional_text(data.get("disambiguation")),
            series_title=", ".join(artist_names) if artist_names else None,
            volume_name=title,
            volume_start_year=release_date.year if release_date else None,
            edition_title=title,
            edition_format=self._edition_format(data, release_group),
            physical_format=medium_formats[0] if medium_formats else None,
            publisher=self._publisher(data),
            release_date=release_date,
            barcode=self._optional_text(data.get("barcode")),
            cover_image_url=self._cover_url(data),
            creators=[NormalizedCredit(name=name, role="Artist") for name in artist_names],
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            volume_provider_ids=(
                {self.name: str(release_group.get("id"))} if release_group.get("id") else {}
            ),
            track_count=track_count,
            catalog_number=catalog_number,
            country=self._optional_text(data.get("country")),
            release_status=self._optional_text(data.get("status")),
        )

    async def _request(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        url = f"{self.settings.musicbrainz_base_url.rstrip('/')}/{path.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.musicbrainz_timeout_seconds,
                headers={
                    "User-Agent": self.settings.musicbrainz_user_agent,
                    "Accept": "application/json",
                },
                follow_redirects=True,
            ) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="musicbrainz_http_error",
                detail=f"MusicBrainz returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="musicbrainz_request_failed",
                detail="MusicBrainz request failed",
            ) from exc
        if not isinstance(payload, dict):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="musicbrainz_invalid_response",
                detail="Invalid MusicBrainz response",
            )
        return payload

    def _search_result(self, release: Mapping[str, Any]) -> ProviderSearchResult:
        artist_names = self._artist_names(release.get("artist-credit"))
        summary_parts = [
            ", ".join(artist_names) if artist_names else None,
            self._optional_text(release.get("date")),
            self._optional_text(release.get("country")),
        ]
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=str(release.get("id") or ""),
            title=self._optional_text(release.get("title")) or "Unknown MusicBrainz release",
            kind=ItemKind.music,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._cover_url(release),
        )

    def _artist_names(self, value: Any) -> list[str]:
        if not isinstance(value, list):
            return []
        names: list[str] = []
        for credit in value:
            if not isinstance(credit, Mapping):
                continue
            artist = credit.get("artist") if isinstance(credit.get("artist"), Mapping) else {}
            name = self._optional_text(artist.get("name")) or self._optional_text(credit.get("name"))
            if name:
                names.append(name)
        return names

    def _publisher(self, data: Mapping[str, Any]) -> str | None:
        labels = data.get("label-info")
        if not isinstance(labels, list):
            return None
        for entry in labels:
            if not isinstance(entry, Mapping):
                continue
            label = entry.get("label") if isinstance(entry.get("label"), Mapping) else {}
            name = self._optional_text(label.get("name"))
            if name:
                return name
        return None

    def _edition_format(self, data: Mapping[str, Any], release_group: Mapping[str, Any]) -> str:
        primary_type = self._optional_text(release_group.get("primary-type"))
        media = data.get("media")
        if isinstance(media, list) and media:
            first = media[0]
            if isinstance(first, Mapping):
                medium_format = self._optional_text(first.get("format"))
                if primary_type and medium_format:
                    return f"{primary_type} / {medium_format}"
                if medium_format:
                    return medium_format
        return primary_type or "Music Release"

    def _media_details(self, media: Any) -> tuple[int | None, list[str]]:
        """Return (total_track_count, list_of_distinct_medium_formats)."""
        if not isinstance(media, list) or not media:
            return None, []
        total_tracks = 0
        formats: list[str] = []
        for medium in media:
            if not isinstance(medium, Mapping):
                continue
            count = medium.get("track-count")
            if isinstance(count, int) and count > 0:
                total_tracks += count
            fmt = self._optional_text(medium.get("format"))
            if fmt and fmt not in formats:
                formats.append(fmt)
        return total_tracks or None, formats

    def _catalog_number(self, data: Mapping[str, Any]) -> str | None:
        labels = data.get("label-info")
        if not isinstance(labels, list):
            return None
        for entry in labels:
            if not isinstance(entry, Mapping):
                continue
            cat = self._optional_text(entry.get("catalog-number"))
            if cat:
                return cat
        return None

    def _cover_url(self, data: Mapping[str, Any]) -> str | None:
        archive = data.get("cover-art-archive")
        if not isinstance(archive, Mapping) or archive.get("front") is not True:
            return None
        release_id = self._optional_text(data.get("id"))
        if not release_id:
            return None
        return f"{self.settings.cover_art_archive_base_url.rstrip('/')}/release/{release_id}/front-500"

    def _date(self, value: Any) -> date | None:
        text = self._optional_text(value)
        if not text:
            return None
        parts = text.split("-")
        try:
            year = int(parts[0])
            month = int(parts[1]) if len(parts) > 1 else 1
            day = int(parts[2]) if len(parts) > 2 else 1
        except ValueError:
            return None
        return date(year, month, day)

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None
