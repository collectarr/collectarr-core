from app.providers.base import MetadataProvider
from app.providers.comicvine import ComicVineProvider
from app.providers.igdb import IGDBProvider
from app.providers.tmdb import TMDbProvider


class ProviderRegistry:
    def __init__(self) -> None:
        self._providers: dict[str, MetadataProvider] = {
            "comicvine": ComicVineProvider(),
            "igdb": IGDBProvider(),
            "tmdb": TMDbProvider(),
        }

    def get(self, name: str) -> MetadataProvider:
        return self._providers[name]

    def all(self) -> list[MetadataProvider]:
        return list(self._providers.values())

