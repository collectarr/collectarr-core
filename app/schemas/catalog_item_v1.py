from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from app.models.partial_date import PartialDateValue
from app.schemas.metadata_music import MusicAlbumTrackV1, MusicAlbumWriteV1


class CatalogItemChildV1(BaseModel):
    model_config = ConfigDict(extra="forbid")


class CatalogIdentifierV1(CatalogItemChildV1):
    identifier_type: str = Field(min_length=1, max_length=64)
    value: str = Field(min_length=1, max_length=255)
    is_primary: bool = False


class CatalogImageV1(CatalogItemChildV1):
    image_type: str = Field(min_length=1, max_length=64)
    url: HttpUrl | None = None
    image_key: str | None = Field(default=None, max_length=512)
    position: int = Field(default=0, ge=0)


class CatalogCreditV1(CatalogItemChildV1):
    name: str = Field(min_length=1, max_length=500)
    role: str = Field(min_length=1, max_length=100)
    sort_name: str | None = Field(default=None, max_length=500)
    character_name: str | None = Field(default=None, max_length=255)


class CatalogSeriesMembershipV1(CatalogItemChildV1):
    series_id: UUID | None = None
    series_title: str = Field(min_length=1, max_length=500)
    position: str | None = Field(default=None, max_length=64)


class CatalogRelatedItemV1(CatalogItemChildV1):
    relation: str = Field(min_length=1, max_length=64)
    item_id: UUID | None = None
    title: str | None = Field(default=None, max_length=500)


class CatalogEpisodeV1(CatalogItemChildV1):
    season_number: int | None = Field(default=None, ge=0)
    episode_number: str | None = Field(default=None, max_length=32)
    title: str = Field(min_length=1, max_length=500)
    air_date: PartialDateValue | None = None
    runtime_minutes: int | None = Field(default=None, ge=0)
    description: str | None = Field(default=None, max_length=10000)


class CatalogSeasonV1(CatalogItemChildV1):
    season_number: int = Field(ge=0)
    title: str | None = Field(default=None, max_length=500)
    episodes: list[CatalogEpisodeV1] = Field(default_factory=list)


class CatalogComponentV1(CatalogItemChildV1):
    name: str = Field(min_length=1, max_length=255)
    quantity: int = Field(default=1, ge=1)
    position: int = Field(default=0, ge=0)


class CatalogMediaTrackV1(CatalogItemChildV1):
    media_number: int = Field(default=1, ge=1)
    title: str | None = Field(default=None, max_length=255)
    media_type: str | None = Field(default=None, max_length=100)
    aspect_ratio: str | None = Field(default=None, max_length=64)
    audio_tracks: list[str] = Field(default_factory=list)
    subtitles: list[str] = Field(default_factory=list)


class CatalogCommonDetailsV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=500)
    sort_title: str | None = Field(default=None, max_length=500)
    subtitle: str | None = Field(default=None, max_length=1000)
    release_date: PartialDateValue | None = None
    identifiers: list[CatalogIdentifierV1] = Field(default_factory=list)
    images: list[CatalogImageV1] = Field(default_factory=list)


class AnimeCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["anime"]
    studios: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    credits: list[CatalogCreditV1] = Field(default_factory=list)
    format: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=64)
    edition_title: str | None = Field(default=None, max_length=500)
    episodes: list[CatalogEpisodeV1] = Field(default_factory=list)


class BoardGameCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["boardgame"]
    edition: str | None = Field(default=None, max_length=255)
    publishers: list[str] = Field(default_factory=list)
    designers: list[str] = Field(default_factory=list)
    mechanics: list[str] = Field(default_factory=list)
    categories: list[str] = Field(default_factory=list)
    player_counts: list[str] = Field(default_factory=list)
    play_time_minutes: int | None = Field(default=None, ge=0)
    components: list[CatalogComponentV1] = Field(default_factory=list)
    related_items: list[CatalogRelatedItemV1] = Field(default_factory=list)


class BookCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["book"]
    contributors: list[CatalogCreditV1] = Field(default_factory=list)
    publisher: str | None = Field(default=None, max_length=255)
    publication_date: PartialDateValue | None = None
    edition: str | None = Field(default=None, max_length=255)
    format: str | None = Field(default=None, max_length=100)
    genres: list[str] = Field(default_factory=list)
    subjects: list[str] = Field(default_factory=list)
    original_title: str | None = Field(default=None, max_length=500)
    series_membership: CatalogSeriesMembershipV1 | None = None


class ComicCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["comic"]
    series: CatalogSeriesMembershipV1 | None = None
    issue_number: str | None = Field(default=None, max_length=64)
    variant: str | None = Field(default=None, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    plot: str | None = Field(default=None, max_length=10000)
    creators: list[CatalogCreditV1] = Field(default_factory=list)
    characters: list[str] = Field(default_factory=list)
    key_issue: bool = False
    story_arcs: list[str] = Field(default_factory=list)


class GameCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["game"]
    platform: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=64)
    edition: str | None = Field(default=None, max_length=255)
    publisher: str | None = Field(default=None, max_length=255)
    related_items: list[CatalogRelatedItemV1] = Field(default_factory=list)


class MangaCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["manga"]
    publisher: str | None = Field(default=None, max_length=255)
    series_membership: CatalogSeriesMembershipV1 | None = None
    volume_number: str | None = Field(default=None, max_length=64)
    edition_format: str | None = Field(default=None, max_length=100)
    chapters: list[str] = Field(default_factory=list)
    contributors: list[CatalogCreditV1] = Field(default_factory=list)


class MovieCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["movie"]
    release_year: int | None = Field(default=None, ge=0, le=9999)
    studios: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    plot: str | None = Field(default=None, max_length=10000)
    audience_rating: Decimal | None = Field(default=None, ge=0, max_digits=5, decimal_places=2)
    credits: list[CatalogCreditV1] = Field(default_factory=list)
    format: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=64)
    runtime_minutes: int | None = Field(default=None, ge=0)
    media_tracks: list[CatalogMediaTrackV1] = Field(default_factory=list)
    box_set: str | None = Field(default=None, max_length=255)


class MusicCatalogWriteDetailsV1(MusicAlbumWriteV1):
    kind: Literal["music"]


class MusicCatalogDetailsV1(MusicAlbumWriteV1):
    kind: Literal["music"]
    tracks: list[MusicAlbumTrackV1] = Field(default_factory=list)


class TVCatalogDetailsV1(CatalogCommonDetailsV1):
    kind: Literal["tv"]
    studios: list[str] = Field(default_factory=list)
    genres: list[str] = Field(default_factory=list)
    credits: list[CatalogCreditV1] = Field(default_factory=list)
    format: str | None = Field(default=None, max_length=100)
    region: str | None = Field(default=None, max_length=64)
    edition_title: str | None = Field(default=None, max_length=500)
    seasons: list[CatalogSeasonV1] = Field(default_factory=list)
    episodes: list[CatalogEpisodeV1] = Field(default_factory=list)


type CatalogItemDetailsV1 = Annotated[
    AnimeCatalogDetailsV1
    | BoardGameCatalogDetailsV1
    | BookCatalogDetailsV1
    | ComicCatalogDetailsV1
    | GameCatalogDetailsV1
    | MangaCatalogDetailsV1
    | MovieCatalogDetailsV1
    | MusicCatalogDetailsV1
    | TVCatalogDetailsV1,
    Field(discriminator="kind"),
]

type CatalogItemWriteDetailsV1 = Annotated[
    AnimeCatalogDetailsV1
    | BoardGameCatalogDetailsV1
    | BookCatalogDetailsV1
    | ComicCatalogDetailsV1
    | GameCatalogDetailsV1
    | MangaCatalogDetailsV1
    | MovieCatalogDetailsV1
    | MusicCatalogWriteDetailsV1
    | TVCatalogDetailsV1,
    Field(discriminator="kind"),
]


class CatalogItemWriteV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    details: CatalogItemWriteDetailsV1


class CatalogItemSummaryV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    kind: Literal["anime", "boardgame", "book", "comic", "game", "manga", "movie", "music", "tv"]
    title: str
    sort_title: str | None = None
    release_date: PartialDateValue | None = None
    cover_image_url: str | None = None


class CatalogItemV1(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    details: CatalogItemDetailsV1
    created_at: datetime
    updated_at: datetime


CATALOG_ITEM_DETAILS_BY_KIND = {
    "anime": AnimeCatalogDetailsV1,
    "boardgame": BoardGameCatalogDetailsV1,
    "book": BookCatalogDetailsV1,
    "comic": ComicCatalogDetailsV1,
    "game": GameCatalogDetailsV1,
    "manga": MangaCatalogDetailsV1,
    "movie": MovieCatalogDetailsV1,
    "music": MusicCatalogDetailsV1,
    "tv": TVCatalogDetailsV1,
}
