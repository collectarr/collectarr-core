from typing import Any, Mapping

from app.models.base import ExternalProvider, ItemKind
from app.providers.base import (
    NormalizedItem,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)


class PlannedProvider:
    def __init__(
        self,
        provider: ExternalProvider,
        kind: ItemKind,
        display_name: str,
        *,
        requires_user_key: bool = False,
        requires_attribution: bool = True,
        allows_redistribution: bool = False,
        license_name: str | None = None,
        terms_url: str | None = None,
        attribution_url: str | None = None,
        cache_policy: str | None = None,
    ) -> None:
        self.provider = provider
        self.name = provider.value
        self.capabilities = ProviderCapabilities(
            kind=kind,
            display_name=display_name,
            supports_search=True,
            supports_ingest=False,
            requires_user_key=requires_user_key,
            requires_attribution=requires_attribution,
            allows_redistribution=allows_redistribution,
            license_name=license_name,
            terms_url=terms_url,
            attribution_url=attribution_url,
            cache_policy=cache_policy
            or f"Planned {display_name} provider; do not ingest into the catalog yet.",
        )

    @property
    def is_configured(self) -> bool:
        return False

    @property
    def status_message(self) -> str:
        return (
            f"{self.capabilities.display_name} search is scaffolded; "
            "catalog ingest is not implemented yet."
        )

    async def search(self, query: str) -> list[ProviderSearchResult]:
        normalized_query = " ".join(query.split())
        if not normalized_query:
            return []
        return [
            ProviderSearchResult(
                provider=self.name,
                provider_item_id=(
                    f"stub-{self.capabilities.kind.value}-{self._slug(normalized_query)}"
                ),
                title=f"{normalized_query} ({self.capabilities.display_name} stub)",
                kind=self.capabilities.kind,
                summary=(
                    f"{self.capabilities.display_name} live normalization is planned; "
                    "this result is search-only."
                ),
            )
        ]

    async def get_item(self, provider_item_id: str) -> ProviderItem:
        raise NotImplementedError(
            f"{self.capabilities.display_name} catalog ingest is not implemented"
        )

    async def normalize(self, data: Mapping[str, Any]) -> NormalizedItem:
        raise NotImplementedError(
            f"{self.capabilities.display_name} catalog ingest is not implemented"
        )

    def _slug(self, value: str) -> str:
        return "-".join(
            "".join(char.lower() if char.isalnum() else " " for char in value).split()
        )


class AniListProvider(PlannedProvider):
    def __init__(self) -> None:
        super().__init__(
            ExternalProvider.anilist,
            ItemKind.manga,
            "AniList",
            requires_user_key=True,
            license_name="AniList API Terms",
            terms_url="https://docs.anilist.co/",
            attribution_url="https://anilist.co/",
        )


class OpenLibraryProvider(PlannedProvider):
    def __init__(self) -> None:
        super().__init__(
            ExternalProvider.openlibrary,
            ItemKind.book,
            "Open Library",
            requires_user_key=False,
            allows_redistribution=True,
            license_name="Open Library Data",
            terms_url="https://openlibrary.org/developers",
            attribution_url="https://openlibrary.org/",
        )


class BGGProvider(PlannedProvider):
    def __init__(self) -> None:
        super().__init__(
            ExternalProvider.bgg,
            ItemKind.boardgame,
            "BoardGameGeek",
            license_name="BoardGameGeek XML API Terms",
            terms_url="https://boardgamegeek.com/wiki/page/BGG_XML_API2",
            attribution_url="https://boardgamegeek.com/",
        )


class MusicBrainzProvider(PlannedProvider):
    def __init__(self) -> None:
        super().__init__(
            ExternalProvider.musicbrainz,
            ItemKind.music,
            "MusicBrainz",
            allows_redistribution=True,
            license_name="MusicBrainz Data Licenses",
            terms_url="https://musicbrainz.org/doc/MusicBrainz_Database",
            attribution_url="https://musicbrainz.org/",
        )
