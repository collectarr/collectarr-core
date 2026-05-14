from app.models.base import ExternalProvider, ItemKind
from app.providers.planned import PlannedProvider


class IGDBProvider(PlannedProvider):
    def __init__(self) -> None:
        super().__init__(
            ExternalProvider.igdb,
            ItemKind.game,
            "IGDB",
            requires_user_key=True,
            license_name="IGDB API Terms",
            terms_url="https://api-docs.igdb.com/",
            attribution_url="https://www.igdb.com/",
            cache_policy="Planned provider; respect IGDB commercial and attribution terms.",
        )
