"""Canonical catalog writer service.

Receives NormalizedProviderEnvelopeV1 and writes deduplicated canonical
catalog entries, including persons, organizations, relations, seasons,
episodes, tracks, bundle releases, provenance snapshots, and search indexing.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import PhysicalFormatConfig
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
    BookSeries,
    BookSeriesMembership,
    BookWork,
    Character,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicSeries,
    ComicSeriesMembership,
    ComicStoryArcMembership,
    ComicWork,
    EntityOrganization,
    EntityPerson,
    ExternalProviderId,
    GameRelease,
    GameWork,
    MangaChapter,
    MangaCharacterAppearance,
    MangaContribution,
    MangaIdentifier,
    MangaSeries,
    MangaSeriesMembership,
    MangaSeriesRelation,
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
    Organization,
    Person,
    PhysicalFormatRef,
    ProviderPayloadSnapshot,
    ReleaseStatus,
    StoryArc,
    Tag,
    TVEpisode,
    TVRelease,
    TVReleaseContribution,
    TVReleaseEpisodeMap,
    TVReleaseIdentifier,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.models.base import ExternalProvider, ItemKind, SeriesRelationType
from app.providers.base import (
    NormalizedBundleMember,
    NormalizedBundleRelease,
    NormalizedCredit,
    NormalizedEpisode,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    NormalizedTrack,
    NormalizedVariantCover,
)
from app.providers.envelope import NormalizedProviderEnvelopeV1, ProviderImageRef
from app.providers.normalize import normalize_arc_title, normalize_person_name
from app.schemas.admin import ProviderIngestResponse
from app.search.client import SearchClient
from app.search.documents import (
    anime_series_search_document,
    boardgame_search_document,
    book_work_search_document,
    comic_work_search_document,
    game_work_search_document,
    manga_work_search_document,
    movie_work_search_document,
    tv_release_search_document,
)
from app.services.admin_domains.provider_ingest_helpers import (
    book_identifier_type,
    comic_identifier_type,
    cover_metadata,
    normalized_identifier,
    normalized_language,
    normalized_region,
    normalized_release_status,
    physical_format_for_normalized,
    provider_metadata_json,
    variant_cover_name,
)
from app.services.admin_domains.shared import (
    character_appearance_role,
    comicvine_credit_provider_id,
    credit_provider_urls,
    provider_link_url_text,
    provider_link_urls_for_provider,
    slug,
    sort_key,
)
from app.services.facade import MetadataFacade as MetadataService
from app.storage.image_cache import ImageCache

logger = logging.getLogger(__name__)


def _parse_date(val: Any) -> date | None:
    if isinstance(val, date):
        return val
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, str) and val.strip():
        try:
            return date.fromisoformat(val.strip()[:10])
        except ValueError:
            return None
    return None


def normalized_item_from_envelope(envelope: NormalizedProviderEnvelopeV1) -> NormalizedItem:
    """Reconstruct NormalizedItem from envelope's normalized dict."""
    d = envelope.normalized
    kind = ItemKind(envelope.kind) if isinstance(envelope.kind, str) else envelope.kind

    creators = [
        NormalizedCredit(
            name=c.get("name", ""),
            role=c.get("role"),
            sort_name=c.get("sort_name"),
            api_detail_url=c.get("api_detail_url"),
            site_detail_url=c.get("site_detail_url"),
            image_url=c.get("image_url"),
            external_ids=dict(c.get("external_ids") or {}),
            role_id=c.get("role_id"),
        )
        for c in (d.get("creators") or [])
        if isinstance(c, dict)
    ]

    characters = [
        NormalizedCredit(
            name=c.get("name", ""),
            role=c.get("role"),
            sort_name=c.get("sort_name"),
            api_detail_url=c.get("api_detail_url"),
            site_detail_url=c.get("site_detail_url"),
            image_url=c.get("image_url"),
            external_ids=dict(c.get("external_ids") or {}),
            role_id=c.get("role_id"),
        )
        for c in (d.get("characters") or [])
        if isinstance(c, dict)
    ]

    story_arcs = [
        NormalizedCredit(
            name=c.get("name", ""),
            role=c.get("role"),
            sort_name=c.get("sort_name"),
            api_detail_url=c.get("api_detail_url"),
            site_detail_url=c.get("site_detail_url"),
            image_url=c.get("image_url"),
            external_ids=dict(c.get("external_ids") or {}),
            role_id=c.get("role_id"),
        )
        for c in (d.get("story_arcs") or [])
        if isinstance(c, dict)
    ]

    variant_covers = [
        NormalizedVariantCover(
            name=vc.get("name", ""),
            cover_image_url=vc.get("cover_image_url", ""),
            thumbnail_image_url=vc.get("thumbnail_image_url"),
            provider_item_id=vc.get("provider_item_id"),
            source_id=vc.get("source_id"),
            caption=vc.get("caption"),
        )
        for vc in (d.get("variant_covers") or [])
        if isinstance(vc, dict)
    ]

    relations = [
        NormalizedRelation(
            relation_type=r.get("relation_type", "related"),
            title=r.get("title", ""),
            provider=r.get("provider"),
            provider_id=r.get("provider_id"),
            kind=ItemKind(r["kind"]) if r.get("kind") else None,
            start_year=r.get("start_year"),
            image_url=r.get("image_url"),
        )
        for r in (d.get("relations") or [])
        if isinstance(r, dict)
    ]

    tracks = [
        NormalizedTrack(
            position=int(t.get("position", idx + 1)),
            title=t.get("title", ""),
            duration_seconds=t.get("duration_seconds"),
            artist=t.get("artist"),
            disc_number=t.get("disc_number"),
            instrument=t.get("instrument"),
            composition=t.get("composition"),
        )
        for idx, t in enumerate(d.get("tracks") or [])
        if isinstance(t, dict)
    ]

    seasons = []
    for s in d.get("seasons") or []:
        if isinstance(s, dict):
            episodes = [
                NormalizedEpisode(
                    episode_number=int(e.get("episode_number", ep_idx + 1)),
                    title=e.get("title", ""),
                    provider_item_id=e.get("provider_item_id"),
                    overview=e.get("overview"),
                    air_date=_parse_date(e.get("air_date")),
                    runtime_minutes=e.get("runtime_minutes"),
                    page_count=e.get("page_count"),
                    still_url=e.get("still_url"),
                    image_url=e.get("image_url"),
                    large_image_url=e.get("large_image_url"),
                )
                for ep_idx, e in enumerate(s.get("episodes") or [])
                if isinstance(e, dict)
            ]
            seasons.append(
                NormalizedSeason(
                    season_number=int(s.get("season_number", 1)),
                    title=s.get("title", ""),
                    provider_item_id=s.get("provider_item_id"),
                    overview=s.get("overview"),
                    air_date=_parse_date(s.get("air_date")),
                    episode_count=s.get("episode_count"),
                    poster_url=s.get("poster_url"),
                    episodes=episodes,
                )
            )

    return NormalizedItem(
        kind=kind,
        title=d.get("title", ""),
        item_number=str(d["item_number"]) if d.get("item_number") is not None else None,
        synopsis=d.get("synopsis"),
        series_title=d.get("series_title"),
        volume_name=d.get("volume_name"),
        volume_number=float(d["volume_number"]) if d.get("volume_number") is not None else None,
        volume_start_year=d.get("volume_start_year"),
        runtime_minutes=d.get("runtime_minutes"),
        page_count=d.get("page_count"),
        edition_title=d.get("edition_title"),
        edition_format=d.get("edition_format"),
        physical_format=d.get("physical_format"),
        publisher=d.get("publisher"),
        imprint=d.get("imprint"),
        release_date=_parse_date(d.get("release_date")),
        isbn=d.get("isbn"),
        barcode=d.get("barcode"),
        cover_price_cents=d.get("cover_price_cents"),
        currency=d.get("currency"),
        variant_name=d.get("variant_name"),
        variant_type=d.get("variant_type"),
        cover_image_url=d.get("cover_image_url"),
        creators=creators,
        characters=characters,
        story_arcs=story_arcs,
        external_ids=dict(d.get("external_ids") or {}),
        trailer_urls=list(d.get("trailer_urls") or []),
        external_links=list(d.get("external_links") or []),
        provider_ids=dict(d.get("provider_ids") or {}),
        volume_provider_ids=dict(d.get("volume_provider_ids") or {}),
        variant_covers=variant_covers,
        relations=relations,
        tracks=tracks,
        track_count=d.get("track_count"),
        catalog_number=d.get("catalog_number"),
        country=d.get("country"),
        release_status=d.get("release_status"),
        platforms=list(d.get("platforms") or []),
        genres=list(d.get("genres") or []),
        language=d.get("language"),
        age_rating=d.get("age_rating"),
        audience_rating=d.get("audience_rating"),
        min_players=d.get("min_players"),
        max_players=d.get("max_players"),
        playing_time_minutes=d.get("playing_time_minutes"),
        min_age=d.get("min_age"),
        color=d.get("color"),
        nr_discs=d.get("nr_discs"),
        screen_ratio=d.get("screen_ratio"),
        audio_tracks=d.get("audio_tracks"),
        subtitles=d.get("subtitles"),
        layers=d.get("layers"),
        subtitle=d.get("subtitle"),
        series_group=d.get("series_group"),
        distributor=d.get("distributor"),
        studio=d.get("studio"),
        recording_date=_parse_date(d.get("recording_date")),
        extras=d.get("extras"),
        packaging=d.get("packaging"),
        media_condition=d.get("media_condition"),
        sound_type=d.get("sound_type"),
        vinyl_color=d.get("vinyl_color"),
        vinyl_weight=d.get("vinyl_weight"),
        rpm=d.get("rpm"),
        spars=d.get("spars"),
    )


@dataclass(frozen=True)
class CanonicalCatalogWriteResult:
    item_id: UUID
    kind: str
    created: bool
    item: Any = None


class CanonicalCatalogWriter:
    """Writes normalized provider envelopes into canonical catalog models."""

    def __init__(
        self,
        db: AsyncSession,
        *,
        search_client: SearchClient | None = None,
        image_cache: ImageCache | None = None,
    ) -> None:
        self.db = db
        self.search_client = search_client
        self.image_cache = image_cache

    async def write_envelope(
        self,
        envelope: NormalizedProviderEnvelopeV1,
        *,
        force_update: bool = False,
    ) -> CanonicalCatalogWriteResult:
        """Process envelope and write canonical models."""
        provider_name = ExternalProvider(envelope.provider) if envelope.provider in ExternalProvider._value2member_map_ else envelope.provider
        provider_item_id = envelope.provider_item_id

        # 1. Deduplication check by external provider ID
        if not force_update:
            existing_ref = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == provider_name,
                    ExternalProviderId.provider_item_id == provider_item_id,
                )
            )
            if existing_ref:
                facade = MetadataService(self.db)
                item_dto = await self._load_item_dto(facade, ItemKind(envelope.kind), existing_ref.entity_id)
                return CanonicalCatalogWriteResult(
                    item_id=existing_ref.entity_id,
                    kind=envelope.kind,
                    created=False,
                    item=item_dto,
                )

        normalized = normalized_item_from_envelope(envelope)

        # 2. Record provenance snapshot
        await self._record_provider_snapshot(
            provider_name=provider_name,
            provider_item_id=provider_item_id,
            envelope=envelope,
        )

        # 3. Dispatch to kind-specific canonical creator
        kind = normalized.kind
        created = True
        item_id: UUID

        if kind == ItemKind.comic:
            work, work_created = await self._create_comic_work_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = work.id
            created = work_created
            await self.db.commit()
            await self._reindex_comic_work(work.id)

        elif kind == ItemKind.manga:
            work = await self._create_manga_work_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = work.id
            await self.db.commit()
            await self._reindex_manga_work(work.id)

        elif kind == ItemKind.anime:
            series = await self._create_anime_series_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = series.id
            await self.db.commit()
            await self._reindex_anime_series(series.id)

        elif kind == ItemKind.movie:
            work = await self._create_movie_work_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = work.id
            await self.db.commit()
            await self._reindex_movie_work(work.id)

        elif kind == ItemKind.tv:
            series = await self._create_tv_series_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = series.id
            await self.db.commit()
            await self._reindex_tv_series(series.id)

        elif kind == ItemKind.book:
            work = await self._create_book_work_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = work.id
            await self.db.commit()
            await self._reindex_book_work(work.id)

        elif kind == ItemKind.music:
            release = await self._create_music_release_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = release.id
            await self.db.commit()

        elif kind == ItemKind.game:
            work = await self._create_game_work_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = work.id
            await self.db.commit()
            await self._reindex_game_work(work.id)

        elif kind == ItemKind.boardgame:
            work = await self._create_boardgame_work_from_normalized(
                provider_name=provider_name,
                provider_item_id=provider_item_id,
                envelope=envelope,
                normalized=normalized,
            )
            item_id = work.id
            await self.db.commit()
            await self._reindex_boardgame_work(work.id)

        else:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="provider_ingest_unsupported",
                detail=f"Kind {kind} is not supported by CanonicalCatalogWriter",
            )

        facade = MetadataService(self.db)
        item_dto = await self._load_item_dto(facade, kind, item_id)
        return CanonicalCatalogWriteResult(
            item_id=item_id,
            kind=envelope.kind,
            created=created,
            item=item_dto,
        )

    async def _load_item_dto(self, facade: MetadataService, kind: ItemKind, item_id: UUID) -> Any:
        if kind == ItemKind.comic:
            return await facade.get_comic_work(item_id)
        if kind == ItemKind.manga:
            return await facade.get_manga_work(item_id)
        if kind == ItemKind.anime:
            return await facade.get_anime_series(item_id)
        if kind == ItemKind.movie:
            return await facade.get_movie_work(item_id)
        if kind == ItemKind.tv:
            return await facade.get_tv_series(item_id)
        if kind == ItemKind.book:
            return await facade.get_book_work(item_id)
        if kind == ItemKind.music:
            return await facade.get_music_release(item_id)
        if kind == ItemKind.game:
            return await facade.get_game_work(item_id)
        if kind == ItemKind.boardgame:
            return await facade.get_boardgame_work(item_id)
        return None

    async def _record_provider_snapshot(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
    ) -> None:
        p_name = provider_name.value if isinstance(provider_name, ExternalProvider) else str(provider_name)
        now = datetime.now(UTC)
        snapshot = ProviderPayloadSnapshot(
            provider=p_name,
            provider_item_id=provider_item_id,
            raw_payload=envelope.to_dict(),
            payload_hash=envelope.provenance.raw_payload_hash or "",
            fetched_at=now,
            expires_at=now + timedelta(days=30),
        )
        self.db.add(snapshot)
        await self.db.flush()

    # --- KIND WRITERS ---

    async def _create_comic_work_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> tuple[ComicWork, bool]:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        series_title = normalized.series_title or normalized.volume_name
        series = await self._get_or_create_comic_series(series_title) if series_title else None

        work_title = normalized.series_title or normalized.title
        work = await self.db.scalar(select(ComicWork).where(ComicWork.title == work_title))

        work_created = False
        if work is None:
            work = ComicWork(
                title=work_title,
                sort_title=sort_key(ItemKind.comic, work_title, None),
                subtitle=normalized.subtitle,
                description=normalized.synopsis,
                original_language=normalized_language(normalized.language),
                first_publication_date=normalized.release_date,
                metadata_json=provider_metadata_json(
                    p_enum,
                    provider_item_id,
                    kind=ItemKind.comic,
                    normalized={"series_title": normalized.series_title},
                ),
            )
            self.db.add(work)
            await self.db.flush()
            work_created = True

        release_status = normalized_release_status(normalized.release_status)
        if release_status is not None:
            await self._ensure_release_status(release_status)

        issue = None
        issue_provider_ids = {
            provider_item_id,
            *(provider_value for provider_value in normalized.provider_ids.values() if provider_value),
        }
        existing_provider_id = None
        if issue_provider_ids:
            existing_provider_id = await self.db.scalar(
                select(ExternalProviderId).where(
                    ExternalProviderId.provider == p_enum,
                    ExternalProviderId.entity_type == "comic_issue",
                    ExternalProviderId.provider_item_id.in_(issue_provider_ids),
                )
            )
        if existing_provider_id:
            issue = await self.db.scalar(
                select(ComicIssue).where(ComicIssue.id == existing_provider_id.entity_id)
            )

        if issue is None:
            issue = ComicIssue(
                work_id=work.id,
                issue_number=normalized.item_number,
                display_title=normalized.edition_title or normalized.title,
                publication_date=normalized.release_date,
                release_date=normalized.release_date,
                publisher=normalized.publisher,
                imprint=normalized.imprint,
                language=normalized_language(normalized.language),
                region=normalized_region(normalized.country),
                page_count=normalized.page_count,
                cover_price_cents=normalized.cover_price_cents,
                currency=(normalized.currency or "").upper()[:8] or None,
                release_status=release_status,
                cover_image_url=normalized.cover_image_url,
                metadata_json=provider_metadata_json(
                    p_enum,
                    provider_item_id,
                    kind=ItemKind.comic,
                    normalized={
                        "item_number": normalized.item_number,
                        "variant_name": normalized.variant_name,
                        "variant_type": normalized.variant_type,
                    },
                ),
            )
            self.db.add(issue)
            await self.db.flush()

        if series:
            membership = await self.db.scalar(
                select(ComicSeriesMembership).where(
                    ComicSeriesMembership.series_id == series.id,
                    ComicSeriesMembership.work_id == work.id,
                )
            )
            if not membership:
                membership = ComicSeriesMembership(
                    series_id=series.id,
                    work_id=work.id,
                    volume_number=normalized.volume_number,
                )
                self.db.add(membership)

        await self._replace_catalog_provider_links(
            entity_type="comic_work",
            entity_id=work.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )
        await self._replace_catalog_provider_links(
            entity_type="comic_issue",
            entity_id=issue.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = ComicContribution(
                work_id=work.id,
                person_id=person.id,
                role=credit.role or "creator",
            )
            self.db.add(contribution)

        for character_credit in normalized.characters:
            character = await self._get_or_create_character(
                character_credit.name,
                character_credit,
                provider=p_enum,
            )
            appearance = ComicCharacterAppearance(
                work_id=work.id,
                character_id=character.id,
                role=character_appearance_role(character_credit.role),
            )
            self.db.add(appearance)

        for arc_credit in normalized.story_arcs:
            story_arc = await self._get_or_create_story_arc(arc_credit.name, arc_credit)
            membership = ComicStoryArcMembership(
                story_arc_id=story_arc.id,
                work_id=work.id,
            )
            self.db.add(membership)

        return work, work_created

    async def _create_manga_work_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> MangaWork:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        series_title = normalized.series_title or normalized.title
        series = await self._get_or_create_manga_series(series_title)

        work = MangaWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.manga, normalized.title, None),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            original_language=normalized_language(normalized.language),
            first_publication_date=normalized.release_date,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.manga,
            ),
        )
        self.db.add(work)
        await self.db.flush()

        membership = MangaSeriesMembership(
            series_id=series.id,
            work_id=work.id,
            volume_number=normalized.volume_number,
        )
        self.db.add(membership)

        await self._replace_catalog_provider_links(
            entity_type="manga_work",
            entity_id=work.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = MangaContribution(
                work_id=work.id,
                person_id=person.id,
                role=credit.role or "author",
            )
            self.db.add(contribution)

        for character_credit in normalized.characters:
            character = await self._get_or_create_character(
                character_credit.name,
                character_credit,
                provider=p_enum,
            )
            appearance = MangaCharacterAppearance(
                work_id=work.id,
                character_id=character.id,
                role=character_appearance_role(character_credit.role),
            )
            self.db.add(appearance)

        return work

    async def _create_anime_series_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> AnimeSeries:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        series = AnimeSeries(
            title=normalized.title,
            sort_title=sort_key(ItemKind.anime, normalized.title, None),
            synopsis=normalized.synopsis,
            original_language=normalized_language(normalized.language),
            release_date=normalized.release_date,
            cover_image_url=normalized.cover_image_url,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.anime,
            ),
        )
        self.db.add(series)
        await self.db.flush()

        await self._replace_catalog_provider_links(
            entity_type="anime_series",
            entity_id=series.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = AnimeContribution(
                series_id=series.id,
                person_id=person.id,
                role=credit.role or "director",
            )
            self.db.add(contribution)

        for character_credit in normalized.characters:
            character = await self._get_or_create_character(
                character_credit.name,
                character_credit,
                provider=p_enum,
            )
            appearance = AnimeCharacterAppearance(
                series_id=series.id,
                character_id=character.id,
                role=character_appearance_role(character_credit.role),
            )
            self.db.add(appearance)

        return series

    async def _create_movie_work_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> MovieWork:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        work = MovieWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.movie, normalized.title, None),
            synopsis=normalized.synopsis,
            original_language=normalized_language(normalized.language),
            release_date=normalized.release_date,
            runtime_minutes=normalized.runtime_minutes,
            cover_image_url=normalized.cover_image_url,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.movie,
            ),
        )
        self.db.add(work)
        await self.db.flush()

        release = MovieRelease(
            work_id=work.id,
            title=normalized.edition_title or normalized.title,
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            country=normalized_region(normalized.country),
            cover_image_url=normalized.cover_image_url,
        )
        self.db.add(release)
        await self.db.flush()

        await self._replace_catalog_provider_links(
            entity_type="movie_work",
            entity_id=work.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = MovieWorkContribution(
                work_id=work.id,
                person_id=person.id,
                role=credit.role or "director",
            )
            self.db.add(contribution)

        return work

    async def _create_tv_series_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> TVSeries:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        series = TVSeries(
            title=normalized.title,
            sort_title=sort_key(ItemKind.tv, normalized.title, None),
            synopsis=normalized.synopsis,
            original_language=normalized_language(normalized.language),
            release_date=normalized.release_date,
            cover_image_url=normalized.cover_image_url,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.tv,
            ),
        )
        self.db.add(series)
        await self.db.flush()

        await self._replace_catalog_provider_links(
            entity_type="tv_series",
            entity_id=series.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = TVReleaseContribution(
                release_id=series.id,
                person_id=person.id,
                role=credit.role or "creator",
            )
            self.db.add(contribution)

        return series

    async def _create_book_work_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> BookWork:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        work = BookWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.book, normalized.title, None),
            subtitle=normalized.subtitle,
            description=normalized.synopsis,
            original_language=normalized_language(normalized.language),
            first_publication_date=normalized.release_date,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.book,
            ),
        )
        self.db.add(work)
        await self.db.flush()

        edition = BookEdition(
            work_id=work.id,
            edition_title=normalized.edition_title or normalized.title,
            publication_date=normalized.release_date,
            publisher=normalized.publisher,
            page_count=normalized.page_count,
            cover_image_url=normalized.cover_image_url,
        )
        self.db.add(edition)
        await self.db.flush()

        if normalized.series_title:
            series = await self._upsert_book_series(normalized.series_title)
            membership = BookSeriesMembership(
                series_id=series.id,
                work_id=work.id,
                book_number=str(normalized.volume_number) if normalized.volume_number else None,
            )
            self.db.add(membership)

        await self._replace_catalog_provider_links(
            entity_type="book_work",
            entity_id=work.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = BookContribution(
                work_id=work.id,
                person_id=person.id,
                role=credit.role or "author",
            )
            self.db.add(contribution)

        return work

    async def _create_music_release_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> MusicRelease:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        release = MusicRelease(
            title=normalized.title,
            sort_title=sort_key(ItemKind.music, normalized.title, None),
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            country=normalized_region(normalized.country),
            cover_image_url=normalized.cover_image_url,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.music,
            ),
        )
        self.db.add(release)
        await self.db.flush()

        if normalized.tracks:
            media = MusicMedia(
                release_id=release.id,
                media_type="digital",
                disc_number=1,
            )
            self.db.add(media)
            await self.db.flush()

            for track_data in normalized.tracks:
                track = MusicTrack(
                    media_id=media.id,
                    track_number=track_data.position,
                    title=track_data.title,
                    duration_seconds=track_data.duration_seconds,
                    artist=track_data.artist,
                )
                self.db.add(track)

        await self._replace_catalog_provider_links(
            entity_type="music_release",
            entity_id=release.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        for credit in normalized.creators:
            person = await self._get_or_create_person(credit.name, credit)
            contribution = MusicReleaseContribution(
                release_id=release.id,
                person_id=person.id,
                role=credit.role or "artist",
            )
            self.db.add(contribution)

        return release

    async def _create_game_work_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> GameWork:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        work = GameWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.game, normalized.title, None),
            synopsis=normalized.synopsis,
            release_date=normalized.release_date,
            cover_image_url=normalized.cover_image_url,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.game,
            ),
        )
        self.db.add(work)
        await self.db.flush()

        release = GameRelease(
            work_id=work.id,
            title=normalized.edition_title or normalized.title,
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            cover_image_url=normalized.cover_image_url,
        )
        self.db.add(release)
        await self.db.flush()

        await self._replace_catalog_provider_links(
            entity_type="game_work",
            entity_id=work.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        return work

    async def _create_boardgame_work_from_normalized(
        self,
        *,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        envelope: NormalizedProviderEnvelopeV1,
        normalized: NormalizedItem,
    ) -> BoardGameWork:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        work = BoardGameWork(
            title=normalized.title,
            sort_title=sort_key(ItemKind.boardgame, normalized.title, None),
            synopsis=normalized.synopsis,
            release_date=normalized.release_date,
            min_players=normalized.min_players,
            max_players=normalized.max_players,
            playing_time_minutes=normalized.playing_time_minutes,
            min_age=normalized.min_age,
            cover_image_url=normalized.cover_image_url,
            metadata_json=provider_metadata_json(
                p_enum,
                provider_item_id,
                kind=ItemKind.boardgame,
            ),
        )
        self.db.add(work)
        await self.db.flush()

        edition = BoardGameEdition(
            work_id=work.id,
            edition_title=normalized.edition_title or normalized.title,
            release_date=normalized.release_date,
            publisher=normalized.publisher,
            cover_image_url=normalized.cover_image_url,
        )
        self.db.add(edition)
        await self.db.flush()

        await self._replace_catalog_provider_links(
            entity_type="boardgame_work",
            entity_id=work.id,
            provider_name=p_enum,
            provider_item_id=provider_item_id,
            normalized=normalized,
        )

        return work

    # --- SEARCH INDEXING ---

    async def _reindex_comic_work(self, work_id: UUID) -> None:
        if not self.search_client:
            return
        work = await self.db.scalar(select(ComicWork).where(ComicWork.id == work_id))
        if work:
            await self.search_client.index_document(comic_work_search_document(work))

    async def _reindex_manga_work(self, work_id: UUID) -> None:
        if not self.search_client:
            return
        work = await self.db.scalar(select(MangaWork).where(MangaWork.id == work_id))
        if work:
            await self.search_client.index_document(manga_work_search_document(work))

    async def _reindex_anime_series(self, series_id: UUID) -> None:
        if not self.search_client:
            return
        series = await self.db.scalar(select(AnimeSeries).where(AnimeSeries.id == series_id))
        if series:
            await self.search_client.index_document(anime_series_search_document(series))

    async def _reindex_movie_work(self, work_id: UUID) -> None:
        if not self.search_client:
            return
        work = await self.db.scalar(select(MovieWork).where(MovieWork.id == work_id))
        if work:
            await self.search_client.index_document(movie_work_search_document(work))

    async def _reindex_tv_series(self, series_id: UUID) -> None:
        if not self.search_client:
            return
        series = await self.db.scalar(select(TVSeries).where(TVSeries.id == series_id))
        if series:
            await self.search_client.index_document(tv_release_search_document(series))

    async def _reindex_book_work(self, work_id: UUID) -> None:
        if not self.search_client:
            return
        work = await self.db.scalar(select(BookWork).where(BookWork.id == work_id))
        if work:
            await self.search_client.index_document(book_work_search_document(work))

    async def _reindex_game_work(self, work_id: UUID) -> None:
        if not self.search_client:
            return
        work = await self.db.scalar(select(GameWork).where(GameWork.id == work_id))
        if work:
            await self.search_client.index_document(game_work_search_document(work))

    async def _reindex_boardgame_work(self, work_id: UUID) -> None:
        if not self.search_client:
            return
        work = await self.db.scalar(select(BoardGameWork).where(BoardGameWork.id == work_id))
        if work:
            await self.search_client.index_document(boardgame_search_document(work))

    # --- ENTITY CREATION & LINKING HELPERS ---

    async def _ensure_release_status(self, status_value: str) -> None:
        exists = await self.db.scalar(
            select(ReleaseStatus).where(ReleaseStatus.name == status_value)
        )
        if not exists:
            self.db.add(ReleaseStatus(name=status_value))
            await self.db.flush()

    async def _get_or_create_comic_series(self, title: str | None) -> ComicSeries | None:
        if not title or not title.strip():
            return None
        clean = title.strip()
        series = await self.db.scalar(select(ComicSeries).where(ComicSeries.title == clean))
        if not series:
            series = ComicSeries(title=clean)
            self.db.add(series)
            await self.db.flush()
        return series

    async def _get_or_create_manga_series(self, title: str) -> MangaSeries:
        clean = title.strip()
        series = await self.db.scalar(select(MangaSeries).where(MangaSeries.title == clean))
        if not series:
            series = MangaSeries(title=clean)
            self.db.add(series)
            await self.db.flush()
        return series

    async def _upsert_book_series(self, title: str) -> BookSeries:
        clean = title.strip()
        series = await self.db.scalar(select(BookSeries).where(BookSeries.title == clean))
        if not series:
            series = BookSeries(title=clean)
            self.db.add(series)
            await self.db.flush()
        return series

    async def _get_or_create_person(self, name: str, credit: NormalizedCredit) -> Person:
        clean = normalize_person_name(name)
        person = await self.db.scalar(select(Person).where(Person.name == clean))
        if not person:
            person = Person(
                name=clean,
                sort_name=credit.sort_name or clean,
            )
            self.db.add(person)
            await self.db.flush()
        return person

    async def _get_or_create_organization(self, name: str, org_type: str) -> Organization:
        clean = name.strip()
        org = await self.db.scalar(select(Organization).where(Organization.name == clean))
        if not org:
            org = Organization(
                name=clean,
                organization_type=org_type,
            )
            self.db.add(org)
            await self.db.flush()
        return org

    async def _get_or_create_character(
        self,
        name: str,
        credit: NormalizedCredit,
        *,
        provider: ExternalProvider | str | None = None,
    ) -> Character:
        clean = name.strip()
        character = await self.db.scalar(select(Character).where(Character.name == clean))
        if not character:
            character = Character(name=clean)
            self.db.add(character)
            await self.db.flush()
        return character

    async def _get_or_create_story_arc(self, name: str, credit: NormalizedCredit) -> StoryArc:
        clean = normalize_arc_title(name)
        arc = await self.db.scalar(select(StoryArc).where(StoryArc.title == clean))
        if not arc:
            arc = StoryArc(title=clean)
            self.db.add(arc)
            await self.db.flush()
        return arc

    async def _replace_catalog_provider_links(
        self,
        *,
        entity_type: str,
        entity_id: UUID,
        provider_name: ExternalProvider | str,
        provider_item_id: str,
        normalized: NormalizedItem,
    ) -> None:
        p_enum = ExternalProvider(provider_name) if provider_name in ExternalProvider._value2member_map_ else provider_name
        existing = await self.db.scalar(
            select(ExternalProviderId).where(
                ExternalProviderId.entity_type == entity_type,
                ExternalProviderId.entity_id == entity_id,
                ExternalProviderId.provider == p_enum,
            )
        )
        if not existing:
            self.db.add(
                ExternalProviderId(
                    entity_type=entity_type,
                    entity_id=entity_id,
                    provider=p_enum,
                    provider_item_id=str(provider_item_id),
                )
            )
