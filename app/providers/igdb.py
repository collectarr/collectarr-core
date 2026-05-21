from datetime import UTC, date, datetime, timedelta
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


class IGDBProvider:
    name = "igdb"
    capabilities = ProviderCapabilities(
        kind=ItemKind.game,
        display_name="IGDB",
        supports_search=True,
        supports_ingest=True,
        requires_user_key=True,
        non_commercial_only=True,
        allows_redistribution=False,
        requires_attribution=True,
        license_name="IGDB API Terms",
        terms_url="https://api-docs.igdb.com/",
        attribution_url="https://www.igdb.com/",
        rate_limit="4 requests per second and up to 8 open requests.",
        cache_policy="Cache per instance; respect IGDB/Twitch non-commercial API terms.",
    )

    def __init__(self) -> None:
        self.settings = get_settings()
        self._token: str | None = None
        self._token_expires_at: datetime | None = None

    @property
    def is_configured(self) -> bool:
        has_direct_token = bool(self.settings.igdb_client_id and self.settings.igdb_access_token)
        has_client_credentials = bool(
            self.settings.igdb_client_id and self.settings.igdb_client_secret
        )
        return has_direct_token or has_client_credentials

    @property
    def status_message(self) -> str:
        return (
            "IGDB credentials configured."
            if self.is_configured
            else "Set IGDB_CLIENT_ID plus IGDB_ACCESS_TOKEN or IGDB_CLIENT_SECRET."
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
            return [
                ProviderSearchResult(
                    provider=self.name,
                    provider_item_id=f"stub-game-{self._slug(normalized_query)}",
                    title=f"{normalized_query} (IGDB stub)",
                    kind=ItemKind.game,
                    summary="Set IGDB credentials to enable live game metadata.",
                )
            ]

        games = await self._request(
            "games",
            "\n".join(
                [
                    f'search "{self._escape_query(normalized_query)}";',
                    "fields id,name,summary,first_release_date,cover.url,genres.name,"
                    "involved_companies.company.name,involved_companies.developer,"
                    "involved_companies.publisher,platforms.name;",
                    "where version_parent = null;",
                    f"limit {self.settings.igdb_search_limit};",
                ]
            ),
        )
        return [self._search_result(game) for game in games if isinstance(game, Mapping)]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        igdb_id = self._id(provider_item_id)
        if igdb_id is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="igdb_invalid_game_id",
                detail="Invalid IGDB game id",
            )
        games = await self._request(
            "games",
            "\n".join(
                [
                    "fields id,name,summary,storyline,first_release_date,cover.url,genres.name,"
                    "involved_companies.company.name,involved_companies.developer,"
                    "involved_companies.publisher,platforms.name,"
                    "game_modes.name,age_ratings.rating,age_ratings.category;",
                    f"where id = {igdb_id};",
                    "limit 1;",
                ]
            ),
        )
        game = games[0] if games and isinstance(games[0], Mapping) else None
        if game is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="igdb_game_not_found",
                detail="IGDB game not found",
            )
        return ProviderItem(provider=self.name, provider_item_id=str(igdb_id), raw=game)

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        provider_item_id = str(data.get("id") or "")
        title = self._optional_text(data.get("name")) or "Unknown game"
        release_date = self._date(data.get("first_release_date"))
        platforms = self._names(data.get("platforms"))
        genres = self._names(data.get("genres"))
        companies = data.get("involved_companies") if isinstance(data.get("involved_companies"), list) else []
        publishers = self._companies(companies, "publisher")
        developers = self._companies(companies, "developer")

        return NormalizedItem(
            kind=ItemKind.game,
            title=title,
            synopsis=self._optional_text(data.get("summary"))
            or self._optional_text(data.get("storyline")),
            series_title=None,
            volume_name=title,
            volume_start_year=release_date.year if release_date else None,
            edition_title=title,
            edition_format=platforms[0] if platforms else "Game",
            publisher=publishers[0] if publishers else None,
            release_date=release_date,
            cover_image_url=self._cover_url(data),
            creators=[NormalizedCredit(name=name, role="Developer") for name in developers],
            genres=genres,
            age_rating=self._age_rating(data.get("age_ratings")),
            provider_ids={self.name: provider_item_id} if provider_item_id else {},
            volume_provider_ids={self.name: provider_item_id} if provider_item_id else {},
            platforms=platforms,
        )

    async def _request(self, endpoint: str, body: str) -> list[dict[str, Any]]:
        client_id = self.settings.igdb_client_id
        token = await self._access_token()
        if not client_id or not token:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="igdb_not_configured",
                detail="IGDB credentials are not configured",
            )
        url = f"{self.settings.igdb_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        try:
            async with httpx.AsyncClient(
                timeout=self.settings.igdb_timeout_seconds,
                headers={
                    "User-Agent": self.settings.igdb_user_agent,
                    "Client-ID": client_id,
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/json",
                },
                follow_redirects=True,
            ) as client:
                response = await client.post(url, content=body)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="igdb_http_error",
                detail=f"IGDB returned HTTP {exc.response.status_code}",
            ) from exc
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="igdb_request_failed",
                detail="IGDB request failed",
            ) from exc
        if not isinstance(payload, list):
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="igdb_invalid_response",
                detail="Invalid IGDB response",
            )
        return [item for item in payload if isinstance(item, dict)]

    async def _access_token(self) -> str | None:
        if self.settings.igdb_access_token:
            return self.settings.igdb_access_token.strip()
        if self._token and self._token_expires_at and self._token_expires_at > datetime.now(UTC):
            return self._token
        if not self.settings.igdb_client_id or not self.settings.igdb_client_secret:
            return None
        try:
            async with httpx.AsyncClient(timeout=self.settings.igdb_timeout_seconds) as client:
                response = await client.post(
                    self.settings.igdb_token_url,
                    params={
                        "client_id": self.settings.igdb_client_id,
                        "client_secret": self.settings.igdb_client_secret,
                        "grant_type": "client_credentials",
                    },
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="igdb_token_failed",
                detail="IGDB token request failed",
            ) from exc
        token = self._optional_text(payload.get("access_token")) if isinstance(payload, dict) else None
        expires_in = self._id(payload.get("expires_in")) if isinstance(payload, dict) else None
        if not token:
            raise ApiHTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                code="igdb_token_invalid",
                detail="Invalid IGDB token response",
            )
        self._token = token
        self._token_expires_at = datetime.now(UTC) + timedelta(seconds=max(60, expires_in or 3600))
        return token

    def _search_result(self, game: Mapping[str, Any]) -> ProviderSearchResult:
        release_date = self._date(game.get("first_release_date"))
        summary_parts = [
            release_date.isoformat() if release_date else None,
            ", ".join(self._names(game.get("platforms"))[:2]),
        ]
        return ProviderSearchResult(
            provider=self.name,
            provider_item_id=str(game.get("id") or ""),
            title=self._optional_text(game.get("name")) or "Unknown IGDB game",
            kind=ItemKind.game,
            summary=" · ".join(part for part in summary_parts if part),
            image_url=self._cover_url(game),
        )

    def _companies(self, value: list[Any], role: str) -> list[str]:
        names: list[str] = []
        for entry in value:
            if not isinstance(entry, Mapping) or entry.get(role) is not True:
                continue
            company = entry.get("company") if isinstance(entry.get("company"), Mapping) else {}
            name = self._optional_text(company.get("name"))
            if name:
                names.append(name)
        return names

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

    def _cover_url(self, game: Mapping[str, Any]) -> str | None:
        cover = game.get("cover") if isinstance(game.get("cover"), Mapping) else {}
        url = self._optional_text(cover.get("url"))
        if not url:
            return None
        if url.startswith("//"):
            url = f"https:{url}"
        return url.replace("/t_thumb/", "/t_cover_big/")

    # IGDB age-rating category 1 = ESRB, 2 = PEGI
    _ESRB_LABELS: dict[int, str] = {
        6: "RP",
        7: "EC",
        8: "E",
        9: "E10+",
        10: "T",
        11: "M",
        12: "AO",
    }

    def _age_rating(self, ratings: Any) -> str | None:
        if not isinstance(ratings, list):
            return None
        for entry in ratings:
            if isinstance(entry, Mapping) and entry.get("category") == 1:
                label = self._ESRB_LABELS.get(entry.get("rating", 0))
                if label:
                    return f"ESRB {label}"
        for entry in ratings:
            if isinstance(entry, Mapping) and entry.get("category") == 2:
                rating = entry.get("rating")
                if rating:
                    return f"PEGI {rating}"
        return None

    def _date(self, value: Any) -> date | None:
        timestamp = self._id(value)
        if timestamp is None:
            return None
        return datetime.fromtimestamp(timestamp, tz=UTC).date()

    def _id(self, value: Any) -> int | None:
        try:
            number = int(str(value).strip())
        except (TypeError, ValueError):
            return None
        return number if number > 0 else None

    def _escape_query(self, value: str) -> str:
        return value.replace("\\", "\\\\").replace('"', '\\"')

    def _optional_text(self, value: Any) -> str | None:
        if value is None:
            return None
        text = str(value).strip()
        return text or None

    def _slug(self, value: str) -> str:
        return "-".join(
            "".join(char.lower() if char.isalnum() else " " for char in value).split()
        )
