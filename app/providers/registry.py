from dataclasses import dataclass

from app.catalog.media_types import media_type_for_kind
from app.models.base import ExternalProvider, ItemKind
from app.providers.anilist import AniListProvider
from app.providers.base import MetadataProvider
from app.providers.bgg import BGGProvider
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider
from app.providers.hardcover import HardcoverProvider
from app.providers.igdb import IGDBProvider
from app.providers.mangadex import MangaDexProvider
from app.providers.musicbrainz import MusicBrainzProvider
from app.providers.openlibrary import OpenLibraryProvider
from app.providers.tmdb import TMDbProvider


@dataclass(frozen=True)
class ProviderRegistryStatus:
    name: str
    display_name: str
    kind: ItemKind
    supported_kinds: tuple[ItemKind, ...]
    is_configured: bool
    status_message: str
    supports_search: bool
    supports_ingest: bool
    requires_user_key: bool
    non_commercial_only: bool
    allows_redistribution: bool
    allows_image_mirroring: bool
    requires_attribution: bool
    license_name: str | None
    terms_url: str | None
    attribution_url: str | None
    rate_limit: str | None
    cache_policy: str | None

    @classmethod
    def from_provider(cls, provider: MetadataProvider) -> "ProviderRegistryStatus":
        capabilities = provider.capabilities
        return cls(
            name=provider.name,
            display_name=capabilities.display_name,
            kind=capabilities.kind,
            supported_kinds=capabilities.supported_kinds,
            is_configured=provider.is_configured,
            status_message=provider.status_message,
            supports_search=capabilities.supports_search,
            supports_ingest=capabilities.supports_ingest,
            requires_user_key=capabilities.requires_user_key,
            non_commercial_only=capabilities.non_commercial_only,
            allows_redistribution=capabilities.allows_redistribution,
            allows_image_mirroring=capabilities.allows_image_mirroring,
            requires_attribution=capabilities.requires_attribution,
            license_name=capabilities.license_name,
            terms_url=capabilities.terms_url,
            attribution_url=capabilities.attribution_url,
            rate_limit=capabilities.rate_limit,
            cache_policy=capabilities.cache_policy,
        )


class ProviderRegistry:
    def __init__(self) -> None:
        providers: list[MetadataProvider] = [
            ComicVineProvider(),
            GCDProvider(),
            HardcoverProvider(),
            IGDBProvider(),
            TMDbProvider(),
            AniListProvider(),
            MangaDexProvider(),
            OpenLibraryProvider(),
            BGGProvider(),
            MusicBrainzProvider(),
        ]
        self._providers = {provider.name: provider for provider in providers}

    def get(self, name: str | ExternalProvider) -> MetadataProvider:
        provider_name = self._provider_name(name)
        return self._providers[provider_name]

    def maybe_get(self, name: str | ExternalProvider) -> MetadataProvider | None:
        return self._providers.get(self._provider_name(name))

    def all(self) -> list[MetadataProvider]:
        return list(self._providers.values())

    def status_entries(self) -> list[ProviderRegistryStatus]:
        return [ProviderRegistryStatus.from_provider(provider) for provider in self.all()]

    def for_kind(self, kind: ItemKind) -> list[MetadataProvider]:
        return [provider for provider in self.all() if provider.capabilities.supports_kind(kind)]

    def default_for_kind(self, kind: ItemKind) -> MetadataProvider | None:
        media_type = media_type_for_kind(kind)
        if media_type is not None:
            for provider_name in media_type.providers:
                provider = self._providers.get(provider_name.value)
                if provider is not None:
                    return provider
        providers = self.for_kind(kind)
        return providers[0] if providers else None

    def _provider_name(self, name: str | ExternalProvider) -> str:
        return name.value if isinstance(name, ExternalProvider) else name
