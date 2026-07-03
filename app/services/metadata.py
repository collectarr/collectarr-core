import asyncio
import logging
import re
from collections import defaultdict
from dataclasses import replace
from datetime import date
from typing import Any
from urllib.parse import urlparse
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import status
from sqlalchemy import extract, func, inspect, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.orm.attributes import NO_VALUE

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.models import (
    AnimeCharacterAppearance,
    AnimeContribution,
    AnimeEpisode,
    AnimeIdentifier,
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeriesMembership,
    BookWork,
    Character,
    CharacterAppearance,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicStoryArcMembership,
    ComicWork,
    EntityPerson,
    ExternalProviderId,
    GameRelease,
    GameWork,
    Item,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaIdentifier,
    MangaSeriesMembership,
    MangaWork,
    MovieRelease,
    MovieReleaseMedia,
    MovieWork,
    MovieWorkContribution,
    MovieWorkIdentifier,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    Person,
    StoryArc,
    StoryArcItem,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseIdentifier,
    TVReleaseMedia,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import MetadataProvider, ProviderSearchResult
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider
from app.providers.registry import ProviderRegistry
from app.schemas import (
    AnimeCharacterResponse,
    AnimeContributorResponse,
    AnimeEpisodeV1Response,
    AnimeIdentifierResponse,
    AnimeSeriesV1Response,
    BoardGameEditionV1Response,
    BoardGameWorkV1Response,
    BookContributorResponse,
    BookEditionV1Response,
    BookIdentifierResponse,
    BookSeriesResponse,
    BookWorkV1Response,
    CharacterAppearanceResponse,
    CharacterFacetResponse,
    CharacterResponse,
    ComicCharacterResponse,
    ComicContributorResponse,
    ComicIdentifierResponse,
    ComicIssueV1Response,
    ComicStoryArcResponse,
    ComicWorkV1Response,
    CreatorCreditResponse,
    CreatorFacetResponse,
    CreatorResponse,
    ExternalProviderIdResponse,
    GameReleaseV1Response,
    GameWorkV1Response,
    MangaChapterV1Response,
    MangaCharacterResponse,
    MangaContributorResponse,
    MangaIdentifierResponse,
    MangaSeriesResponse,
    MangaWorkV1Response,
    MetadataProposalCreate,
    MetadataProposalResponse,
    MovieContributorResponse,
    MovieIdentifierResponse,
    MovieReleaseMediaResponse,
    MovieReleaseV1Response,
    MovieWorkV1Response,
    MusicContributorResponse,
    MusicIdentifierResponse,
    MusicMediaV1Response,
    MusicReleaseV1Response,
    MusicTrackV1Response,
    ProviderSearchResultResponse,
    SeasonResponse,
    StoryArcFacetResponse,
    StoryArcItemResponse,
    StoryArcResponse,
    TVContributorResponse,
    TVEpisodeV1Response,
    TVIdentifierResponse,
    TVReleaseMediaResponse,
    TVSeasonV1Response,
    TVSeriesV1Response,
)
from app.schemas import (
    EpisodeResponse as ProviderEpisodeResponse,
)
from app.schemas.metadata_shared import SearchResult, public_item_kind
from app.search.client import SearchClient
from app.services.metadata_helpers import (
    _loaded_rows,
    _metadata_links,
    _metadata_list,
    _model_text_or_metadata,
    _organization_name,
)
from app.services.metadata_public import (
    barcode_provider_search as _barcode_provider_search,
)
from app.services.metadata_public import (
    create_proposal as _create_proposal,
)
from app.services.metadata_public import (
    mirror_provider_image_bytes as _mirror_provider_image_bytes,
)
from app.services.metadata_public import (
    mirror_provider_image_url as _mirror_provider_image_url,
)
from app.services.metadata_public import (
    search_default_provider as _search_default_provider,
)
from app.services.metadata_public import (
    search_provider as _search_provider,
)
from app.services.metadata_typed_reads import MetadataTypedReadService
from app.services.provider_search_state import ProviderSearchState

logger = logging.getLogger(__name__)

_UPSTREAM_HTTP_STATUS_RE = re.compile(r"\bHTTP\s+(?P<status>\d{3})\b")
_PROVIDER_INTERNAL_RETRY_NAMES = {ExternalProvider.bgg.value, ExternalProvider.comicvine.value}


class MetadataService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.settings = get_settings()
        self.search_client = SearchClient()
        self.providers = ProviderRegistry()
        self.provider_search_state = ProviderSearchState(self.settings)
        self.typed_reads = MetadataTypedReadService(self)

    def __getattr__(self, name: str) -> Any:
        try:
            return getattr(self.typed_reads, name)
        except AttributeError as exc:
            raise AttributeError(name) from exc

    async def _provider_links_for_entity(
        self,
        entity_type: str,
        entity_id: UUID,
    ) -> list[ExternalProviderIdResponse]:
        result = await self.db.execute(
            select(ExternalProviderId)
            .where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id == entity_id,
            )
            .order_by(ExternalProviderId.provider, ExternalProviderId.provider_item_id)
        )
        return [
            ExternalProviderIdResponse(
                provider=row.provider,
                entity_type=row.entity_type,
                provider_item_id=row.provider_item_id,
                site_url=row.site_url,
                api_url=row.api_url,
            )
            for row in result.scalars()
        ]

    async def get_item(
        self, item_id: UUID, kind: ItemKind
    ) -> (
        BookWorkV1Response
        | BoardGameWorkV1Response
        | AnimeSeriesV1Response
        | ComicWorkV1Response
        | GameWorkV1Response
        | MangaWorkV1Response
        | MovieWorkV1Response
        | MusicReleaseV1Response
        | TVSeriesV1Response
        | dict[str, Any]
    ):
        if kind == ItemKind.book:
            return await self.get_book_work(item_id)
        if kind == ItemKind.comic:
            try:
                return await self.get_comic_work(item_id)
            except ApiHTTPException as exc:
                if exc.code != "comic_work_not_found":
                    raise
        if kind == ItemKind.manga:
            return await self.get_manga_work(item_id)
        if kind == ItemKind.anime:
            return await self.get_anime_series(item_id)
        if kind == ItemKind.movie:
            return await self.get_movie_work(item_id)
        if kind == ItemKind.tv:
            return await self.get_tv_series(item_id)
        if kind == ItemKind.music:
            return await self.get_music_release(item_id)
        if kind == ItemKind.game:
            return await self.get_game_work(item_id)
        if kind == ItemKind.boardgame:
            return await self.get_boardgame_work(item_id)
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="metadata_item_not_found",
            detail="Item not found",
        )

    def _book_contributor_response(
        self,
        contribution: BookContribution,
        *,
        scope: str,
    ) -> BookContributorResponse:
        person = contribution.person
        return BookContributorResponse(
            person_id=contribution.person_id,
            name=person.name if person is not None else "",
            role=contribution.role,
            sequence=contribution.sequence,
            scope=scope,
        )

    def _book_identifier_response(self, identifier: BookIdentifier) -> BookIdentifierResponse:
        return BookIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            normalized_value=identifier.normalized_value,
            is_primary=identifier.is_primary,
            source_provider=identifier.source_provider,
        )

    def _book_edition_response(self, edition: BookEdition) -> BookEditionV1Response:
        return BookEditionV1Response(
            id=edition.id,
            work_id=edition.work_id,
            display_title=edition.display_title,
            edition_statement=edition.edition_statement,
            format=edition.format,
            binding=edition.binding,
            publication_date=edition.publication_date,
            publisher=edition.publisher,
            imprint=edition.imprint,
            language=edition.language,
            region=edition.region,
            page_count=edition.page_count,
            audio_length_minutes=edition.audio_length_minutes,
            age_rating=edition.age_rating,
            release_status=edition.release_status,
            cover_image_url=edition.cover_image_url,
            cover_image_key=edition.cover_image_key,
            description=edition.description,
            contributors=[
                self._book_contributor_response(row, scope="edition")
                for row in sorted(
                    edition.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._book_identifier_response(row)
                for row in sorted(
                    edition.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
        )

    def _book_series_response(self, membership: BookSeriesMembership) -> BookSeriesResponse:
        series = membership.series
        return BookSeriesResponse(
            id=series.id,
            title=series.title,
            slug=series.slug,
            sequence=membership.sequence,
            display_number=membership.display_number,
        )

    def _book_work_response(self, work: BookWork) -> BookWorkV1Response:
        editions = sorted(
            work.editions or [],
            key=lambda e: (
                e.publication_date is None,
                e.publication_date or date.max,
                str(e.id),
            ),
        )
        return BookWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            original_publication_date=work.original_publication_date,
            first_publication_date=work.first_publication_date,
            contributors=[
                self._book_contributor_response(row, scope="work")
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            series=[
                self._book_series_response(row)
                for row in sorted(
                    work.series_memberships or [],
                    key=lambda m: (
                        m.sequence is None,
                        m.sequence or 0,
                        str(m.series_id),
                    ),
                )
            ],
            editions=[self._book_edition_response(row) for row in editions],
        )

    def _game_release_response(self, release: GameRelease) -> GameReleaseV1Response:
        return GameReleaseV1Response(
            id=release.id,
            work_id=release.work_id,
            release_title=release.release_title,
            platform=release.platform,
            release_date=release.release_date,
            region_code=release.region_code,
            format=release.format,
            publisher=release.publisher,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            release_status=release.release_status,
            language=release.language,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
        )

    def _game_work_response(self, work: GameWork) -> GameWorkV1Response:
        releases = sorted(
            work.releases or [],
            key=lambda row: (
                getattr(row, "release_date", None) is None,
                getattr(row, "release_date", None) or date.max,
                str(getattr(row, "id", "")),
            ),
        )
        primary_release = releases[0] if releases else None
        metadata = work.metadata_json or {}
        return GameWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            release_date=work.release_date,
            original_language=work.original_language,
            publisher=primary_release.publisher if primary_release is not None else None,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            search_aliases=_metadata_list(metadata, "search_aliases"),
            genres=_metadata_list(metadata, "genres"),
            platforms=_metadata_list(metadata, "platforms"),
            identifiers=_metadata_list(metadata, "identifiers"),
            company_roles=_metadata_list(metadata, "company_roles"),
            age_ratings=_metadata_list(metadata, "age_ratings"),
            trailer_urls=_metadata_links(metadata, "trailer_urls"),
            external_links=_metadata_links(metadata, "external_links"),
            releases=[self._game_release_response(row) for row in releases],
        )

    def _boardgame_edition_response(self, edition: BoardGameEdition) -> BoardGameEditionV1Response:
        return BoardGameEditionV1Response(
            id=edition.id,
            work_id=edition.work_id,
            edition_title=edition.edition_title,
            format=edition.format,
            release_date=edition.release_date,
            publisher=edition.publisher,
            catalog_number=edition.catalog_number,
            barcode=edition.barcode,
            release_status=edition.release_status,
            language=edition.language,
            country=edition.country,
            age_rating=edition.age_rating,
            audience_rating=edition.audience_rating,
            min_players=edition.min_players,
            max_players=edition.max_players,
            playing_time_minutes=edition.playing_time_minutes,
            min_age=edition.min_age,
            cover_image_url=edition.cover_image_url,
            cover_image_key=edition.cover_image_key,
            description=edition.description,
        )

    def _boardgame_work_response(self, work: BoardGameWork) -> BoardGameWorkV1Response:
        editions = sorted(
            work.editions or [],
            key=lambda row: (
                getattr(row, "release_date", None) is None,
                getattr(row, "release_date", None) or date.max,
                str(getattr(row, "id", "")),
            ),
        )
        primary_edition = editions[0] if editions else None
        metadata = work.metadata_json or {}
        return BoardGameWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            release_date=work.release_date,
            original_language=work.original_language,
            publisher=primary_edition.publisher if primary_edition is not None else None,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            search_aliases=_metadata_list(metadata, "search_aliases"),
            genres=_metadata_list(metadata, "genres"),
            platforms=_metadata_list(metadata, "platforms"),
            identifiers=_metadata_list(metadata, "identifiers"),
            contributors=_metadata_list(metadata, "contributors"),
            mechanics=_metadata_list(metadata, "mechanics"),
            categories=_metadata_list(metadata, "categories"),
            families=_metadata_list(metadata, "families"),
            expansions=_metadata_list(metadata, "expansions"),
            rankings=_metadata_list(metadata, "rankings"),
            trailer_urls=_metadata_links(metadata, "trailer_urls"),
            external_links=_metadata_links(metadata, "external_links"),
            editions=[self._boardgame_edition_response(row) for row in editions],
        )

    def _comic_contributor_response(
        self,
        contribution: ComicContribution,
        *,
        scope: str,
    ) -> ComicContributorResponse:
        person = contribution.person
        return ComicContributorResponse(
            person_id=contribution.person_id,
            name=person.name if person is not None else "",
            role=contribution.role,
            sequence=contribution.sequence,
            scope=scope,
        )

    def _comic_identifier_response(self, identifier: ComicIdentifier) -> ComicIdentifierResponse:
        return ComicIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            normalized_value=identifier.normalized_value,
            is_primary=identifier.is_primary,
            source_provider=identifier.source_provider,
        )

    def _comic_issue_response(self, issue: ComicIssue) -> ComicIssueV1Response:
        return ComicIssueV1Response(
            id=issue.id,
            work_id=issue.work_id,
            issue_number=issue.issue_number,
            display_title=issue.display_title,
            publication_date=issue.publication_date,
            release_date=issue.release_date,
            publisher=issue.publisher,
            imprint=issue.imprint,
            language=issue.language,
            region=issue.region,
            page_count=issue.page_count,
            cover_price_cents=issue.cover_price_cents,
            currency=issue.currency,
            release_status=issue.release_status,
            cover_image_url=issue.cover_image_url,
            cover_image_key=issue.cover_image_key,
            description=issue.description,
            contributors=[
                self._comic_contributor_response(row, scope="issue")
                for row in sorted(
                    issue.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._comic_identifier_response(row)
                for row in sorted(
                    issue.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            characters=[
                ComicCharacterResponse(
                    character_id=row.character_id,
                    name=row.character.name if row.character is not None else "",
                    role=row.role,
                )
                for row in sorted(
                    issue.character_appearances or [],
                    key=lambda c: (
                        c.role.casefold(),
                        str(c.character_id),
                    ),
                )
            ],
            story_arcs=[
                ComicStoryArcResponse(
                    story_arc_id=row.story_arc_id,
                    name=row.story_arc.name if row.story_arc is not None else "",
                    ordinal=row.ordinal,
                )
                for row in sorted(
                    issue.story_arc_memberships or [],
                    key=lambda a: (
                        a.ordinal is None,
                        a.ordinal or 0,
                        str(a.story_arc_id),
                    ),
                )
            ],
        )

    def _manga_work_response(self, work: MangaWork) -> MangaWorkV1Response:
        chapters = sorted(
            work.chapters or [],
            key=lambda c: (
                c.chapter_number is None,
                c.chapter_number or 0,
                c.publication_date is None,
                c.publication_date or date.max,
                str(c.id),
            ),
        )
        return MangaWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            original_publication_date=work.original_publication_date,
            first_publication_date=work.first_publication_date,
            status=work.status,
            series=[
                self._manga_series_response(row)
                for row in sorted(
                    work.series_memberships or [],
                    key=lambda m: (
                        m.sequence is None,
                        m.sequence or 0,
                        str(m.series_id),
                    ),
                )
            ],
            chapters=[self._manga_chapter_response(row) for row in chapters],
            contributions=[
                self._manga_contributor_response(row)
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._manga_identifier_response(row)
                for row in sorted(
                    work.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[
                self._manga_character_response(row)
                for row in sorted(
                    work.character_appearances or [],
                    key=lambda c: (
                        c.role.casefold(),
                        str(c.character_id),
                    ),
                )
            ],
        )

    def _manga_chapter_response(self, chapter: MangaChapter) -> MangaChapterV1Response:
        return MangaChapterV1Response(
            id=chapter.id,
            work_id=chapter.work_id,
            chapter_number=chapter.chapter_number,
            chapter_title=chapter.chapter_title,
            publication_date=chapter.publication_date,
            page_count=chapter.page_count,
            description=chapter.description,
            cover_image_url=chapter.cover_image_url,
            cover_image_key=chapter.cover_image_key,
        )

    def _manga_contributor_response(self, contrib: MangaContribution) -> MangaContributorResponse:
        return MangaContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _manga_identifier_response(self, identifier: MangaIdentifier) -> MangaIdentifierResponse:
        return MangaIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _manga_character_response(self, char: MangaCharacterAppearance) -> MangaCharacterResponse:
        return MangaCharacterResponse(
            id=char.id,
            character_id=char.character_id,
            character_name=char.character.name if char.character is not None else "",
            role=char.role,
        )

    def _anime_series_response(self, series: AnimeSeries) -> AnimeSeriesV1Response:
        episodes = sorted(
            series.episodes or [],
            key=lambda e: (
                e.episode_number is None,
                e.episode_number or 0,
                e.air_date is None,
                e.air_date or date.max,
                str(e.id),
            ),
        )
        return AnimeSeriesV1Response(
            id=series.id,
            title=series.title,
            sort_title=series.sort_title,
            description=series.description,
            original_language=series.original_language,
            original_air_date=series.original_air_date,
            end_date=series.end_date,
            status=series.status,
            anime_type=series.anime_type,
            episode_count=series.episode_count,
            episodes=[self._anime_episode_response(row) for row in episodes],
            contributions=[
                self._anime_contributor_response(row)
                for row in sorted(
                    series.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._anime_identifier_response(row)
                for row in sorted(
                    series.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[
                self._anime_character_response(row)
                for row in sorted(
                    series.character_appearances or [],
                    key=lambda c: (
                        c.role.casefold(),
                        str(c.character_id),
                    ),
                )
            ],
        )

    def _anime_episode_response(self, episode: AnimeEpisode) -> AnimeEpisodeV1Response:
        return AnimeEpisodeV1Response(
            id=episode.id,
            series_id=episode.series_id,
            episode_number=episode.episode_number,
            episode_title=episode.episode_title,
            air_date=episode.air_date,
            description=episode.description,
            cover_image_url=episode.cover_image_url,
            cover_image_key=episode.cover_image_key,
            runtime_minutes=episode.runtime_minutes,
        )

    def _anime_contributor_response(self, contrib: AnimeContribution) -> AnimeContributorResponse:
        return AnimeContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _anime_identifier_response(self, identifier: AnimeIdentifier) -> AnimeIdentifierResponse:
        return AnimeIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _anime_character_response(self, char: AnimeCharacterAppearance) -> AnimeCharacterResponse:
        return AnimeCharacterResponse(
            id=char.id,
            character_id=char.character_id,
            character_name=char.character.name if char.character is not None else "",
            role=char.role,
        )

    def _movie_work_response(self, work: MovieWork) -> MovieWorkV1Response:
        releases = sorted(
            work.releases or [],
            key=lambda r: (
                r.release_date is None,
                r.release_date or date.max,
                str(r.id),
            ),
        )
        return MovieWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            release_date=work.original_release_date,
            runtime_minutes=work.runtime_minutes,
            age_rating=work.age_rating,
            audience_rating=work.audience_rating,
            releases=[self._movie_release_response(row) for row in releases],
            contributions=[
                self._movie_contributor_response(row)
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            trailer_urls=_metadata_links(work.metadata_json, "trailer_urls"),
            external_links=_metadata_links(work.metadata_json, "external_links"),
            identifiers=[
                self._movie_identifier_response(row)
                for row in sorted(
                    work.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[],  # Not supported in v1 schema
        )

    def _movie_release_media_response(self, media: MovieReleaseMedia) -> MovieReleaseMediaResponse:
        return MovieReleaseMediaResponse(
            id=media.id,
            release_id=media.release_id,
            media_number=media.media_number,
            media_type=media.media_type,
            title=media.title,
            aspect_ratio=media.aspect_ratio,
            screen_ratio=media.screen_ratio,
            color=media.color,
            num_discs=media.num_discs,
            nr_layers=media.nr_layers,
            layers=media.layers,
            audio_tracks=media.audio_tracks,
            subtitles=media.subtitles,
        )

    def _movie_release_response(self, release: MovieRelease) -> MovieReleaseV1Response:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        return MovieReleaseV1Response(
            id=release.id,
            work_id=release.work_id,
            release_date=release.release_date,
            region=release.region_code,
            format=release.format,
            distributor=release.distributor,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            trailer_urls=_metadata_links(release.metadata_json, "trailer_urls"),
            external_links=_metadata_links(release.metadata_json, "external_links"),
            media=[self._movie_release_media_response(row) for row in media],
        )

    def _movie_contributor_response(self, contrib: MovieWorkContribution) -> MovieContributorResponse:
        return MovieContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
            character_name=contrib.character_name,
        )

    def _movie_identifier_response(self, identifier: MovieWorkIdentifier) -> MovieIdentifierResponse:
        return MovieIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _music_release_response(self, release: MusicRelease) -> MusicReleaseV1Response:
        track_count = release.track_count
        if track_count is None:
            media_track_counts = [
                media.track_count
                for media in (release.media or [])
                if media.track_count is not None
            ]
            if media_track_counts:
                track_count = sum(media_track_counts)
            else:
                track_count = sum(len(media.tracks or []) for media in (release.media or [])) or None
        media_list = []
        if release.media:
            for m in sorted(
                release.media,
                key=lambda media: (media.media_number, str(media.id)),
            ):
                tracks = [
                    MusicTrackV1Response(
                        id=t.id,
                        media_id=t.media_id,
                        position=t.position,
                        title=t.title,
                        duration_ms=t.duration_ms,
                        instrument=t.instrument,
                        composition=t.composition,
                    )
                    for t in sorted(
                        m.tracks or [],
                        key=lambda track: (track.position.casefold(), str(track.id)),
                    )
                ]
                media_list.append(
                    MusicMediaV1Response(
                        id=m.id,
                        release_id=m.release_id,
                        media_number=m.media_number,
                        media_type=m.media_type,
                        title=m.title,
                        track_count=m.track_count,
                        packaging=m.packaging,
                        media_condition=m.media_condition,
                        sound_type=m.sound_type,
                        vinyl_color=m.vinyl_color,
                        vinyl_weight=m.vinyl_weight,
                        rpm=m.rpm,
                        spars=m.spars,
                        tracks=tracks,
                    )
                )
        return MusicReleaseV1Response(
            id=release.id,
            title=release.title,
            sort_title=release.sort_title,
            subtitle=release.subtitle,
            release_status=release.release_status,
            release_date=release.release_date,
            recording_date=release.recording_date,
            track_count=track_count,
            publisher=release.publisher,
            studio=release.studio,
            catalog_number=release.catalog_number,
            barcode=release.barcode,
            country_code=release.country_code,
            language=release.language,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            extras=release.extras,
            media=media_list,
            contributions=[
                self._music_contributor_response(row)
                for row in sorted(
                    release.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._music_identifier_response(row)
                for row in sorted(
                    release.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
        )

    def _music_media_response(self, media: MusicMedia) -> MusicMediaV1Response:
        return MusicMediaV1Response(
            id=media.id,
            release_id=media.release_id,
            media_number=media.media_number,
            media_type=media.media_type,
            title=media.title,
            track_count=media.track_count,
            packaging=media.packaging,
            media_condition=media.media_condition,
            sound_type=media.sound_type,
            vinyl_color=media.vinyl_color,
            vinyl_weight=media.vinyl_weight,
            rpm=media.rpm,
            spars=media.spars,
            tracks=[self._music_track_response(track) for track in sorted(
                media.tracks or [],
                key=lambda track: (track.position.casefold(), str(track.id)),
            )],
        )

    def _music_track_response(self, track: MusicTrack) -> MusicTrackV1Response:
        return MusicTrackV1Response(
            id=track.id,
            media_id=track.media_id,
            position=track.position,
            title=track.title,
            duration_ms=track.duration_ms,
            instrument=track.instrument,
            composition=track.composition,
        )

    def _music_contributor_response(self, contrib: MusicReleaseContribution) -> MusicContributorResponse:
        return MusicContributorResponse(
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _music_identifier_response(self, identifier: MusicReleaseIdentifier) -> MusicIdentifierResponse:
        return MusicIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            normalized_value=identifier.normalized_value or identifier.value,
            is_primary=identifier.is_primary,
            source_provider=identifier.source_provider,
        )

    def _tv_episode_response(self, episode: TVEpisode) -> TVEpisodeV1Response:
        return TVEpisodeV1Response(
            id=episode.id,
            series_id=episode.release_id,
            episode_number=float(episode.episode_number),
            episode_title=episode.title,
            air_date=episode.original_air_date,
            description=episode.overview,
            cover_image_url=episode.still_url,
            cover_image_key=episode.still_key,
            runtime_minutes=episode.duration_seconds // 60 if episode.duration_seconds is not None else None,
        )

    def _tv_release_media_response(self, media: TVReleaseMedia) -> TVReleaseMediaResponse:
        return TVReleaseMediaResponse(
            id=media.id,
            release_id=media.release_id,
            media_number=media.media_number,
            media_type=media.media_type,
            title=media.title,
            episode_count=media.episode_count,
            runtime_minutes=media.runtime_minutes,
            region_code=media.region_code,
            encoding=media.encoding,
            aspect_ratio=media.aspect_ratio,
            color=media.color,
            audio_tracks=media.audio_tracks,
            subtitles=media.subtitles,
            layers=media.layers,
            frame_rate=media.frame_rate,
            bit_depth=media.bit_depth,
            resolution=media.resolution,
            hdr_format=media.hdr_format,
        )

    def _tv_season_response(self, release: TVRelease, season_number: int, episodes: list[TVEpisode]) -> TVSeasonV1Response:
        ordered_episodes = sorted(
            episodes,
            key=lambda episode: (episode.episode_number, episode.original_air_date or date.max, str(episode.id)),
        )
        season_air_date = next((episode.original_air_date for episode in ordered_episodes if episode.original_air_date), None)
        return TVSeasonV1Response(
            id=uuid5(NAMESPACE_URL, f"tv-season:{release.id}:{season_number}"),
            series_id=release.id,
            season_number=season_number,
            air_date=season_air_date,
            episode_count=len(ordered_episodes),
            description=release.description,
            cover_image_url=release.cover_image_url,
            cover_image_key=release.cover_image_key,
            episodes=[self._tv_episode_response(episode) for episode in ordered_episodes],
        )

    def _tv_series_response(self, release: TVRelease) -> TVSeriesV1Response:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        episodes_by_season: dict[int, list[TVEpisode]] = defaultdict(list)
        for episode in release.episodes or []:
            episodes_by_season[episode.season_number].append(episode)
        seasons = [
            self._tv_season_response(release, season_number, episodes)
            for season_number, episodes in sorted(episodes_by_season.items(), key=lambda item: item[0])
        ]
        return TVSeriesV1Response(
            id=release.id,
            title=release.title,
            sort_title=release.sort_title,
            description=release.description,
            original_language=None,
            original_air_date=release.release_date,
            end_date=None,
            status=None,
            season_count=release.season_count or len(seasons),
            episode_count=release.episode_count or sum(len(season.episodes) for season in seasons),
            network=release.publisher,
            seasons=seasons,
            media=[self._tv_release_media_response(row) for row in media],
            contributions=[
                self._tv_contributor_response(row)
                for row in sorted(
                    release.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            identifiers=[
                self._tv_identifier_response(row)
                for row in sorted(
                    release.identifiers or [],
                    key=lambda i: (
                        i.identifier_type.casefold(),
                        (i.normalized_value or i.value or "").casefold(),
                        str(i.id),
                    ),
                )
            ],
            character_appearances=[],
        )

    def _tv_contributor_response(self, contrib: TVReleaseContribution) -> TVContributorResponse:
        return TVContributorResponse(
            id=contrib.id,
            person_id=contrib.person_id,
            name=contrib.person.name if contrib.person is not None else "",
            role=contrib.role,
            sequence=contrib.sequence,
        )

    def _tv_identifier_response(self, identifier: TVReleaseIdentifier) -> TVIdentifierResponse:
        return TVIdentifierResponse(
            id=identifier.id,
            identifier_type=identifier.identifier_type,
            value=identifier.value,
            is_primary=identifier.is_primary,
        )

    def _comic_work_response(self, work: ComicWork) -> ComicWorkV1Response:
        issues = sorted(
            work.issues or [],
            key=lambda i: (
                i.publication_date is None,
                i.publication_date or date.max,
                i.issue_number is None,
                i.issue_number or "",
                str(i.id),
            ),
        )
        return ComicWorkV1Response(
            id=work.id,
            title=work.title,
            sort_title=work.sort_title,
            subtitle=work.subtitle,
            description=work.description,
            original_language=work.original_language,
            first_publication_date=work.first_publication_date,
            contributors=[
                self._comic_contributor_response(row, scope="work")
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
            ],
            issues=[self._comic_issue_response(row) for row in issues],
        )

    def _manga_series_response(self, membership: MangaSeriesMembership) -> MangaSeriesResponse:
        series = membership.series
        return MangaSeriesResponse(
            id=series.id,
            title=series.title,
            slug=series.slug,
            sequence=membership.sequence,
            display_number=membership.display_number,
        )

    async def search(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        series: str | None = None,
        issue_number: str | None = None,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        language: str | None = None,
        country: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
        year: int | None = None,
        barcode: str | None = None,
        limit: int = 25,
    ) -> list[SearchResult]:
        if not any(
            value is not None and str(value).strip()
            for value in (
                query,
                series,
                issue_number,
                publisher,
                imprint,
                subtitle,
                series_group,
                language,
                country,
                age_rating,
                catalog_number,
                release_status,
                year,
                barcode,
            )
        ):
            return []

        meili_results = await self.search_client.search(
            query=query or "",
            kind=kind,
            series=series,
            issue_number=issue_number,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            series_group=series_group,
            language=language,
            country=country,
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=release_status,
            year=year,
            barcode=barcode,
            limit=limit,
        )
        if meili_results is not None and not barcode:
            return [
                SearchResult(
                    **{
                        **result,
                        "kind": public_item_kind(result.get("kind")),
                    }
                )
                for result in meili_results
            ]
        if kind == ItemKind.comic:
            comic_results = await self._search_comic_works(
                query=query,
                series=series,
                issue_number=issue_number,
                publisher=publisher,
                imprint=imprint,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if comic_results:
                return comic_results
        if kind == ItemKind.book:
            book_results = await self._search_book_works(
                query=query,
                series=series,
                publisher=publisher,
                imprint=imprint,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if book_results:
                return book_results
        if kind == ItemKind.movie:
            movie_results = await self._search_movie_works(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if movie_results:
                return movie_results
        if kind == ItemKind.tv:
            tv_results = await self._search_tv_releases(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if tv_results:
                return tv_results
        if kind == ItemKind.anime:
            anime_results = await self._search_anime_series(
                query=query,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if anime_results:
                return anime_results
        if kind == ItemKind.music:
            music_results = await self._search_music_releases(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                catalog_number=catalog_number,
                limit=limit,
            )
            if music_results:
                return music_results
        if kind == ItemKind.boardgame:
            boardgame_results = await self._search_boardgame_works(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if boardgame_results:
                return boardgame_results
        if kind == ItemKind.game:
            game_results = await self._search_game_works(
                query=query,
                publisher=publisher,
                subtitle=subtitle,
                language=language,
                country=country,
                age_rating=age_rating,
                catalog_number=catalog_number,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if game_results:
                return game_results
        if kind == ItemKind.manga:
            manga_results = await self._search_manga_works(
                query=query,
                language=language,
                country=country,
                release_status=release_status,
                year=year,
                barcode=barcode,
                limit=limit,
            )
            if manga_results:
                return manga_results
        if kind is None:
            results: list[SearchResult] = []
            for batch in (
                await self._search_comic_works(
                    query=query,
                    series=series,
                    issue_number=issue_number,
                    publisher=publisher,
                    imprint=imprint,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_book_works(
                    query=query,
                    series=series,
                    publisher=publisher,
                    imprint=imprint,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_movie_works(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_tv_releases(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_anime_series(
                    query=query,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_music_releases(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    catalog_number=catalog_number,
                    limit=limit,
                ),
                await self._search_boardgame_works(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_game_works(
                    query=query,
                    publisher=publisher,
                    subtitle=subtitle,
                    language=language,
                    country=country,
                    age_rating=age_rating,
                    catalog_number=catalog_number,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
                await self._search_manga_works(
                    query=query,
                    language=language,
                    country=country,
                    release_status=release_status,
                    year=year,
                    barcode=barcode,
                    limit=limit,
                ),
            ):
                results.extend(batch)
            deduped: list[SearchResult] = []
            seen: set[tuple[ItemKind, UUID]] = set()
            for result in results:
                key = (result.kind, result.id)
                if key in seen:
                    continue
                seen.add(key)
                deduped.append(result)
            return deduped[:limit]
        return []

    async def lookup_barcode(self, barcode: str, kind: ItemKind | None = None) -> SearchResult:
        if kind == ItemKind.comic:
            match = await self._comic_work_by_barcode(barcode)
            if match is not None:
                return self._comic_search_result(match[0], issue=match[1])
        if kind == ItemKind.book:
            match = await self._book_work_by_barcode(barcode)
            if match is not None:
                return self._book_search_result(match[0], edition=match[1])
        if kind == ItemKind.movie:
            match = await self._movie_work_by_barcode(barcode)
            if match is not None:
                return self._movie_search_result(match[0], release=match[1])
        if kind == ItemKind.tv:
            release = await self._tv_release_by_barcode(barcode)
            if release is not None:
                return self._tv_search_result(release)
        if kind == ItemKind.anime:
            series = await self._anime_series_by_barcode(barcode)
            if series is not None:
                return self._anime_search_result(series)
        if kind == ItemKind.music:
            release = await self._music_release_by_barcode(barcode)
            if release is not None:
                return self._music_search_result(release)
        if kind == ItemKind.boardgame:
            work = await self._boardgame_work_by_barcode(barcode)
            if work is not None:
                return self._boardgame_search_result(work)
        if kind == ItemKind.game:
            work = await self._game_work_by_barcode(barcode)
            if work is not None:
                return self._game_search_result(work)
        if kind == ItemKind.manga:
            work = await self._manga_work_by_barcode(barcode)
            if work is not None:
                return self._manga_search_result(work)
        if kind is None:
            for lookup in (
                self._comic_work_by_barcode,
                self._book_work_by_barcode,
                self._movie_work_by_barcode,
                self._tv_release_by_barcode,
                self._anime_series_by_barcode,
                self._music_release_by_barcode,
                self._boardgame_work_by_barcode,
                self._game_work_by_barcode,
                self._manga_work_by_barcode,
            ):
                match = await lookup(barcode)
                if match is None:
                    continue
                if isinstance(match, tuple):
                    if isinstance(match[0], ComicWork):
                        return self._comic_search_result(match[0], issue=match[1])
                    if isinstance(match[0], BookWork):
                        return self._book_search_result(match[0], edition=match[1])
                    if isinstance(match[0], MovieWork):
                        return self._movie_search_result(match[0], release=match[1])
                if isinstance(match, TVRelease):
                    return self._tv_search_result(match)
                if isinstance(match, AnimeSeries):
                    return self._anime_search_result(match)
                if isinstance(match, MusicRelease):
                    return self._music_search_result(match)
                if isinstance(match, BoardGameWork):
                    return self._boardgame_search_result(match)
                if isinstance(match, GameWork):
                    return self._game_search_result(match)
                if isinstance(match, MangaWork):
                    return self._manga_search_result(match)
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="barcode_not_found",
            detail="Barcode not found",
        )

    async def _search_comic_works(
        self,
        *,
        query: str | None,
        series: str | None,
        issue_number: str | None,
        publisher: str | None,
        imprint: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(ComicWork)
            .options(
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.contributions)
                .selectinload(ComicContribution.person),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.character_appearances)
                .selectinload(ComicCharacterAppearance.character),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.story_arc_memberships)
                .selectinload(ComicStoryArcMembership.story_arc),
            )
            .order_by(ComicWork.sort_title.asc().nullslast(), ComicWork.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    ComicWork.title.ilike(pattern),
                    ComicIssue.issue_number.ilike(pattern),
                    ComicIssue.display_title.ilike(pattern),
                    ComicIssue.publisher.ilike(pattern),
                    ComicIssue.imprint.ilike(pattern),
                )
            )
        if series and series.strip():
            stmt = stmt.where(ComicWork.title.ilike(f"%{series.strip()}%"))
        if issue_number and issue_number.strip():
            stmt = stmt.where(ComicIssue.issue_number.ilike(f"%{issue_number.strip()}%"))
        if publisher and publisher.strip():
            stmt = stmt.where(ComicIssue.publisher.ilike(f"%{publisher.strip()}%"))
        if imprint and imprint.strip():
            stmt = stmt.where(ComicIssue.imprint.ilike(f"%{imprint.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(ComicIssue.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(ComicIssue.region.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(ComicIssue.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(func.extract("year", ComicIssue.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                self._normalized_barcode_expr(ComicIdentifier.value) == normalized
            )
        rows = list(
            (
                await self.db.execute(
                    stmt.join(ComicWork.issues, isouter=True).join(ComicIssue.identifiers, isouter=True)
                )
            )
            .scalars()
            .unique()
        )
        return [self._comic_search_result(work) for work in rows]

    def _comic_search_result(self, work: ComicWork, *, issue: ComicIssue | None = None) -> SearchResult:
        issues = sorted(
            work.issues or [],
            key=lambda row: (
                row.publication_date is None,
                row.publication_date or date.max,
                row.issue_number is None,
                row.issue_number or "",
                str(row.id),
            ),
        )
        primary = issue or (issues[0] if issues else None)
        creators: list[dict[str, Any]] = []
        if primary is not None:
            for row in primary.contributions or []:
                if row.person is None:
                    continue
                creators.append({"name": row.person.name, "role": row.role})
        return SearchResult(
            id=work.id,
            kind=ItemKind.comic,
            title=work.title,
            item_number=primary.issue_number if primary is not None else None,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            release_date=primary.release_date if primary is not None else None,
            release_year=primary.release_date.year if primary is not None and primary.release_date else None,
            barcode=next(
                (
                    identifier.value
                    for identifier in (primary.identifiers or [])
                    if identifier.identifier_type in {"upc", "ean", "isbn10", "isbn13", "provider_item_id"}
                ),
                None,
            )
            if primary is not None
            else None,
            variant=primary.display_title if primary is not None else None,
            series_title=work.title,
            volume_name=work.title,
            creators=creators or None,
            characters=[
                row.character.name
                for row in (primary.character_appearances or [])
                if row.character is not None and row.character.name
            ]
            if primary is not None
            else None,
            story_arcs=[
                row.story_arc.name
                for row in (primary.story_arc_memberships or [])
                if row.story_arc is not None and row.story_arc.name
            ]
            if primary is not None
            else None,
            page_count=primary.page_count if primary is not None else None,
            cover_price_cents=primary.cover_price_cents if primary is not None else None,
            currency=primary.currency if primary is not None else None,
            country=primary.region if primary is not None else None,
            release_status=primary.release_status if primary is not None else None,
            language=primary.language if primary is not None else None,
            imprint=primary.imprint if primary is not None else None,
        )

    async def _search_book_works(
        self,
        *,
        query: str | None,
        series: str | None,
        publisher: str | None,
        imprint: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(BookWork)
            .options(
                selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                    BookContribution.person
                ),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
            )
            .order_by(BookWork.sort_title.asc().nullslast(), BookWork.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    BookWork.title.ilike(pattern),
                    BookWork.subtitle.ilike(pattern),
                    BookEdition.display_title.ilike(pattern),
                    BookEdition.edition_statement.ilike(pattern),
                    BookEdition.publisher.ilike(pattern),
                    BookEdition.imprint.ilike(pattern),
                )
            )
        if series and series.strip():
            stmt = stmt.where(BookWork.title.ilike(f"%{series.strip()}%"))
        if publisher and publisher.strip():
            stmt = stmt.where(BookEdition.publisher.ilike(f"%{publisher.strip()}%"))
        if imprint and imprint.strip():
            stmt = stmt.where(BookEdition.imprint.ilike(f"%{imprint.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(BookWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(BookEdition.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(BookEdition.region.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(BookEdition.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(BookEdition.edition_statement.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(BookEdition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(func.extract("year", BookEdition.publication_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(BookIdentifier.value) == normalized,
                    self._normalized_barcode_expr(BookIdentifier.normalized_value) == normalized,
                )
            )
        rows = list(
            (
                await self.db.execute(
                    stmt.join(BookWork.editions, isouter=True).join(BookEdition.identifiers, isouter=True)
                )
            )
            .scalars()
            .unique()
        )
        return [self._book_search_result(work) for work in rows]

    def _book_search_result(self, work: BookWork, *, edition: BookEdition | None = None) -> SearchResult:
        editions = sorted(
            work.editions or [],
            key=lambda row: (
                row.publication_date is None,
                row.publication_date or date.max,
                str(row.id),
            ),
        )
        primary = edition or (editions[0] if editions else None)
        creators: list[dict[str, Any]] = []
        if primary is not None:
            for row in primary.contributions or []:
                if row.person is None:
                    continue
                creators.append({"name": row.person.name, "role": row.role})
        return SearchResult(
            id=work.id,
            kind=ItemKind.book,
            title=work.title,
            item_number=primary.display_title if primary is not None else None,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            edition_title=primary.display_title if primary is not None else None,
            physical_format=primary.format if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            release_date=primary.publication_date if primary is not None else None,
            release_year=primary.publication_date.year if primary is not None and primary.publication_date else None,
            barcode=next((identifier.value for identifier in (primary.identifiers or []) if identifier.value), None)
            if primary is not None
            else None,
            variant=primary.binding if primary is not None else None,
            series_title=work.title,
            volume_name=work.title,
            creators=creators or None,
            page_count=primary.page_count if primary is not None else None,
            country=primary.region if primary is not None else None,
            release_status=primary.release_status if primary is not None else None,
            language=primary.language if primary is not None else None,
            age_rating=primary.age_rating if primary is not None else None,
            imprint=primary.imprint if primary is not None else None,
            subtitle=primary.edition_statement if primary is not None else None,
        )

    async def _book_work_by_barcode(self, barcode: str) -> tuple[BookWork, BookEdition | None] | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        row = (
            await self.db.execute(
                select(BookWork, BookEdition)
                .join(BookWork.editions)
                .join(BookEdition.identifiers)
                .where(
                    or_(
                        self._normalized_barcode_expr(BookIdentifier.value) == normalized,
                        self._normalized_barcode_expr(BookIdentifier.normalized_value) == normalized,
                    )
                )
                .options(
                    selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                        BookContribution.person
                    ),
                    selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    async def _search_movie_works(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(MovieWork)
            .options(
                selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                selectinload(MovieWork.releases).selectinload(MovieRelease.media),
                selectinload(MovieWork.identifiers),
            )
            .order_by(MovieWork.sort_title.asc().nullslast(), MovieWork.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    MovieWork.title.ilike(pattern),
                    MovieWork.subtitle.ilike(pattern),
                    MovieRelease.distributor.ilike(pattern),
                    MovieRelease.publisher.ilike(pattern),
                    MovieRelease.format.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(or_(MovieRelease.publisher.ilike(f"%{publisher.strip()}%"), MovieRelease.distributor.ilike(f"%{publisher.strip()}%")))
        if subtitle and subtitle.strip():
            stmt = stmt.where(MovieWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(or_(MovieRelease.language_audio.any(language.strip()), MovieRelease.language_subtitles.any(language.strip())))
        if country and country.strip():
            stmt = stmt.where(MovieRelease.region_code.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(MovieWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(or_(MovieRelease.sku.ilike(f"%{catalog_number.strip()}%"), MovieRelease.barcode.ilike(f"%{catalog_number.strip()}%")))
        if release_status and release_status.strip():
            stmt = stmt.where(MovieRelease.release_type.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(func.extract("year", MovieRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(MovieWorkIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MovieRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MovieRelease.sku) == normalized,
                )
            )
        rows = list(
            (
                await self.db.execute(
                    stmt.join(MovieWork.releases, isouter=True).join(MovieWork.identifiers, isouter=True)
                )
            )
            .scalars()
            .unique()
        )
        return [self._movie_search_result(work) for work in rows]

    def _movie_search_result(self, work: MovieWork, *, release: MovieRelease | None = None) -> SearchResult:
        releases = sorted(
            work.releases or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date or date.max,
                str(row.id),
            ),
        )
        primary = release or (releases[0] if releases else None)
        return SearchResult(
            id=work.id,
            kind=ItemKind.movie,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else work.poster_image_url,
            thumbnail_image_url=None,
            edition_title=primary.format if primary is not None else None,
            physical_format=primary.format if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            release_date=primary.release_date if primary is not None else work.original_release_date,
            release_year=(primary.release_date or work.original_release_date).year
            if (primary is not None and primary.release_date is not None) or work.original_release_date is not None
            else None,
            barcode=primary.barcode if primary is not None and primary.barcode else primary.sku if primary is not None else None,
            release_status=primary.release_type if primary is not None else work.status,
            language=next(iter(primary.language_audio), None) if primary is not None and primary.language_audio else None,
            age_rating=work.age_rating,
            creators=[
                {"name": row.person.name, "role": row.role}
                for row in sorted(
                    work.contributions or [],
                    key=lambda c: (
                        c.sequence is None,
                        c.sequence or 0,
                        c.role.casefold(),
                        str(c.person_id),
                    ),
                )
                if row.person is not None
            ]
            or None,
            catalog_number=primary.sku if primary is not None else None,
            country=primary.region_code if primary is not None else None,
        )

    async def _movie_work_by_barcode(self, barcode: str) -> tuple[MovieWork, MovieRelease | None] | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        row = (
            await self.db.execute(
                select(MovieWork, MovieRelease)
                .join(MovieWork.releases, isouter=True)
                .join(MovieWork.identifiers, isouter=True)
                .where(
                    or_(
                        self._normalized_barcode_expr(MovieWorkIdentifier.value) == normalized,
                        self._normalized_barcode_expr(MovieRelease.barcode) == normalized,
                        self._normalized_barcode_expr(MovieRelease.sku) == normalized,
                    )
                )
                .options(
                    selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                    selectinload(MovieWork.releases).selectinload(MovieRelease.media),
                    selectinload(MovieWork.identifiers),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    async def _search_tv_releases(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(TVRelease)
            .options(
                selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
                selectinload(TVRelease.media),
                selectinload(TVRelease.identifiers),
            )
            .order_by(TVRelease.sort_title.asc().nullslast(), TVRelease.title.asc())
            .limit(limit)
        )
        pattern = f"%{query.strip()}%" if query and query.strip() else None
        if pattern:
            stmt = stmt.where(
                or_(
                    TVRelease.title.ilike(pattern),
                    TVRelease.description.ilike(pattern),
                    TVRelease.publisher.ilike(pattern),
                    TVRelease.sku.ilike(pattern),
                    TVRelease.content_rating.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(TVRelease.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(TVRelease.description.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(
                or_(
                    TVRelease.language_audio.any(language.strip()),
                    TVRelease.language_subtitles.any(language.strip()),
                )
            )
        if country and country.strip():
            stmt = stmt.where(TVRelease.region_code.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(TVRelease.content_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(TVRelease.sku.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(TVRelease.format.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(func.extract("year", TVRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.where(
                or_(
                    self._normalized_barcode_expr(TVReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(TVRelease.sku) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt.join(TVRelease.identifiers, isouter=True))).scalars().unique())
        return [self._tv_search_result(release) for release in rows]

    def _tv_search_result(self, release: TVRelease) -> SearchResult:
        return SearchResult(
            id=release.id,
            kind=ItemKind.tv,
            title=release.title,
            synopsis=release.description,
            cover_image_url=release.cover_image_url,
            physical_format=release.format,
            publisher=release.publisher,
            release_date=release.release_date,
            release_year=release.release_date.year if release.release_date else None,
            barcode=next((identifier.value for identifier in release.identifiers or [] if identifier.value), release.sku),
            catalog_number=release.sku,
            country=release.region_code,
            age_rating=release.content_rating,
            language=(release.language_audio or [None])[0],
            release_status=release.format,
        )

    def _anime_search_result(self, series: AnimeSeries) -> SearchResult:
        episodes = sorted(
            series.episodes or [],
            key=lambda row: (
                row.episode_number is None,
                row.episode_number or 0,
                row.air_date is None,
                row.air_date or date.max,
                str(row.id),
            ),
        )
        primary = episodes[0] if episodes else None
        return SearchResult(
            id=series.id,
            kind=ItemKind.anime,
            title=series.title,
            synopsis=series.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            release_date=series.original_air_date or (primary.air_date if primary is not None else None),
            release_year=(
                (series.original_air_date or primary.air_date).year
                if series.original_air_date or (primary is not None and primary.air_date is not None)
                else None
            ),
            release_status=series.status,
            language=series.original_language,
            item_number=primary.episode_title if primary is not None else None,
            episode_count=series.episode_count,
            series_title=series.title,
        )

    async def _anime_series_by_barcode(self, barcode: str) -> AnimeSeries | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(AnimeSeries)
            .join(AnimeSeries.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(AnimeIdentifier.value) == normalized,
                    self._normalized_barcode_expr(AnimeIdentifier.normalized_value) == normalized,
                )
            )
            .options(
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.identifiers),
                selectinload(AnimeSeries.character_appearances).selectinload(
                    AnimeCharacterAppearance.character
                ),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_anime_series(
        self,
        *,
        query: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(AnimeSeries)
            .options(
                selectinload(AnimeSeries.episodes),
                selectinload(AnimeSeries.contributions).selectinload(AnimeContribution.person),
                selectinload(AnimeSeries.identifiers),
                selectinload(AnimeSeries.character_appearances).selectinload(
                    AnimeCharacterAppearance.character
                ),
            )
            .order_by(AnimeSeries.sort_title.asc().nullslast(), AnimeSeries.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(AnimeSeries.episodes, isouter=True).where(
                or_(
                    AnimeSeries.title.ilike(pattern),
                    AnimeSeries.description.ilike(pattern),
                    AnimeSeries.status.ilike(pattern),
                    AnimeSeries.anime_type.ilike(pattern),
                    AnimeEpisode.episode_title.ilike(pattern),
                )
            )
        if language and language.strip():
            stmt = stmt.where(AnimeSeries.original_language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(AnimeSeries.status.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(AnimeSeries.status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", AnimeSeries.original_air_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(AnimeSeries.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(AnimeIdentifier.value) == normalized,
                    self._normalized_barcode_expr(AnimeIdentifier.normalized_value) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._anime_search_result(series) for series in rows]

    def _music_search_result(self, release: MusicRelease) -> SearchResult:
        media = sorted(
            release.media or [],
            key=lambda row: (
                row.media_number is None,
                row.media_number or 0,
                str(row.id),
            ),
        )
        primary = media[0] if media else None
        tracks = []
        if primary is not None:
            for track in sorted(
                primary.tracks or [],
                key=lambda row: (row.position.casefold(), str(row.id)),
            ):
                tracks.append(
                    {
                        "id": track.id,
                        "media_id": track.media_id,
                        "position": track.position,
                        "title": track.title,
                        "duration_ms": track.duration_ms,
                        "instrument": track.instrument,
                        "composition": track.composition,
                    }
                )
        return SearchResult(
            id=release.id,
            kind=ItemKind.music,
            title=release.title,
            synopsis=release.extras,
            cover_image_url=release.cover_image_url,
            release_date=release.release_date,
            release_year=release.release_date.year if release.release_date else None,
            barcode=release.barcode,
            catalog_number=release.catalog_number,
            publisher=release.publisher,
            country=release.country_code,
            language=release.language,
            release_status=release.release_status,
            track_count=release.track_count,
            tracks=tracks or None,
            item_number=primary.title if primary is not None else None,
            edition_title=primary.title if primary is not None else None,
        )

    async def _music_release_by_barcode(self, barcode: str) -> MusicRelease | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(MusicRelease)
            .join(MusicRelease.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(MusicReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MusicReleaseIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(MusicRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MusicRelease.catalog_number) == normalized,
                )
            )
            .options(
                selectinload(MusicRelease.media).selectinload(MusicMedia.tracks),
                selectinload(MusicRelease.contributions).selectinload(MusicReleaseContribution.person),
                selectinload(MusicRelease.identifiers),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_music_releases(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        catalog_number: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(MusicRelease)
            .options(
                selectinload(MusicRelease.media).selectinload(MusicMedia.tracks),
                selectinload(MusicRelease.contributions).selectinload(MusicReleaseContribution.person),
                selectinload(MusicRelease.identifiers),
            )
            .order_by(MusicRelease.sort_title.asc().nullslast(), MusicRelease.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(MusicRelease.media, isouter=True).where(
                or_(
                    MusicRelease.title.ilike(pattern),
                    MusicRelease.subtitle.ilike(pattern),
                    MusicRelease.publisher.ilike(pattern),
                    MusicRelease.studio.ilike(pattern),
                    MusicMedia.title.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(or_(MusicRelease.publisher.ilike(f"%{publisher.strip()}%"), MusicRelease.studio.ilike(f"%{publisher.strip()}%")))
        if subtitle and subtitle.strip():
            stmt = stmt.where(MusicRelease.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(MusicRelease.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(MusicRelease.country_code.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(MusicRelease.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", MusicRelease.release_date) == year)
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(MusicRelease.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(MusicRelease.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(MusicReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MusicReleaseIdentifier.normalized_value) == normalized,
                    self._normalized_barcode_expr(MusicRelease.barcode) == normalized,
                    self._normalized_barcode_expr(MusicRelease.catalog_number) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._music_search_result(release) for release in rows]

    def _boardgame_search_result(self, work: BoardGameWork) -> SearchResult:
        editions = sorted(
            work.editions or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date or date.max,
                str(row.id),
            ),
        )
        primary = editions[0] if editions else None
        return SearchResult(
            id=work.id,
            kind=ItemKind.boardgame,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else work.cover_image_url,
            release_date=primary.release_date if primary is not None else None,
            release_year=primary.release_date.year if primary is not None and primary.release_date else None,
            barcode=primary.barcode if primary is not None else None,
            catalog_number=primary.catalog_number if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            country=primary.country if primary is not None else None,
            language=primary.language if primary is not None else None,
            age_rating=primary.age_rating if primary is not None else work.age_rating,
            release_status=primary.release_status if primary is not None else None,
            item_number=primary.edition_title if primary is not None else None,
            edition_title=primary.edition_title if primary is not None else None,
        )

    async def _boardgame_work_by_barcode(self, barcode: str) -> BoardGameWork | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(BoardGameWork)
            .join(BoardGameWork.editions, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(BoardGameEdition.barcode) == normalized,
                    self._normalized_barcode_expr(BoardGameEdition.catalog_number) == normalized,
                )
            )
            .options(selectinload(BoardGameWork.editions))
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_boardgame_works(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(BoardGameWork)
            .options(selectinload(BoardGameWork.editions))
            .order_by(BoardGameWork.sort_title.asc().nullslast(), BoardGameWork.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(BoardGameWork.editions, isouter=True).where(
                or_(
                    BoardGameWork.title.ilike(pattern),
                    BoardGameWork.subtitle.ilike(pattern),
                    BoardGameEdition.publisher.ilike(pattern),
                    BoardGameEdition.catalog_number.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(BoardGameEdition.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(BoardGameWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(BoardGameEdition.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(BoardGameEdition.country.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(BoardGameEdition.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(BoardGameEdition.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(BoardGameEdition.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", BoardGameEdition.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(BoardGameWork.editions, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(BoardGameEdition.barcode) == normalized,
                    self._normalized_barcode_expr(BoardGameEdition.catalog_number) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._boardgame_search_result(work) for work in rows]

    def _game_search_result(self, work: GameWork) -> SearchResult:
        releases = sorted(
            work.releases or [],
            key=lambda row: (
                row.release_date is None,
                row.release_date or date.max,
                str(row.id),
            ),
        )
        primary = releases[0] if releases else None
        return SearchResult(
            id=work.id,
            kind=ItemKind.game,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else work.cover_image_url,
            release_date=primary.release_date if primary is not None else work.release_date,
            release_year=(primary.release_date or work.release_date).year
            if primary is not None and (primary.release_date or work.release_date)
            else (work.release_date.year if work.release_date else None),
            barcode=primary.barcode if primary is not None else None,
            catalog_number=primary.catalog_number if primary is not None else None,
            publisher=primary.publisher if primary is not None else None,
            country=primary.region_code if primary is not None else None,
            language=primary.language if primary is not None else None,
            age_rating=work.age_rating,
            release_status=primary.release_status if primary is not None else None,
            item_number=primary.release_title if primary is not None else None,
            edition_title=primary.release_title if primary is not None else None,
        )

    async def _game_work_by_barcode(self, barcode: str) -> GameWork | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(GameWork)
            .join(GameWork.releases, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(GameRelease.barcode) == normalized,
                    self._normalized_barcode_expr(GameRelease.catalog_number) == normalized,
                )
            )
            .options(selectinload(GameWork.releases))
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_game_works(
        self,
        *,
        query: str | None,
        publisher: str | None,
        subtitle: str | None,
        language: str | None,
        country: str | None,
        age_rating: str | None,
        catalog_number: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(GameWork)
            .options(selectinload(GameWork.releases))
            .order_by(GameWork.sort_title.asc().nullslast(), GameWork.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(GameWork.releases, isouter=True).where(
                or_(
                    GameWork.title.ilike(pattern),
                    GameWork.subtitle.ilike(pattern),
                    GameRelease.publisher.ilike(pattern),
                    GameRelease.format.ilike(pattern),
                )
            )
        if publisher and publisher.strip():
            stmt = stmt.where(GameRelease.publisher.ilike(f"%{publisher.strip()}%"))
        if subtitle and subtitle.strip():
            stmt = stmt.where(GameWork.subtitle.ilike(f"%{subtitle.strip()}%"))
        if language and language.strip():
            stmt = stmt.where(GameRelease.language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(GameRelease.region_code.ilike(f"%{country.strip()}%"))
        if age_rating and age_rating.strip():
            stmt = stmt.where(GameWork.age_rating.ilike(f"%{age_rating.strip()}%"))
        if catalog_number and catalog_number.strip():
            stmt = stmt.where(GameRelease.catalog_number.ilike(f"%{catalog_number.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(GameRelease.release_status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", GameRelease.release_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(GameWork.releases, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(GameRelease.barcode) == normalized,
                    self._normalized_barcode_expr(GameRelease.catalog_number) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._game_search_result(work) for work in rows]

    def _manga_search_result(self, work: MangaWork) -> SearchResult:
        chapters = sorted(
            work.chapters or [],
            key=lambda row: (
                row.chapter_number is None,
                row.chapter_number or 0,
                row.publication_date is None,
                row.publication_date or date.max,
                str(row.id),
            ),
        )
        primary = chapters[0] if chapters else None
        return SearchResult(
            id=work.id,
            kind=ItemKind.manga,
            title=work.title,
            synopsis=work.description,
            cover_image_url=primary.cover_image_url if primary is not None else None,
            release_date=work.original_publication_date or (primary.publication_date if primary is not None else None),
            release_year=(
                (work.original_publication_date or primary.publication_date).year
                if work.original_publication_date or (primary is not None and primary.publication_date is not None)
                else None
            ),
            release_status=work.status,
            item_number=primary.chapter_title if primary is not None else None,
            series_title=work.title,
            volume_name=work.title,
            page_count=primary.page_count if primary is not None else None,
        )

    async def _manga_work_by_barcode(self, barcode: str) -> MangaWork | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(MangaWork)
            .join(MangaWork.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(MangaIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MangaIdentifier.normalized_value) == normalized,
                )
            )
            .options(
                selectinload(MangaWork.chapters),
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.identifiers),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
                selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _search_manga_works(
        self,
        *,
        query: str | None,
        language: str | None,
        country: str | None,
        release_status: str | None,
        year: int | None,
        barcode: str | None,
        limit: int,
    ) -> list[SearchResult]:
        stmt = (
            select(MangaWork)
            .options(
                selectinload(MangaWork.chapters),
                selectinload(MangaWork.contributions).selectinload(MangaContribution.person),
                selectinload(MangaWork.identifiers),
                selectinload(MangaWork.character_appearances).selectinload(MangaCharacterAppearance.character),
                selectinload(MangaWork.series_memberships).selectinload(MangaSeriesMembership.series),
            )
            .order_by(MangaWork.sort_title.asc().nullslast(), MangaWork.title.asc())
            .limit(limit)
        )
        if query and query.strip():
            pattern = f"%{query.strip()}%"
            stmt = stmt.join(MangaWork.chapters, isouter=True).where(
                or_(
                    MangaWork.title.ilike(pattern),
                    MangaWork.subtitle.ilike(pattern),
                    MangaChapter.chapter_title.ilike(pattern),
                )
            )
        if language and language.strip():
            stmt = stmt.where(MangaWork.original_language.ilike(f"%{language.strip()}%"))
        if country and country.strip():
            stmt = stmt.where(MangaWork.status.ilike(f"%{country.strip()}%"))
        if release_status and release_status.strip():
            stmt = stmt.where(MangaWork.status.ilike(f"%{release_status.strip()}%"))
        if year is not None:
            stmt = stmt.where(extract("year", MangaWork.original_publication_date) == year)
        if barcode and barcode.strip():
            normalized = self._normalized_barcode(barcode)
            stmt = stmt.join(MangaWork.identifiers, isouter=True).where(
                or_(
                    self._normalized_barcode_expr(MangaIdentifier.value) == normalized,
                    self._normalized_barcode_expr(MangaIdentifier.normalized_value) == normalized,
                )
            )
        rows = list((await self.db.execute(stmt)).scalars().unique())
        return [self._manga_search_result(work) for work in rows]

    async def _tv_release_by_barcode(self, barcode: str) -> TVRelease | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        stmt = (
            select(TVRelease)
            .options(
                selectinload(TVRelease.contributions).selectinload(TVReleaseContribution.person),
                selectinload(TVRelease.media),
                selectinload(TVRelease.identifiers),
            )
            .join(TVRelease.identifiers, isouter=True)
            .where(
                or_(
                    self._normalized_barcode_expr(TVReleaseIdentifier.value) == normalized,
                    self._normalized_barcode_expr(TVRelease.sku) == normalized,
                )
            )
            .limit(1)
        )
        return await self.db.scalar(stmt)

    async def _comic_work_by_barcode(self, barcode: str) -> tuple[ComicWork, ComicIssue | None] | None:
        normalized = self._normalized_barcode(barcode)
        if not normalized:
            return None
        row = (
            await self.db.execute(
                select(ComicWork, ComicIssue)
                .join(ComicWork.issues)
                .join(ComicIssue.identifiers)
                .where(self._normalized_barcode_expr(ComicIdentifier.value) == normalized)
                .options(
                    selectinload(ComicWork.issues)
                    .selectinload(ComicIssue.contributions)
                    .selectinload(ComicContribution.person),
                    selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                    selectinload(ComicWork.issues)
                    .selectinload(ComicIssue.character_appearances)
                    .selectinload(ComicCharacterAppearance.character),
                    selectinload(ComicWork.issues)
                    .selectinload(ComicIssue.story_arc_memberships)
                    .selectinload(ComicStoryArcMembership.story_arc),
                )
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return row[0], row[1]

    def _normalized_barcode_expr(self, column: Any) -> Any:
        return func.replace(func.replace(func.replace(column, "-", ""), " ", ""), ".", "")

    def _normalized_barcode(self, value: str) -> str:
        return value.strip().replace("-", "").replace(" ", "").replace(".", "")

    async def barcode_provider_search(
        self,
        barcode: str,
        kind: ItemKind | None = None,
    ) -> list[ProviderSearchResult]:
        """Search external providers for a barcode/UPC/ISBN."""
        return await _barcode_provider_search(self, barcode, kind)

    async def search_provider(
        self,
        provider_name: ExternalProvider,
        query: str | None,
        kind: ItemKind | None = None,
        *,
        series: str | None = None,
        issue_number: str | None = None,
        year: int | None = None,
    ) -> list[ProviderSearchResultResponse]:
        return await _search_provider(self, provider_name, query, kind, series=series, issue_number=issue_number, year=year)

    async def search_default_provider(
        self,
        query: str | None,
        kind: ItemKind,
        *,
        series: str | None = None,
        issue_number: str | None = None,
        year: int | None = None,
    ) -> list[ProviderSearchResultResponse]:
        return await _search_default_provider(self, query, kind, series=series, issue_number=issue_number, year=year)

    async def _search_provider_live(
        self,
        provider_name: ExternalProvider,
        provider: MetadataProvider,
        query: str,
        kind: ItemKind | None,
    ) -> list[ProviderSearchResult]:
        await self._raise_if_provider_on_backoff(provider_name)
        attempts = self._provider_search_attempts(provider_name)
        last_error: ApiHTTPException | None = None
        for attempt in range(attempts):
            try:
                return await provider.search(query, kind)
            except ApiHTTPException as exc:
                last_error = exc
                if self._should_backoff_provider_search(exc):
                    await self._record_provider_search_backoff(provider_name, exc)
                if attempt >= attempts - 1 or not self._should_retry_provider_search(exc):
                    raise
                await asyncio.sleep(self._provider_search_retry_delay(exc, attempt))
        raise last_error or ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="provider_search_failed",
            detail=f"Provider '{provider_name.value}' search failed",
        )

    def _provider_search_attempts(self, provider_name: ExternalProvider) -> int:
        if provider_name.value in _PROVIDER_INTERNAL_RETRY_NAMES:
            return 1
        return max(1, self.settings.provider_search_retry_attempts + 1)

    def _provider_search_cache_key(
        self,
        provider_name: ExternalProvider | str,
        query: str,
        kind: ItemKind | None,
    ) -> tuple[str, str, str]:
        normalized_query = " ".join(query.split()).casefold()
        return self._provider_search_cache_namespace(provider_name), kind.value if kind else "*", normalized_query

    def _provider_search_cache_namespace(
        self,
        provider_name: ExternalProvider | str,
    ) -> str:
        return provider_name.value if isinstance(provider_name, ExternalProvider) else str(provider_name)

    def _provider_search_query(
        self,
        query: str | None,
        kind: ItemKind | None,
        *,
        series: str | None,
        issue_number: str | None,
        year: int | None,
    ) -> str:
        base_query = self._clean_provider_query_part(query)
        if kind == ItemKind.comic:
            series_query = self._clean_provider_query_part(series)
            issue_query = self._clean_issue_number(issue_number)
            if series_query or issue_query:
                parts = [series_query or base_query]
                if issue_query:
                    parts.append(f"#{issue_query}")
                provider_query = " ".join(part for part in parts if part)
            else:
                provider_query = base_query
            if year is not None and provider_query and str(year) not in provider_query:
                provider_query = f"{provider_query} ({year})"
            return self._clean_provider_query_part(provider_query)
        if kind == ItemKind.music:
            series_query = self._clean_provider_query_part(series)
            release_query = self._clean_provider_query_part(issue_number)
            if not release_query:
                release_query = base_query
            if not series_query and year is None:
                return base_query
            parts: list[str] = []
            if series_query:
                parts.append(f'artist:"{self._escape_provider_query_phrase(series_query)}"')
            if release_query:
                parts.append(f'release:"{self._escape_provider_query_phrase(release_query)}"')
            if year is not None:
                parts.append(f'date:{year}')
            return " AND ".join(parts)
        return base_query

    def _clean_provider_query_part(self, value: str | None) -> str:
        return " ".join(str(value or "").split())

    def _escape_provider_query_phrase(self, value: str) -> str:
        return value.replace('"', r'\"')

    def _clean_issue_number(self, value: str | None) -> str:
        text = self._clean_provider_query_part(value)
        return re.sub(r"^#+\s*", "", text)

    async def _cached_provider_search_results(
        self,
        key: tuple[str, str, str],
    ) -> list[ProviderSearchResult] | None:
        return await self.provider_search_state.cached(key)

    async def _store_provider_search_results(
        self,
        key: tuple[str, str, str],
        results: list[ProviderSearchResult],
    ) -> None:
        await self.provider_search_state.store(key, results)

    async def _raise_if_provider_on_backoff(self, provider_name: ExternalProvider) -> None:
        await self.provider_search_state.raise_if_backoff(provider_name)

    async def _record_provider_search_backoff(
        self,
        provider_name: ExternalProvider,
        exc: ApiHTTPException,
    ) -> None:
        seconds = (
            self._provider_search_retry_after(exc) or self.settings.provider_search_backoff_seconds
        )
        if seconds <= 0:
            return
        provider = self.providers.maybe_get(provider_name)
        provider_label = provider.capabilities.display_name if provider else provider_name.value
        await self.provider_search_state.record_backoff(
            provider_name,
            seconds=seconds,
            provider_label=provider_label,
            reason=self._provider_search_error_reason(exc),
        )

    def _should_retry_provider_search(self, exc: ApiHTTPException) -> bool:
        return self._provider_search_status(exc) in {401, 429, 500, 502, 503, 504}

    def _should_backoff_provider_search(self, exc: ApiHTTPException) -> bool:
        return self._provider_search_status(exc) in {401, 429, 500, 502, 503, 504}

    def _provider_search_retry_delay(self, exc: ApiHTTPException, attempt: int) -> float:
        retry_after = self._provider_search_retry_after(exc)
        if retry_after is not None:
            return min(float(retry_after), 3.0)
        base = self.settings.provider_search_retry_base_delay_seconds
        return min(base * (2**attempt), 3.0)

    def _provider_search_retry_after(self, exc: ApiHTTPException) -> int | None:
        retry_after = (exc.headers or {}).get("Retry-After")
        if retry_after is None:
            return None
        try:
            value = int(float(retry_after))
        except ValueError:
            return None
        return value if value > 0 else None

    def _provider_search_status(self, exc: ApiHTTPException) -> int:
        detail = exc.detail
        if isinstance(detail, str):
            match = _UPSTREAM_HTTP_STATUS_RE.search(detail)
            if match:
                return int(match.group("status"))
        return exc.status_code

    def _provider_search_error_reason(self, exc: ApiHTTPException) -> str:
        upstream_status = self._provider_search_status(exc)
        if upstream_status != exc.status_code:
            return f"HTTP {upstream_status}"
        return f"HTTP {exc.status_code}"

    async def mirror_provider_image_url(
        self,
        source_url: str | None,
        *,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
        cache_only: bool = False,
    ) -> str | None:
        return await _mirror_provider_image_url(self, source_url, provider_name=provider_name, provider_item_id=provider_item_id, cache_only=cache_only)

    async def mirror_provider_image_bytes(
        self,
        image_bytes: bytes | None,
        *,
        source_url: str | None,
        provider_name: str | ExternalProvider,
        provider_item_id: str | None,
    ) -> str | None:
        return await _mirror_provider_image_bytes(self, image_bytes, source_url=source_url, provider_name=provider_name, provider_item_id=provider_item_id)

    async def _with_stable_provider_image_urls(
        self,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        stable_results: list[ProviderSearchResult] = []
        for result in results:
            mirrored_url = await self.mirror_provider_image_url(
                result.image_url,
                provider_name=result.provider,
                provider_item_id=result.provider_item_id,
                cache_only=True,
            )
            stable_results.append(
                replace(result, image_url=mirrored_url) if mirrored_url else result
            )
        return stable_results

    def _can_mirror_provider_image(
        self,
        provider_name: str | ExternalProvider,
        source_url: str | None,
    ) -> bool:
        if not self.settings.mirror_provider_images:
            return False
        if not self._is_external_image_url(source_url):
            return False
        provider = self._provider_for_name(provider_name)
        if provider is None:
            return False
        if self.settings.mirror_provider_images_allow_restricted:
            return True
        return provider.capabilities.allows_image_mirroring

    def _provider_for_name(
        self,
        provider_name: str | ExternalProvider,
    ) -> MetadataProvider | None:
        try:
            provider_enum = (
                provider_name
                if isinstance(provider_name, ExternalProvider)
                else ExternalProvider(str(provider_name))
            )
        except ValueError:
            return None
        return self.providers.maybe_get(provider_enum)

    def _provider_value(self, provider_name: str | ExternalProvider) -> str:
        return (
            provider_name.value
            if isinstance(provider_name, ExternalProvider)
            else str(provider_name)
        )

    def _is_external_image_url(self, value: str | None) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def _search_provider_fallback(
        self,
        provider_name: ExternalProvider,
        query: str,
        kind: ItemKind | None,
        original_error: ApiHTTPException,
    ):
        if not self.settings.provider_search_comicvine_fallback_enabled:
            return None
        if provider_name != ExternalProvider.gcd:
            return None
        if not self._should_backoff_provider_search(original_error):
            return None
        fallback = self.providers.maybe_get(ExternalProvider.comicvine)
        if fallback is None or not fallback.is_configured:
            return None
        if kind is not None and not fallback.capabilities.supports_kind(kind):
            return None
        if isinstance(fallback, ComicVineProvider):
            exact_results = await self._search_gcd_comicvine_exact_fallback(
                fallback,
                query,
                kind,
                requested_provider=provider_name,
            )
            if exact_results:
                return exact_results
        try:
            results = await fallback.search(query, kind)
        except Exception:
            logger.warning(
                "provider_search_fallback_failed provider=%s fallback=%s code=%s",
                provider_name.value,
                fallback.name,
                original_error.code,
                exc_info=True,
            )
            return None
        if not results:
            return None
        results = [
            self._with_provider_fallback_notice(
                result,
                requested_provider=provider_name,
                fallback_provider=ExternalProvider.comicvine,
            )
            for result in results
        ]
        logger.info(
            "provider_search_fallback_used provider=%s fallback=%s code=%s",
            provider_name.value,
            fallback.name,
            original_error.code,
        )
        return results

    async def _with_provider_search_enrichment(
        self,
        provider_name: ExternalProvider,
        query: str,
        kind: ItemKind | None,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        if not self.settings.provider_search_comicvine_fallback_enabled:
            return results
        if provider_name != ExternalProvider.gcd or not results:
            return results
        target_kind = kind or ItemKind.comic
        if target_kind != ItemKind.comic:
            return results
        if any(result.provider == ExternalProvider.comicvine.value for result in results):
            return results

        fallback = self.providers.maybe_get(ExternalProvider.comicvine)
        if (
            fallback is None
            or not fallback.is_configured
            or not fallback.capabilities.supports_kind(target_kind)
        ):
            return results

        plan = GCDProvider()._query_plan(query)
        if not plan.is_series_search:
            return results

        cache_key = self._provider_search_cache_key(
            ExternalProvider.comicvine,
            query,
            target_kind,
        )
        fallback_results = await self._cached_provider_search_results(cache_key)
        if fallback_results is None:
            try:
                fallback_results = await self._search_provider_live(
                    ExternalProvider.comicvine,
                    fallback,
                    query,
                    target_kind,
                )
            except Exception:
                logger.warning(
                    "provider_search_enrichment_failed provider=%s fallback=%s",
                    provider_name.value,
                    fallback.name,
                    exc_info=True,
                )
                return results
            await self._store_provider_search_results(cache_key, fallback_results)
        if not fallback_results:
            return results

        seen = {(result.provider, result.provider_item_id) for result in results}
        enriched = list(results)
        for result in fallback_results:
            key = (result.provider, result.provider_item_id)
            if key in seen:
                continue
            seen.add(key)
            enriched.append(result)
        return enriched

    async def _search_gcd_comicvine_exact_fallback(
        self,
        provider: ComicVineProvider,
        query: str,
        kind: ItemKind | None,
        *,
        requested_provider: ExternalProvider,
    ) -> list[ProviderSearchResult]:
        target_kind = kind or ItemKind.comic
        if target_kind != ItemKind.comic:
            return []
        plan = GCDProvider()._query_plan(query)
        if plan.is_series_search:
            return []
        for series_title, issue_number in plan.candidates[:3]:
            try:
                cover = await provider.find_issue_cover(
                    series_title=series_title,
                    issue_number=issue_number,
                )
            except Exception:
                logger.warning(
                    "provider_search_exact_cover_fallback_failed series=%s issue=%s",
                    series_title,
                    issue_number,
                    exc_info=True,
                )
                continue
            if cover is None:
                continue
            return [
                self._with_provider_fallback_notice(
                    ProviderSearchResult(
                        provider=provider.name,
                        provider_item_id=cover.provider_item_id,
                        title=f"{series_title.title()} #{issue_number}",
                        kind=target_kind,
                        image_url=cover.image_url,
                        candidate_type="issue",
                        series_title=series_title.title(),
                        issue_number=issue_number,
                        is_variant=False,
                    ),
                    requested_provider=requested_provider,
                    fallback_provider=ExternalProvider.comicvine,
                )
            ]
        return []

    async def _with_provider_search_credit_previews(
        self,
        _provider_name: ExternalProvider,
        results: list[ProviderSearchResult],
    ) -> list[ProviderSearchResult]:
        if not results:
            return results

        series_preview: dict[str, tuple[list[str], list[str]]] = {}
        for result in results:
            if result.candidate_type not in {"issue", "variant"}:
                continue
            if not result.character_preview and not result.story_arc_preview:
                continue
            series_key = self._preview_series_key(result.series_title or result.title)
            if not series_key:
                continue
            merged = self._merge_preview_lists(
                series_preview.get(series_key),
                result.character_preview,
                result.story_arc_preview,
            )
            if merged is not None:
                series_preview[series_key] = merged

        if not series_preview:
            return results

        changed = False
        final_results: list[ProviderSearchResult] = []
        for result in results:
            if (
                result.candidate_type == "series"
                and not result.character_preview
                and not result.story_arc_preview
            ):
                series_key = self._preview_series_key(result.series_title or result.title)
                series_data = series_preview.get(series_key or "")
                if series_data is not None:
                    chars, arcs = series_data
                    result = replace(
                        result,
                        character_preview=chars,
                        story_arc_preview=arcs,
                    )
                    changed = True
            final_results.append(result)

        return final_results if changed else results

    def _preview_series_key(self, value: str | None) -> str:
        if not value:
            return ""
        return re.sub(r"\s+", " ", value).strip().casefold()

    def _merge_preview_lists(
        self,
        existing: tuple[list[str], list[str]] | None,
        characters: list[str],
        arcs: list[str],
    ) -> tuple[list[str], list[str]] | None:
        if not characters and not arcs and existing is None:
            return None
        existing_characters = list(existing[0]) if existing else []
        existing_arcs = list(existing[1]) if existing else []
        merged_characters = self._merge_names(existing_characters, characters)
        merged_arcs = self._merge_names(existing_arcs, arcs)
        return merged_characters, merged_arcs

    def _merge_names(self, base: list[str], extra: list[str]) -> list[str]:
        merged = list(base)
        seen = {name.casefold() for name in merged}
        for name in extra:
            text = str(name or "").strip()
            if not text:
                continue
            key = text.casefold()
            if key in seen:
                continue
            seen.add(key)
            merged.append(text)
            if len(merged) >= 3:
                break
        return merged[:3]

    def _with_provider_fallback_notice(
        self,
        result: ProviderSearchResult,
        *,
        requested_provider: ExternalProvider,
        fallback_provider: ExternalProvider,
    ) -> ProviderSearchResult:
        notice = (
            f"{self._provider_display_name(fallback_provider)} fallback while "
            f"{self._provider_display_name(requested_provider)} is unavailable."
        )
        summary = notice if not result.summary else f"{notice} {result.summary}"
        return replace(result, summary=summary)

    def _provider_display_name(self, provider_name: ExternalProvider) -> str:
        provider = self.providers.maybe_get(provider_name)
        return provider.capabilities.display_name if provider else provider_name.value

    async def create_proposal(self, payload: MetadataProposalCreate) -> MetadataProposalResponse:
        return await _create_proposal(self, payload)

    def _search_result(
        self,
        item,
        cover_url: str | None,
        thumbnail_url: str | None,
        *,
        preferred_variant=None,
    ) -> SearchResult:
        publisher = _organization_name(item, "publisher")
        release_date = None
        release_year = None
        barcode = None
        edition_title = None
        physical_format_id = None
        physical_format_label = None
        variant_name = getattr(preferred_variant, "name", None)
        if preferred_variant is not None:
            barcode = preferred_variant.barcode or preferred_variant.isbn or preferred_variant.sku
            preferred_format = self._physical_format(
                preferred_variant.metadata_json,
                fallback_format=preferred_variant.variant_type,
                kind=item.kind,
            )
            if preferred_format is not None:
                physical_format_id = preferred_format.id
                physical_format_label = preferred_format.label
        for edition in item.editions:
            edition_title = edition_title or edition.title
            publisher = publisher or edition.publisher
            barcode = barcode or edition.upc or edition.isbn
            physical_format = self._physical_format(
                edition.metadata_json,
                fallback_format=edition.format,
                kind=item.kind,
            )
            if physical_format is not None:
                physical_format_id = physical_format_id or physical_format.id
                physical_format_label = physical_format_label or physical_format.label
                variant_name = variant_name or physical_format.label
            if edition.release_date is not None and release_date is None:
                release_date = edition.release_date
                release_year = edition.release_date.year
            primary = next((variant for variant in edition.variants if variant.is_primary), None)
            if primary is not None and variant_name is None:
                variant_name = primary.name
                barcode = barcode or primary.barcode or primary.isbn or primary.sku
                primary_format = self._physical_format(
                    primary.metadata_json,
                    fallback_format=primary.variant_type,
                    kind=item.kind,
                )
                if primary_format is not None:
                    physical_format_id = physical_format_id or primary_format.id
                    physical_format_label = physical_format_label or primary_format.label
            if (
                publisher is not None
                and release_date is not None
                and barcode is not None
                and variant_name is not None
                and (not is_video_item_kind(item.kind) or physical_format_label is not None)
            ):
                break
        metadata_json = getattr(item, "metadata_json", None)
        metadata = metadata_json if isinstance(metadata_json, dict) else {}
        series_title = getattr(item, "series_title", None) or metadata.get("series_title")
        volume_name = getattr(item, "volume_name", None) or metadata.get("volume_name")
        metadata = getattr(item, "metadata_json", None)
        typed_metadata = dict(metadata.get("normalized") or {}) if isinstance(metadata, dict) else {}
        track_count: int | None = (
            int(typed_metadata["track_count"])
            if isinstance(typed_metadata.get("track_count"), int)
            else None
        )
        tracks: list[dict] | None = (
            typed_metadata.get("tracks")
            if isinstance(typed_metadata.get("tracks"), list)
            else None
        )
        catalog_number: str | None = None
        creators: list[dict] | None = None
        characters: list[str] | None = None
        character_details: list[dict] | None = None
        story_arcs: list[str] | None = None
        platforms: list[str] | None = (
            [
                str(value).strip()
                for value in typed_metadata.get("platforms", [])
                if str(value).strip()
            ]
            if isinstance(typed_metadata.get("platforms"), list)
            else None
        )
        genres: list[str] | None = (
            [str(value).strip() for value in typed_metadata.get("genres", []) if str(value).strip()]
            if isinstance(typed_metadata.get("genres"), list)
            else None
        )
        page_count: int | None = getattr(item, "page_count", None)
        runtime_minutes: int | None = getattr(item, "runtime_minutes", None)
        cover_price_cents: int | None = None
        item_currency: str | None = None
        country: str | None = None
        release_status: str | None = None
        language: str | None = None
        age_rating: str | None = None
        imprint_val: str | None = _organization_name(item, "imprint")
        subtitle: str | None = None
        series_group: str | None = None
        bundle_titles: list[str] | None = None
        bundle_release_ids: list[str] | None = None
        creator_links = sorted(
            _loaded_rows(item, "creator_links"),
            key=lambda link: (
                getattr(link, "created_at", None) is None,
                getattr(link, "created_at", None),
                str(getattr(link, "id", "") or ""),
            ),
        )
        if creator_links:
            creators = [
                {
                    "name": link.person.name,
                    "role": link.role,
                    "api_detail_url": _model_text_or_metadata(link.person, "api_detail_url"),
                    "site_detail_url": _model_text_or_metadata(link.person, "site_detail_url"),
                    "image_url": _model_text_or_metadata(link.person, "image_url"),
                }
                for link in creator_links
                if getattr(link, "person", None) is not None and getattr(link.person, "name", None)
            ] or None
        character_links = sorted(
            _loaded_rows(item, "character_appearances"),
            key=lambda appearance: (
                str(getattr(appearance, "role", "") or "").casefold(),
                str(getattr(getattr(appearance, "character", None), "name", "") or "").casefold(),
            ),
        )
        if character_links:
            character_details = [
                {
                    "name": appearance.character.name,
                    "role": appearance.role,
                    "aliases": [
                        str(alias).strip()
                        for alias in (getattr(appearance.character, "aliases", None) or [])
                        if str(alias).strip()
                    ],
                    "description": getattr(appearance.character, "description", None),
                    "image_url": getattr(appearance.character, "image_url", None),
                    "first_appearance_item_id": getattr(
                        appearance.character,
                        "first_appearance_item_id",
                        None,
                    ),
                }
                for appearance in character_links
                if getattr(appearance, "character", None) is not None
                and getattr(appearance.character, "name", None)
            ] or None
            characters = [
                appearance.character.name
                for appearance in character_links
                if getattr(appearance, "character", None) is not None
                and getattr(appearance.character, "name", None)
            ] or None
        story_arc_links = sorted(
            _loaded_rows(item, "story_arc_items"),
            key=lambda link: (
                getattr(link, "ordinal", None) is None,
                getattr(link, "ordinal", None) or 0,
                str(getattr(getattr(link, "story_arc", None), "name", "") or "").casefold(),
            ),
        )
        if story_arc_links:
            story_arcs = [
                link.story_arc.name
                for link in story_arc_links
                if getattr(link, "story_arc", None) is not None
                and getattr(link.story_arc, "name", None)
            ] or None
        for edition in item.editions:
            catalog_number = catalog_number or getattr(edition, "catalog_number", None)
            release_status = release_status or getattr(edition, "release_status", None)
            country = country or getattr(edition, "region", None)
            language = language or getattr(edition, "language", None)
            age_rating = age_rating or getattr(edition, "age_rating", None)
            imprint_val = imprint_val or getattr(edition, "imprint", None)
            subtitle = subtitle or getattr(edition, "subtitle", None)
            series_group = series_group or getattr(edition, "series_group", None)
            primary = next((v for v in edition.variants if v.is_primary), None)
            if primary is not None:
                cover_price_cents = cover_price_cents or primary.cover_price_cents
                item_currency = item_currency or primary.currency
        component_attr = inspect(item).attrs.bundle_release_components.loaded_value
        bundle_releases = []
        if component_attr is not NO_VALUE and component_attr is not None:
            seen_bundle_ids: set[str] = set()
            for component in component_attr:
                bundle_release = getattr(component, "bundle_release", None)
                if bundle_release is None:
                    continue
                bundle_release_id = str(getattr(bundle_release, "id", ""))
                if bundle_release_id in seen_bundle_ids:
                    continue
                seen_bundle_ids.add(bundle_release_id)
                bundle_releases.append(bundle_release)
        bundle_releases = sorted(
            bundle_releases,
            key=lambda bundle: (
                getattr(bundle, "release_date", None) is None,
                -getattr(bundle, "release_date", None).toordinal()
                if getattr(bundle, "release_date", None) is not None
                else 0,
                str(getattr(bundle, "title", "")).casefold(),
            ),
        )
        if bundle_releases:
            bundle_titles = [bundle.title for bundle in bundle_releases if getattr(bundle, "title", None)]
            bundle_release_ids = [str(bundle.id) for bundle in bundle_releases]
        return SearchResult(
            id=item.id,
            kind=public_item_kind(item.kind),
            title=item.title,
            item_number=item.item_number,
            synopsis=item.synopsis,
            runtime_minutes=runtime_minutes,
            cover_image_url=cover_url,
            thumbnail_image_url=thumbnail_url,
            edition_title=edition_title,
            physical_format=physical_format_id,
            physical_format_label=physical_format_label,
            publisher=publisher,
            release_date=release_date,
            release_year=release_year,
            barcode=barcode,
            variant=variant_name,
            crossover=getattr(item, "crossover", None),
            plot_summary=getattr(item, "plot_summary", None),
            plot_description=getattr(item, "plot_description", None),
            series_title=series_title,
            volume_name=volume_name,
            track_count=track_count,
            tracks=tracks,
            catalog_number=catalog_number,
            creators=creators,
            characters=characters,
            character_details=character_details,
            story_arcs=story_arcs,
            platforms=platforms,
            genres=genres,
            page_count=page_count,
            cover_price_cents=cover_price_cents,
            currency=item_currency,
            country=country,
            release_status=release_status,
            language=language,
            age_rating=age_rating,
            imprint=imprint_val,
            subtitle=subtitle,
            series_group=series_group,
            bundle_titles=bundle_titles,
            bundle_release_ids=bundle_release_ids,
        )

    def _preferred_variant(
        self,
        item,
        *,
        query: str | None = None,
        barcode: str | None = None,
    ):
        normalized_barcode = self._normalized_barcode(barcode)
        normalized_query = " ".join(query.split()).casefold() if query else None
        if not normalized_barcode and not normalized_query:
            return None
        for edition in item.editions:
            for variant in edition.variants:
                if normalized_barcode and normalized_barcode in {
                    self._normalized_barcode(variant.barcode),
                    self._normalized_barcode(variant.isbn),
                    self._normalized_barcode(variant.sku),
                }:
                    return variant
                if normalized_query:
                    values = [
                        variant.name,
                        variant.variant_type,
                        variant.barcode,
                        variant.isbn,
                        variant.sku,
                        variant.platform,
                    ]
                    if any(value and normalized_query in str(value).casefold() for value in values):
                        return variant
        return None

    def _primary_variant(self, item):
        for edition in item.editions:
            primary = next((variant for variant in edition.variants if variant.is_primary), None)
            if primary is not None:
                return primary
            if edition.variants:
                return edition.variants[0]
        return None

    def _variant_cover(self, variant) -> tuple[str | None, str | None]:
        if variant is None:
            return None, None
        return variant.cover_image_url, variant.thumbnail_image_url

    def _normalized_barcode(self, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().replace("-", "").replace(" ", "").replace(".", "")
        return normalized or None

    def _physical_format(
        self,
        metadata: dict | None,
        *,
        fallback_format: str | None,
        kind: ItemKind,
    ):
        config = None
        if isinstance(metadata, dict):
            normalized = metadata.get("normalized")
            if isinstance(normalized, dict) and normalized.get("physical_format"):
                config = physical_format_for_id(str(normalized["physical_format"]))
        if config is None and fallback_format and is_video_item_kind(kind):
            config = physical_format_for_id(fallback_format)
        return config

    async def get_provider_seasons(
        self, provider_name: ExternalProvider, provider_item_id: str
    ) -> list[SeasonResponse]:
        from app.providers.base import NormalizedSeason

        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider_name.value}' is not configured",
            )
        if not hasattr(provider, "get_seasons"):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_seasons_unsupported",
                detail=f"Provider '{provider_name.value}' does not support seasons",
            )
        seasons: list[NormalizedSeason] = await provider.get_seasons(provider_item_id)
        return [
            SeasonResponse(
                season_number=s.season_number,
                title=s.title,
                provider_item_id=s.provider_item_id,
                overview=s.overview,
                air_date=s.air_date,
                episode_count=s.episode_count,
                poster_url=s.poster_url,
                episodes=[
                    ProviderEpisodeResponse(
                        episode_number=ep.episode_number,
                        title=ep.title,
                        provider_item_id=ep.provider_item_id,
                        overview=ep.overview,
                        air_date=ep.air_date,
                        runtime_minutes=ep.runtime_minutes,
                        page_count=ep.page_count,
                    )
                    for ep in s.episodes
                ],
            )
            for s in seasons
        ]

    async def get_provider_volumes(
        self, provider_name: ExternalProvider, provider_item_id: str
    ) -> list[SeasonResponse]:
        from app.providers.base import NormalizedSeason

        provider = self.providers.maybe_get(provider_name)
        if provider is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_not_configured",
                detail=f"Provider '{provider_name.value}' is not configured",
            )
        if not hasattr(provider, "get_volumes"):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_volumes_unsupported",
                detail=f"Provider '{provider_name.value}' does not support volumes",
            )
        volumes: list[NormalizedSeason] = await provider.get_volumes(provider_item_id)
        return [
            SeasonResponse(
                season_number=v.season_number,
                title=v.title,
                provider_item_id=v.provider_item_id,
                overview=v.overview,
                air_date=v.air_date,
                episode_count=v.episode_count,
                poster_url=v.poster_url,
                episodes=[
                    ProviderEpisodeResponse(
                        episode_number=ep.episode_number,
                        title=ep.title,
                        provider_item_id=ep.provider_item_id,
                        overview=ep.overview,
                        air_date=ep.air_date,
                        runtime_minutes=ep.runtime_minutes,
                        page_count=ep.page_count,
                    )
                    for ep in v.episodes
                ],
            )
            for v in volumes
        ]

    async def _tv_release_seasons(self, release: TVRelease) -> list[SeasonResponse]:

        episodes_by_season: dict[int, list[TVEpisode]] = defaultdict(list)
        for episode in release.episodes or []:
            episodes_by_season[episode.season_number].append(episode)
        season_provider_item_id = (
            release.metadata_json.get("provider_item_id")
            if isinstance(release.metadata_json, dict)
            else None
        )
        if not season_provider_item_id:
            season_provider_item_id = next(
                (
                    link.provider_item_id
                    for link in await self._provider_links_for_entity("tv_release", release.id)
                    if link.provider == ExternalProvider.tmdb and link.provider_item_id
                ),
                None,
            )
        seasons: list[SeasonResponse] = []
        for season_number, episodes in sorted(episodes_by_season.items(), key=lambda item: item[0]):
            ordered_episodes = sorted(
                episodes,
                key=lambda episode: (
                    episode.episode_number,
                    episode.original_air_date or date.max,
                    str(episode.id),
                ),
            )
            seasons.append(
                SeasonResponse(
                    season_number=season_number,
                    title=f"Season {season_number}",
                    provider_item_id=season_provider_item_id,
                    overview=release.description,
                    air_date=next(
                        (episode.original_air_date for episode in ordered_episodes if episode.original_air_date),
                        None,
                    ),
                    episode_count=len(ordered_episodes),
                    poster_url=release.cover_image_url,
                    episodes=[
                        ProviderEpisodeResponse(
                            episode_number=episode.episode_number,
                            title=episode.title,
                            provider_item_id=(
                                episode.metadata_json.get("provider_item_id")
                                if isinstance(episode.metadata_json, dict)
                                else None
                            ),
                            overview=episode.overview,
                            air_date=episode.original_air_date,
                            runtime_minutes=episode.duration_seconds // 60
                            if episode.duration_seconds is not None
                            else None,
                            page_count=None,
                        )
                        for episode in ordered_episodes
                    ],
                )
            )
        return seasons

    async def search_story_arcs(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[StoryArcResponse]:
        count_expr = func.count(StoryArcItem.id)
        stmt = (
            select(StoryArc, count_expr.label("item_count"))
            .outerjoin(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id)
            .group_by(StoryArc.id)
            .order_by(count_expr.desc(), StoryArc.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    StoryArc.name.ilike(pattern),
                    StoryArc.description.ilike(pattern),
                    StoryArc.publisher.ilike(pattern),
                )
            )
        rows = (await self.db.execute(stmt)).all()
        return [
            StoryArcResponse(
                id=arc.id,
                name=arc.name,
                description=arc.description,
                publisher=arc.publisher,
                start_date=arc.start_date,
                end_date=arc.end_date,
                item_count=int(item_count or 0),
            )
            for arc, item_count in rows
        ]

    async def search_creators(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[CreatorResponse]:
        count_expr = func.count(EntityPerson.id)
        stmt = (
            select(Person, count_expr.label("item_count"))
            .join(EntityPerson, EntityPerson.person_id == Person.id)
            .where(EntityPerson.entity_type == "item")
            .group_by(Person.id)
            .order_by(count_expr.desc(), Person.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(Person.name.ilike(pattern))
        rows = (await self.db.execute(stmt)).all()
        return [
            CreatorResponse(
                id=person.id,
                name=person.name,
                description=_model_text_or_metadata(person, "description"),
                image_url=_model_text_or_metadata(person, "image_url"),
                api_detail_url=_model_text_or_metadata(person, "api_detail_url"),
                site_detail_url=_model_text_or_metadata(person, "site_detail_url"),
                item_count=int(item_count or 0),
            )
            for person, item_count in rows
        ]

    async def get_creator_credits(
        self,
        creator_id: UUID,
    ) -> list[CreatorCreditResponse]:
        creator = await self.db.get(Person, creator_id)
        if creator is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="creator_not_found",
                detail="Creator not found",
            )
        links = list(
            (
                await self.db.execute(
                    select(EntityPerson)
                    .where(
                        EntityPerson.person_id == creator_id,
                        EntityPerson.entity_type == "item",
                    )
                    .order_by(EntityPerson.role.asc(), EntityPerson.created_at.asc())
                )
            ).scalars()
        )
        if not links:
            return []

        item_ids = [link.entity_id for link in links]
        items = {
            item.id: item
            for item in (
                await self.db.execute(select(Item).where(Item.id.in_(item_ids)))
            ).scalars()
        }
        results: list[CreatorCreditResponse] = []
        for link in links:
            item = items.get(link.entity_id)
            if item is None:
                continue
            results.append(
                CreatorCreditResponse(
                    creator_id=creator_id,
                    item_id=item.id,
                    role=link.role,
                    kind=public_item_kind(item.kind),
                    title=item.title,
                    item_number=item.item_number,
                    series_title=getattr(item, "series_title", None)
                    or (item.metadata_json.get("series_title") if isinstance(item.metadata_json, dict) else None),
                    volume_name=getattr(item, "volume_name", None)
                    or (item.metadata_json.get("volume_name") if isinstance(item.metadata_json, dict) else None),
                    cover_image_url=self._item_primary_cover_url(item),
                )
            )
        return results

    async def get_story_arc_items(self, story_arc_id: UUID) -> list[StoryArcItemResponse]:
        arc = await self.db.get(StoryArc, story_arc_id)
        if arc is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="story_arc_not_found",
                detail="Story arc not found",
            )
        links = list(
            (
                await self.db.execute(
                    select(StoryArcItem)
                    .where(StoryArcItem.story_arc_id == story_arc_id)
                    .options(selectinload(StoryArcItem.item))
                    .order_by(
                        StoryArcItem.ordinal.asc().nullslast(),
                        StoryArcItem.created_at.asc(),
                    )
                )
            ).scalars()
        )
        return [
            StoryArcItemResponse(
                story_arc_id=story_arc_id,
                item_id=link.item.id,
                ordinal=link.ordinal,
                kind=public_item_kind(link.item.kind),
                title=link.item.title,
                item_number=link.item.item_number,
                series_title=getattr(link.item, "series_title", None)
                or (link.item.metadata_json.get("series_title") if isinstance(link.item.metadata_json, dict) else None),
                volume_name=getattr(link.item, "volume_name", None)
                or (link.item.metadata_json.get("volume_name") if isinstance(link.item.metadata_json, dict) else None),
                cover_image_url=self._item_primary_cover_url(link.item),
            )
            for link in links
            if link.item is not None
        ]

    async def get_story_arc_facets(
        self,
        item_ids: list[UUID],
    ) -> list[StoryArcFacetResponse]:
        ordered_item_ids = list(dict.fromkeys(item_ids))
        if not ordered_item_ids:
            return []

        item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
        rows = (
            await self.db.execute(
                select(StoryArc, StoryArcItem.item_id)
                .join(StoryArcItem, StoryArcItem.story_arc_id == StoryArc.id)
                .where(StoryArcItem.item_id.in_(ordered_item_ids))
            )
        ).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for arc, item_id in rows:
            bucket = grouped.setdefault(
                arc.id,
                {
                    "arc": arc,
                    "item_ids": set(),
                },
            )
            cast_item_ids = bucket["item_ids"]
            if isinstance(cast_item_ids, set):
                cast_item_ids.add(item_id)

        facets: list[StoryArcFacetResponse] = []
        for bucket in grouped.values():
            arc = bucket["arc"]
            if not isinstance(arc, StoryArc):
                continue
            raw_item_ids = bucket["item_ids"]
            if not isinstance(raw_item_ids, set):
                continue
            facet_item_ids = sorted(
                raw_item_ids,
                key=lambda item_id: item_order.get(item_id, len(item_order)),
            )
            facets.append(
                StoryArcFacetResponse(
                    id=arc.id,
                    name=arc.name,
                    description=arc.description,
                    publisher=arc.publisher,
                    start_date=arc.start_date,
                    end_date=arc.end_date,
                    item_count=len(facet_item_ids),
                    item_ids=facet_item_ids,
                )
            )
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def get_creator_facets(
        self,
        item_ids: list[UUID],
    ) -> list[CreatorFacetResponse]:
        ordered_item_ids = list(dict.fromkeys(item_ids))
        if not ordered_item_ids:
            return []

        item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
        rows = (
            await self.db.execute(
                select(Person, EntityPerson.entity_id, EntityPerson.role)
                .join(EntityPerson, EntityPerson.person_id == Person.id)
                .where(
                    EntityPerson.entity_type == "item",
                    EntityPerson.entity_id.in_(ordered_item_ids),
                )
            )
        ).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for person, item_id, role in rows:
            bucket = grouped.setdefault(
                person.id,
                {
                    "person": person,
                    "item_ids": set(),
                    "role_counts": {},
                },
            )
            cast_item_ids = bucket["item_ids"]
            if isinstance(cast_item_ids, set):
                cast_item_ids.add(item_id)
            cast_role_counts = bucket["role_counts"]
            if isinstance(cast_role_counts, dict):
                cast_role_counts[role] = int(cast_role_counts.get(role, 0)) + 1

        facets: list[CreatorFacetResponse] = []
        for bucket in grouped.values():
            person = bucket["person"]
            if not isinstance(person, Person):
                continue
            raw_item_ids = bucket["item_ids"]
            if not isinstance(raw_item_ids, set):
                continue
            facet_item_ids = sorted(
                raw_item_ids,
                key=lambda item_id: item_order.get(item_id, len(item_order)),
            )
            role_counts = bucket["role_counts"]
            facets.append(
                CreatorFacetResponse(
                    id=person.id,
                    name=person.name,
                    description=_model_text_or_metadata(person, "description"),
                    image_url=_model_text_or_metadata(person, "image_url"),
                    item_count=len(facet_item_ids),
                    item_ids=facet_item_ids,
                    role_counts=role_counts if isinstance(role_counts, dict) else {},
                )
            )
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def search_characters(
        self,
        *,
        q: str | None = None,
        limit: int = 25,
    ) -> list[CharacterResponse]:
        count_expr = func.count(CharacterAppearance.id)
        stmt = (
            select(Character, count_expr.label("appearance_count"))
            .outerjoin(CharacterAppearance, CharacterAppearance.character_id == Character.id)
            .group_by(Character.id)
            .order_by(count_expr.desc(), Character.name.asc())
            .limit(limit)
        )
        if q:
            pattern = f"%{q.strip()}%"
            stmt = stmt.where(
                or_(
                    Character.name.ilike(pattern),
                    Character.description.ilike(pattern),
                )
            )
        rows = (await self.db.execute(stmt)).all()
        return [
            CharacterResponse(
                id=character.id,
                name=character.name,
                aliases=[str(alias) for alias in (character.aliases or []) if str(alias).strip()],
                description=character.description,
                image_url=character.image_url,
                first_appearance_item_id=character.first_appearance_item_id,
                appearance_count=int(appearance_count or 0),
            )
            for character, appearance_count in rows
        ]

    async def get_character_appearances(
        self,
        character_id: UUID,
    ) -> list[CharacterAppearanceResponse]:
        character = await self.db.get(Character, character_id)
        if character is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="character_not_found",
                detail="Character not found",
            )
        links = list(
            (
                await self.db.execute(
                    select(CharacterAppearance)
                    .where(CharacterAppearance.character_id == character_id)
                    .options(selectinload(CharacterAppearance.item))
                    .order_by(
                        CharacterAppearance.role.asc(),
                        CharacterAppearance.created_at.asc(),
                    )
                )
            ).scalars()
        )
        return [
            CharacterAppearanceResponse(
                character_id=character_id,
                item_id=link.item.id,
                role=link.role,
                kind=public_item_kind(link.item.kind),
                title=link.item.title,
                item_number=link.item.item_number,
                series_title=getattr(link.item, "series_title", None)
                or (link.item.metadata_json.get("series_title") if isinstance(link.item.metadata_json, dict) else None),
                volume_name=getattr(link.item, "volume_name", None)
                or (link.item.metadata_json.get("volume_name") if isinstance(link.item.metadata_json, dict) else None),
                cover_image_url=self._item_primary_cover_url(link.item),
            )
            for link in links
            if link.item is not None
        ]

    async def get_character_facets(
        self,
        item_ids: list[UUID],
    ) -> list[CharacterFacetResponse]:
        ordered_item_ids = list(dict.fromkeys(item_ids))
        if not ordered_item_ids:
            return []

        item_order = {item_id: index for index, item_id in enumerate(ordered_item_ids)}
        rows = (
            await self.db.execute(
                select(Character, CharacterAppearance.item_id, CharacterAppearance.role)
                .join(
                    CharacterAppearance,
                    CharacterAppearance.character_id == Character.id,
                )
                .where(CharacterAppearance.item_id.in_(ordered_item_ids))
            )
        ).all()
        grouped: dict[UUID, dict[str, object]] = {}
        for character, item_id, role in rows:
            bucket = grouped.setdefault(
                character.id,
                {
                    "character": character,
                    "item_ids": set(),
                    "role_counts": {},
                },
            )
            cast_item_ids = bucket["item_ids"]
            if isinstance(cast_item_ids, set):
                cast_item_ids.add(item_id)
            cast_role_counts = bucket["role_counts"]
            if isinstance(cast_role_counts, dict):
                role_key = str(role or "main")
                cast_role_counts[role_key] = int(cast_role_counts.get(role_key, 0)) + 1

        facets: list[CharacterFacetResponse] = []
        for bucket in grouped.values():
            character = bucket["character"]
            if not isinstance(character, Character):
                continue
            raw_item_ids = bucket["item_ids"]
            raw_role_counts = bucket["role_counts"]
            if not isinstance(raw_item_ids, set) or not isinstance(raw_role_counts, dict):
                continue
            facet_item_ids = sorted(
                raw_item_ids,
                key=lambda item_id: item_order.get(item_id, len(item_order)),
            )
            facets.append(
                CharacterFacetResponse(
                    id=character.id,
                    name=character.name,
                    aliases=[
                        str(alias) for alias in (character.aliases or []) if str(alias).strip()
                    ],
                    image_url=character.image_url,
                    item_count=len(facet_item_ids),
                    item_ids=facet_item_ids,
                    role_counts={str(role): int(count) for role, count in raw_role_counts.items()},
                )
            )
        facets.sort(key=lambda facet: (-facet.item_count, facet.name.casefold()))
        return facets

    async def _manga_volume_lookup_query(self, item) -> str:
        metadata = item.metadata_json if isinstance(item.metadata_json, dict) else {}
        series_title = metadata.get("volume_name") or metadata.get("series_title")
        title = series_title or item.title
        if not title:
            return ""
        cleaned = re.sub(r"\s*\((?:19|20)\d{2}\)\s*$", "", str(title)).strip()
        cleaned = re.sub(r"\s+#?\d+(?:[./-]\d+)?$", "", cleaned).strip()
        return cleaned or str(title).strip()

    def _best_mangadex_volume_candidate(
        self,
        item,
        results: list[ProviderSearchResult],
    ) -> ProviderSearchResult | None:
        metadata = item.metadata_json if isinstance(item.metadata_json, dict) else {}
        series_title = metadata.get("series_title")
        volume_name = metadata.get("volume_name")
        targets = {
            text
            for text in (
                self._normalized_title(item.title),
                self._normalized_title(series_title),
                self._normalized_title(volume_name),
            )
            if text
        }
        best: ProviderSearchResult | None = None
        best_score = 0
        for index, result in enumerate(results[:10]):
            if result.kind != ItemKind.comic or not result.provider_item_id:
                continue
            score = self._manga_title_match_score(targets, result)
            if score <= 0:
                continue
            ranked_score = score * 100 - index
            if ranked_score > best_score:
                best_score = ranked_score
                best = result
        return best

    def _manga_title_match_score(
        self,
        targets: set[str],
        result: ProviderSearchResult,
    ) -> int:
        title = self._normalized_title(result.series_title or result.title)
        if not title:
            return 0
        if title in targets:
            return 4
        if any(
            len(target) >= 4
            and len(title) >= 4
            and (title.startswith(target) or target.startswith(title))
            for target in targets
        ):
            return 3
        if any(
            len(target) >= 6 and len(title) >= 6 and (title in target or target in title)
            for target in targets
        ):
            return 2
        return 0

    def _normalized_title(self, value: str | None) -> str:
        if not value:
            return ""
        text = re.sub(r"\s+", " ", str(value)).casefold().strip()
        text = re.sub(r"\((?:19|20)\d{2}\)", "", text)
        text = re.sub(r"[^0-9a-z\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    def _item_primary_cover_url(self, item: Item) -> str | None:
        metadata = item.metadata_json if isinstance(item.metadata_json, dict) else {}
        for key in ("cover_image_url", "image_url", "thumbnail_image_url"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None
