from app.catalog.media_types import media_type_for_kind
from app.models.base import ExternalProvider, ItemKind
from app.providers.anilist import AniListProvider
from app.providers.base import MetadataProvider
from app.providers.bgg import BGGProvider
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider
from app.providers.igdb import IGDBProvider
from app.providers.musicbrainz import MusicBrainzProvider
from app.providers.openlibrary import OpenLibraryProvider
from app.providers.tmdb import TMDbProvider


class ProviderRegistry:
    def __init__(self) -> None:
        providers: list[MetadataProvider] = [
            ComicVineProvider(),
            GCDProvider(),
            IGDBProvider(),
            TMDbProvider(),
            AniListProvider(),
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
