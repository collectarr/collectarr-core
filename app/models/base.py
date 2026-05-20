import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )


class UuidMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )


class ItemKind(str, enum.Enum):
    anime = "anime"
    boardgame = "boardgame"
    book = "book"
    bluray = "bluray"
    comic = "comic"
    game = "game"
    manga = "manga"
    movie = "movie"
    music = "music"
    tv = "tv"


class ExternalProvider(str, enum.Enum):
    anilist = "anilist"
    bgg = "bgg"
    comicvine = "comicvine"
    gcd = "gcd"
    hardcover = "hardcover"
    igdb = "igdb"
    mangadex = "mangadex"
    musicbrainz = "musicbrainz"
    openlibrary = "openlibrary"
    tmdb = "tmdb"


class SeriesRelationType(str, enum.Enum):
    sequel = "sequel"
    prequel = "prequel"
    side_story = "side_story"
    spin_off = "spin_off"
    parent = "parent"
    adaptation = "adaptation"
    alternative = "alternative"
    summary = "summary"
    compilation = "compilation"
    other = "other"


class UserRole(str, enum.Enum):
    viewer = "viewer"
    editor = "editor"
    admin = "admin"
