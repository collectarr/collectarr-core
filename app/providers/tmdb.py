from app.models.base import ExternalProvider, ItemKind
from app.providers.planned import PlannedProvider


class TMDbProvider(PlannedProvider):
    def __init__(self) -> None:
        super().__init__(
            ExternalProvider.tmdb,
            ItemKind.bluray,
            "TMDb",
            requires_user_key=True,
            allows_redistribution=False,
            license_name="TMDb API Terms",
            terms_url="https://www.themoviedb.org/documentation/api/terms-of-use",
            attribution_url="https://www.themoviedb.org/",
            cache_policy="Planned provider; commercial use may require a written agreement.",
        )
