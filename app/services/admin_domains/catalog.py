import re
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.core.errors import ApiHTTPException
from app.metadata_normalized import (
    NORMALIZED_SCHEMA_VERSION,
    merge_normalized_metadata,
    normalized_metadata_issues,
    typed_metadata_payload,
)
from app.models import (
    AnimeSeries,
    BoardGameEdition,
    BoardGameWork,
    BookContribution,
    BookEdition,
    BookSeriesMembership,
    BookWork,
    Character,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIssue,
    ComicStoryArcMembership,
    ComicWork,
    GameRelease,
    GameWork,
    MangaWork,
    MovieRelease,
    MovieWork,
    MovieWorkContribution,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicTrack,
    Person,
    PhysicalFormatRef,
    ReleaseStatus,
    StoryArc,
    TVRelease,
    TVReleaseContribution,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.models.base import ItemKind
from app.schemas.admin import (
    AdminMetadataCorrectionRequest,
    AdminNormalizedMetadataDriftReportResponse,
    AdminNormalizedMetadataDriftSample,
)
from app.search.client import SearchClient
from app.search.documents import catalog_search_document
from app.services.facade import MetadataFacade as MetadataService

_LANGUAGE_RE = re.compile(r"^[a-z]{2,3}(?:-[a-z0-9]{2,8})*$")
_REGION_RE = re.compile(r"^[A-Z]{2}(?:-[A-Z0-9]{1,3})?$")


class AdminCatalogService:
    def __init__(
        self,
        *,
        db: Any,
        item_response_loader: Callable[[Any], Awaitable[Any]],
        audit_recorder: Callable[..., None],
        reindex_items: Callable[[set[UUID]], Awaitable[None]],
        sort_key_builder: Callable[[ItemKind, str, str | None], str],
        get_or_create_tag: Callable[[str, str], Awaitable[Any]],
    ) -> None:
        self.db = db
        self._item_response_loader = item_response_loader
        self._audit_recorder = audit_recorder
        self._reindex_items = reindex_items
        self._sort_key_builder = sort_key_builder
        self._get_or_create_tag = get_or_create_tag

    async def catalog_items(
        self,
        query: str | None = None,
        kind: ItemKind | None = None,
        limit: int = 25,
        publisher: str | None = None,
        imprint: str | None = None,
        subtitle: str | None = None,
        series_group: str | None = None,
        country: str | None = None,
        language: str | None = None,
        age_rating: str | None = None,
        catalog_number: str | None = None,
        release_status: str | None = None,
    ) -> list[Any]:
        results = await MetadataService(self.db).search(
            query=query,
            kind=kind,
            limit=limit,
            series=series_group,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            country=self._normalize_region(country),
            language=self._normalize_language(language),
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=self._normalize_release_status(release_status),
        )
        responses: list[Any] = []
        for result in results:
            entity = await self._load_native_catalog_entity(result.kind, result.id)
            if entity is None:
                continue
            responses.append(await self._item_response_loader(entity))
        return responses

    async def normalized_metadata_drift_report(
        self,
        *,
        sample_limit: int = 100,
        scan_limit: int | None = None,
    ) -> AdminNormalizedMetadataDriftReportResponse:
        schema_issue_keys = {"schema_version_missing", "schema_version_mismatch"}
        issue_counts: dict[str, int] = {}
        samples: list[AdminNormalizedMetadataDriftSample] = []
        scanned_entities = 0
        entities_with_normalized = 0
        drifted_entities = 0
        typed_scanned_items = 0
        typed_drifted_items = 0

        def _typed_source(entity: Any, kind: ItemKind) -> dict[str, Any]:
            metadata = dict(getattr(entity, "metadata_json", None) or {})
            metadata.pop("normalized", None)
            if kind == ItemKind.music:
                tracks: list[dict[str, Any]] = []
                for media in sorted(
                    getattr(entity, "media", []) or [],
                    key=lambda row: (getattr(row, "media_number", 0), str(getattr(row, "id", ""))),
                ):
                    for track in sorted(
                        getattr(media, "tracks", []) or [],
                        key=lambda row: (str(getattr(row, "position", "")), str(getattr(row, "id", ""))),
                    ):
                        tracks.append(
                            {
                                "position": int(track.position) if str(track.position).isdigit() else track.position,
                                "title": track.title,
                                "duration_seconds": (
                                    track.duration_ms // 1000 if track.duration_ms is not None else None
                                ),
                            }
                        )
                if tracks:
                    metadata["tracks"] = tracks
                    metadata["track_count"] = getattr(entity, "track_count", None) or len(tracks)
            primary_release = next(iter(getattr(entity, "releases", []) or []), None)
            primary_media = (
                next(iter(getattr(primary_release, "media", []) or []), None)
                if primary_release is not None
                else None
            )
            if kind in {ItemKind.movie, ItemKind.tv} and primary_media is not None:
                for key in ("color", "audio_tracks", "subtitles", "layers", "screen_ratio"):
                    value = getattr(primary_media, key, None)
                    if value is not None:
                        metadata[key] = value
                if getattr(primary_media, "num_discs", None) is not None:
                    metadata["nr_discs"] = primary_media.num_discs
                if getattr(primary_media, "aspect_ratio", None) is not None:
                    metadata.setdefault("screen_ratio", primary_media.aspect_ratio)
            return metadata

        def _record(entity_type: str, entity: Any, kind: ItemKind) -> None:
            nonlocal scanned_entities, entities_with_normalized, drifted_entities
            nonlocal typed_scanned_items, typed_drifted_items
            scanned_entities += 1
            typed_scanned_items += 1
            metadata_json = getattr(entity, "metadata_json", None)
            if not isinstance(metadata_json, dict):
                return
            normalized = metadata_json.get("normalized")
            if not isinstance(normalized, dict):
                return
            entities_with_normalized += 1
            issues = normalized_metadata_issues(normalized, kind=kind)
            if issues:
                drifted_entities += 1
                for issue in issues:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
                if len(samples) < sample_limit:
                    samples.append(
                        AdminNormalizedMetadataDriftSample(
                            entity_type=entity_type,
                            entity_id=entity.id,
                            kind=kind,
                            issues=issues,
                            normalized_keys=sorted(str(key) for key in normalized),
                        )
                    )
            expected_typed = typed_metadata_payload(normalized, kind=kind)
            actual_typed = typed_metadata_payload(_typed_source(entity, kind), kind=kind)
            issues = []
            for key in sorted(set(expected_typed) | set(actual_typed)):
                if key not in actual_typed:
                    issues.append(f"typed_missing:{key}")
                elif key not in expected_typed:
                    issues.append(f"typed_extra:{key}")
                elif expected_typed[key] != actual_typed[key]:
                    issues.append(f"typed_mismatch:{key}")
            if issues:
                typed_drifted_items += 1
                for issue in issues:
                    issue_counts[issue] = issue_counts.get(issue, 0) + 1
                if len(samples) < sample_limit:
                    samples.append(
                        AdminNormalizedMetadataDriftSample(
                            entity_type="typed_metadata",
                            entity_id=entity.id,
                            kind=kind,
                            issues=issues,
                            normalized_keys=sorted(set(expected_typed) | set(actual_typed)),
                        )
                    )

        async def _scan(model: Any, kind: ItemKind, entity_type: str) -> None:
            stmt = select(model).options(*self._native_load_options(kind)).order_by(model.id.asc())
            if scan_limit is not None:
                stmt = stmt.limit(scan_limit)
            rows = (await self.db.execute(stmt)).scalars()
            for entity in rows:
                _record(entity_type, entity, kind)

        await _scan(BookWork, ItemKind.book, "book_work")
        await _scan(ComicWork, ItemKind.comic, "comic_work")
        await _scan(MusicRelease, ItemKind.music, "music_release")
        await _scan(GameWork, ItemKind.game, "game_work")
        await _scan(MovieWork, ItemKind.movie, "movie_work")
        await _scan(TVSeries, ItemKind.tv, "tv_series")
        await _scan(BoardGameWork, ItemKind.boardgame, "boardgame_work")

        schema_issue_count = sum(count for issue, count in issue_counts.items() if issue in schema_issue_keys)
        blocking_issue_count = sum(
            count for issue, count in issue_counts.items() if issue not in schema_issue_keys
        )

        return AdminNormalizedMetadataDriftReportResponse(
            expected_schema_version=NORMALIZED_SCHEMA_VERSION,
            scan_limit=scan_limit,
            scan_limited=scan_limit is not None,
            scanned_entities=scanned_entities,
            entities_with_normalized=entities_with_normalized,
            drifted_entities=drifted_entities,
            typed_scanned_items=typed_scanned_items,
            typed_drifted_items=typed_drifted_items,
            schema_issue_count=schema_issue_count,
            blocking_issue_count=blocking_issue_count,
            release_gate_ok=(blocking_issue_count == 0),
            issue_counts=dict(sorted(issue_counts.items())),
            samples=samples,
        )

    async def update_catalog_item(
        self,
        item_id: UUID,
        payload: AdminMetadataCorrectionRequest,
        kind: ItemKind | None = None,
    ) -> Any:
        if kind is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="metadata_kind_required",
                detail="kind is required",
            )
        entity = await self._load_native_catalog_entity(kind, item_id)
        if entity is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )

        update_data = payload.model_dump(exclude_unset=True)
        metadata = dict(getattr(entity, "metadata_json", None) or {})
        before: dict[str, Any] = {
            "title": getattr(entity, "title", None),
            "sort_title": getattr(entity, "sort_title", None),
            "subtitle": getattr(entity, "subtitle", None),
            "description": getattr(entity, "description", None),
            "search_aliases": list(metadata.get("search_aliases") or []),
            "genres": list(metadata.get("genres") or []),
            "platforms": list(metadata.get("platforms") or []),
            "identifiers": list(metadata.get("identifiers") or []),
            "company_roles": list(metadata.get("company_roles") or []),
            "age_ratings": list(metadata.get("age_ratings") or []),
            "contributors": list(metadata.get("contributors") or []),
            "mechanics": list(metadata.get("mechanics") or []),
            "categories": list(metadata.get("categories") or []),
            "families": list(metadata.get("families") or []),
            "expansions": list(metadata.get("expansions") or []),
            "rankings": list(metadata.get("rankings") or []),
            "tracks": list(metadata.get("tracks") or []),
            "trailer_urls": list(metadata.get("trailer_urls") or []),
            "external_links": list(metadata.get("external_links") or []),
        }

        def _set_metadata_value(key: str, value: Any) -> None:
            if value is None or value == [] or value == {}:
                metadata.pop(key, None)
                return
            metadata[key] = value

        def _set_named_field(obj: Any, field: str, value: Any) -> None:
            if hasattr(obj, field):
                setattr(obj, field, value)

        async def _clear_existing(collection: list[Any]) -> None:
            for row in list(collection):
                await self.db.delete(row)

        primary_issue = next(iter(getattr(entity, "issues", []) or []), None)
        primary_edition = next(iter(getattr(entity, "editions", []) or []), None)
        primary_release = next(iter(getattr(entity, "releases", []) or []), None)
        primary_media = next(iter(getattr(entity, "media", []) or []), None)

        if "title" in update_data and payload.title is not None:
            _set_named_field(entity, "title", payload.title)
        if "sort_key" in update_data:
            _set_named_field(entity, "sort_title", self._normalize_optional_text(payload.sort_key))
        if "title_extension" in update_data:
            _set_named_field(entity, "subtitle", self._normalize_optional_text(payload.title_extension))
        if "original_title" in update_data:
            _set_metadata_value("original_title", self._normalize_optional_text(payload.original_title))
        if "localized_title" in update_data:
            _set_metadata_value("localized_title", self._normalize_optional_text(payload.localized_title))
        if "search_aliases" in update_data:
            _set_metadata_value("search_aliases", self._normalize_text_values(payload.search_aliases))
        if "synopsis" in update_data:
            _set_named_field(entity, "description", self._normalize_optional_text(payload.synopsis))
        if "crossover" in update_data:
            _set_metadata_value("crossover", self._normalize_optional_text(payload.crossover))
        if "plot_summary" in update_data:
            _set_metadata_value("plot_summary", self._normalize_optional_text(payload.plot_summary))
        if "plot_description" in update_data:
            _set_metadata_value("plot_description", self._normalize_optional_text(payload.plot_description))

        if kind == ItemKind.comic:
            issue = primary_issue
            if issue is None and any(key in update_data for key in ("item_number", "edition_title", "publisher")):
                issue = ComicIssue(work_id=entity.id)
                self.db.add(issue)
                await self.db.flush()
            if issue is not None:
                before["item_number"] = issue.issue_number
                before["edition_title"] = issue.display_title
                before["publisher"] = issue.publisher
                before["release_date"] = issue.release_date
                before["imprint"] = issue.imprint
                before["country"] = issue.region
                before["language"] = issue.language
                before["age_rating"] = issue.age_rating if hasattr(issue, "age_rating") else None
                before["catalog_number"] = None
                before["release_status"] = issue.release_status
                before["page_count"] = issue.page_count
                if "item_number" in update_data:
                    issue.issue_number = payload.item_number
                if "edition_title" in update_data:
                    issue.display_title = payload.edition_title
                if "publisher" in update_data:
                    issue.publisher = payload.publisher
                if "release_date" in update_data:
                    issue.release_date = payload.release_date
                if "imprint" in update_data:
                    issue.imprint = payload.imprint
                if "series_group" in update_data:
                    _set_metadata_value("series_group", self._normalize_optional_text(payload.series_group))
                if "country" in update_data:
                    issue.region = self._normalize_region(payload.country)
                if "language" in update_data:
                    issue.language = self._normalize_language(payload.language)
                if "age_rating" in update_data:
                    _set_metadata_value("age_rating", payload.age_rating)
                if "catalog_number" in update_data:
                    _set_metadata_value("catalog_number", payload.catalog_number)
                if "release_status" in update_data:
                    issue.release_status = self._normalize_release_status(payload.release_status)
                    if issue.release_status is not None:
                        await self._ensure_release_status(issue.release_status)
                if "page_count" in update_data:
                    issue.page_count = payload.page_count
                if "cover_image_url" in update_data:
                    issue.cover_image_url = payload.cover_image_url
                    issue.metadata_json = self._metadata_with_cover(issue.metadata_json, payload.cover_image_url, item_kind=kind)
                if "barcode" in update_data:
                    _set_metadata_value("barcode", payload.barcode)
                if "creators" in update_data:
                    await _clear_existing(list(getattr(entity, "contributions", []) or []))
                    await self.db.flush()
                    for index, creator in enumerate(payload.creators or [], start=1):
                        name = " ".join(str(creator.name or "").split()).strip()
                        if not name:
                            continue
                        person = await self._get_or_create_person(name)
                        self.db.add(
                            ComicContribution(
                                work_id=entity.id,
                                person_id=person.id,
                                role=(creator.role or "creator").strip() or "creator",
                                sequence=index,
                            )
                        )
                if "characters" in update_data and issue is not None:
                    await _clear_existing(list(getattr(issue, "character_appearances", []) or []))
                    await self.db.flush()
                    for name in self._normalize_text_values(payload.characters):
                        character = await self._get_or_create_character(name)
                        self.db.add(ComicCharacterAppearance(issue_id=issue.id, character_id=character.id, role="appears"))
                if "story_arcs" in update_data and issue is not None:
                    await _clear_existing(list(getattr(issue, "story_arc_memberships", []) or []))
                    await self.db.flush()
                    for index, name in enumerate(self._normalize_text_values(payload.story_arcs), start=1):
                        story_arc = await self._get_or_create_story_arc(name)
                        self.db.add(ComicStoryArcMembership(issue_id=issue.id, story_arc_id=story_arc.id, ordinal=index))
                if "external_links" in update_data:
                    _set_metadata_value("external_links", self._current_link_values(payload.external_links))
                if "trailer_urls" in update_data:
                    _set_metadata_value("trailer_urls", self._current_link_values(payload.trailer_urls))
                if "genres" in update_data:
                    _set_metadata_value("genres", self._normalize_text_values(payload.genres))
                if "audience_rating" in update_data:
                    _set_metadata_value("audience_rating", payload.audience_rating)

        elif kind == ItemKind.music:
            release = entity
            if "subtitle" in update_data:
                _set_metadata_value("subtitle", self._normalize_optional_text(payload.subtitle))
            if "publisher" in update_data:
                release.publisher = payload.publisher
            if "release_date" in update_data:
                release.release_date = payload.release_date
            if "catalog_number" in update_data:
                release.catalog_number = payload.catalog_number
            if "barcode" in update_data:
                release.barcode = payload.barcode
            if "language" in update_data:
                release.language = self._normalize_language(payload.language)
            if "country" in update_data:
                release.country_code = self._normalize_region(payload.country)
            if "release_status" in update_data:
                release.release_status = self._normalize_release_status(payload.release_status)
            if "audience_rating" in update_data:
                release.audience_rating = float(payload.audience_rating) if payload.audience_rating else None
            if "genres" in update_data:
                _set_metadata_value("genres", self._normalize_text_values(payload.genres))
            if "tracks" in update_data:
                tracks = self._normalize_tracks(payload.tracks)
                media = primary_media
                if media is None:
                    media = MusicMedia(release_id=release.id, media_number=1)
                    self.db.add(media)
                    await self.db.flush()
                await _clear_existing(list(getattr(media, "tracks", []) or []))
                await self.db.flush()
                for track in tracks:
                    self.db.add(
                        MusicTrack(
                            release_id=release.id,
                            media_id=media.id,
                            position=str(track.get("position") or len(getattr(media, "tracks", []) or []) + 1),
                            title=track["title"],
                            duration_ms=(track.get("duration_seconds") * 1000) if track.get("duration_seconds") else None,
                        )
                    )
                release.track_count = len(tracks)
                media.track_count = len(tracks)
                _set_metadata_value("tracks", tracks)
                _set_metadata_value("track_count", len(tracks))
            if "creators" in update_data:
                await _clear_existing(list(getattr(release, "contributions", []) or []))
                await self.db.flush()
                for index, creator in enumerate(payload.creators or [], start=1):
                    name = " ".join(str(creator.name or "").split()).strip()
                    if not name:
                        continue
                    person = await self._get_or_create_person(name)
                    self.db.add(
                        MusicReleaseContribution(
                            release_id=release.id,
                            person_id=person.id,
                            role=(creator.role or "creator").strip() or "creator",
                            sequence=index,
                        )
                    )

        elif kind == ItemKind.game:
            release = primary_release
            if release is None and any(key in update_data for key in ("edition_title", "publisher", "barcode")):
                release = GameRelease(work_id=entity.id, release_title=payload.edition_title)
                self.db.add(release)
                await self.db.flush()
            if release is not None:
                before["edition_title"] = release.release_title
                before["publisher"] = release.publisher
                before["release_date"] = release.release_date
                before["country"] = release.region_code
                before["language"] = release.language
                before["catalog_number"] = release.catalog_number
                before["barcode"] = release.barcode
                before["release_status"] = release.release_status
                if "title" in update_data:
                    entity.title = payload.title or entity.title
                if "edition_title" in update_data:
                    release.release_title = payload.edition_title
                if "publisher" in update_data:
                    release.publisher = payload.publisher
                if "release_date" in update_data:
                    release.release_date = payload.release_date
                if "country" in update_data:
                    release.region_code = self._normalize_region(payload.country)
                if "language" in update_data:
                    release.language = self._normalize_language(payload.language)
                if "catalog_number" in update_data:
                    release.catalog_number = payload.catalog_number
                if "barcode" in update_data:
                    release.barcode = payload.barcode
                if "release_status" in update_data:
                    release.release_status = self._normalize_release_status(payload.release_status)
                if "physical_format" in update_data:
                    physical_format = self._validated_physical_format(kind, payload.physical_format)
                    await self._ensure_physical_format_ref(physical_format)
                    release.format = physical_format.label
                    release.metadata_json = self._metadata_with_physical_format(release.metadata_json, physical_format, item_kind=kind)
                if "genres" in update_data:
                    _set_metadata_value("genres", self._normalize_text_values(payload.genres))
                if "platforms" in update_data:
                    _set_metadata_value("platforms", self._normalize_text_values(payload.platforms))
                if "identifiers" in update_data:
                    _set_metadata_value("identifiers", self._normalize_text_values(payload.identifiers))
                if "company_roles" in update_data:
                    _set_metadata_value("company_roles", self._normalize_text_values(payload.company_roles))
                if "age_ratings" in update_data:
                    _set_metadata_value("age_ratings", self._normalize_text_values(payload.age_ratings))
                if "trailer_urls" in update_data:
                    _set_metadata_value("trailer_urls", self._current_link_values(payload.trailer_urls))
                if "external_links" in update_data:
                    _set_metadata_value("external_links", self._current_link_values(payload.external_links))
                if "audience_rating" in update_data:
                    entity.audience_rating = payload.audience_rating

        elif kind in {ItemKind.movie, ItemKind.tv}:
            release = primary_release if kind == ItemKind.movie else next(iter(getattr(entity, "releases", []) or []), None)
            media = primary_media
            if release is None and any(key in update_data for key in ("edition_title", "publisher", "barcode", "physical_format")):
                if kind == ItemKind.movie:
                    release = MovieRelease(work_id=entity.id, format=payload.physical_format or "digital")
                    self.db.add(release)
                else:
                    release = TVRelease(series_id=entity.id, title=payload.edition_title or entity.title, format=payload.physical_format or "dvd")
                    self.db.add(release)
                    await self.db.flush()
            if release is not None:
                before["edition_title"] = getattr(release, "format", None)
                before["publisher"] = getattr(release, "publisher", None)
                before["release_date"] = getattr(release, "release_date", None)
                before["catalog_number"] = getattr(release, "catalog_number", None) or getattr(release, "sku", None)
                before["barcode"] = getattr(release, "barcode", None)
                if "subtitle" in update_data:
                    release.subtitle = self._normalize_optional_text(payload.subtitle)
                if "publisher" in update_data:
                    release.publisher = payload.publisher
                if "release_date" in update_data:
                    release.release_date = payload.release_date
                if "country" in update_data and hasattr(release, "region_code"):
                    release.region_code = self._normalize_region(payload.country)
                if "language" in update_data and hasattr(release, "language_audio"):
                    release.language_audio = [self._normalize_language(payload.language)] if payload.language else None
                if "catalog_number" in update_data:
                    if hasattr(release, "catalog_number"):
                        release.catalog_number = payload.catalog_number
                    if hasattr(release, "sku"):
                        release.sku = payload.catalog_number
                if "barcode" in update_data and hasattr(release, "barcode"):
                    release.barcode = payload.barcode
                if "release_status" in update_data and hasattr(release, "release_status"):
                    release.release_status = self._normalize_release_status(payload.release_status)
                if "color" in update_data and media is not None:
                    media.color = payload.color
                if "nr_discs" in update_data and media is not None and hasattr(media, "num_discs"):
                    media.num_discs = payload.nr_discs
                if "screen_ratio" in update_data and media is not None:
                    if hasattr(media, "screen_ratio"):
                        media.screen_ratio = payload.screen_ratio
                    if hasattr(media, "aspect_ratio"):
                        media.aspect_ratio = payload.screen_ratio
                if "audio_tracks" in update_data and media is not None:
                    media.audio_tracks = payload.audio_tracks
                if "subtitles" in update_data and media is not None:
                    media.subtitles = payload.subtitles
                if "layers" in update_data and media is not None:
                    media.layers = payload.layers
                if "physical_format" in update_data:
                    physical_format = self._validated_physical_format(kind, payload.physical_format)
                    await self._ensure_physical_format_ref(physical_format)
                    release.format = physical_format.label
                    release.metadata_json = self._metadata_with_physical_format(release.metadata_json, physical_format, item_kind=kind)
                    if media is not None:
                        media.metadata_json = self._metadata_with_physical_format(media.metadata_json, physical_format, item_kind=kind)
                if "cover_image_url" in update_data:
                    release.cover_image_url = payload.cover_image_url
                    release.metadata_json = self._metadata_with_cover(release.metadata_json, payload.cover_image_url, item_kind=kind)
                if "thumbnail_image_url" in update_data and media is not None:
                    media.metadata_json = self._metadata_with_cover(media.metadata_json, payload.thumbnail_image_url, item_kind=kind)
                if "creators" in update_data and kind == ItemKind.movie:
                    await _clear_existing(list(getattr(entity, "contributions", []) or []))
                    await self.db.flush()
                    for index, creator in enumerate(payload.creators or [], start=1):
                        name = " ".join(str(creator.name or "").split()).strip()
                        if not name:
                            continue
                        person = await self._get_or_create_person(name)
                        self.db.add(
                            MovieWorkContribution(
                                work_id=entity.id,
                                person_id=person.id,
                                role=(creator.role or "creator").strip() or "creator",
                                sequence=index,
                            )
                        )
                if "creators" in update_data and kind == ItemKind.tv:
                    await _clear_existing(list(getattr(entity, "contributions", []) or []))
                    await self.db.flush()
                    for index, creator in enumerate(payload.creators or [], start=1):
                        name = " ".join(str(creator.name or "").split()).strip()
                        if not name:
                            continue
                        person = await self._get_or_create_person(name)
                        self.db.add(
                            TVReleaseContribution(
                                release_id=entity.id,
                                person_id=person.id,
                                role=(creator.role or "creator").strip() or "creator",
                                sequence=index,
                            )
                        )

        elif kind == ItemKind.book:
            edition = primary_edition
            if edition is None and any(key in update_data for key in ("edition_title", "publisher", "barcode")):
                edition = BookEdition(work_id=entity.id)
                self.db.add(edition)
                await self.db.flush()
            if edition is not None:
                before["edition_title"] = edition.display_title
                before["publisher"] = edition.publisher
                before["release_date"] = edition.publication_date
                before["imprint"] = edition.imprint
                before["country"] = edition.region
                before["language"] = edition.language
                before["age_rating"] = edition.age_rating
                before["catalog_number"] = None
                before["release_status"] = edition.release_status
                if "edition_title" in update_data:
                    edition.display_title = payload.edition_title
                if "publisher" in update_data:
                    edition.publisher = payload.publisher
                if "release_date" in update_data:
                    edition.publication_date = payload.release_date
                if "imprint" in update_data:
                    edition.imprint = payload.imprint
                if "subtitle" in update_data:
                    entity.subtitle = payload.subtitle
                if "country" in update_data:
                    edition.region = self._normalize_region(payload.country)
                if "language" in update_data:
                    edition.language = self._normalize_language(payload.language)
                if "age_rating" in update_data:
                    edition.age_rating = payload.age_rating
                if "catalog_number" in update_data:
                    _set_metadata_value("catalog_number", payload.catalog_number)
                if "release_status" in update_data:
                    edition.release_status = self._normalize_release_status(payload.release_status)
                if "page_count" in update_data:
                    edition.page_count = payload.page_count
                if "cover_image_url" in update_data:
                    edition.cover_image_url = payload.cover_image_url
                    edition.metadata_json = self._metadata_with_cover(edition.metadata_json, payload.cover_image_url, item_kind=kind)
                if "creators" in update_data:
                    _clear_existing(list(getattr(entity, "contributions", []) or []))
                    await self.db.flush()
                    for index, creator in enumerate(payload.creators or [], start=1):
                        name = " ".join(str(creator.name or "").split()).strip()
                        if not name:
                            continue
                        person = await self._get_or_create_person(name)
                        self.db.add(
                            BookContribution(
                                work_id=entity.id,
                                person_id=person.id,
                                role=(creator.role or "creator").strip() or "creator",
                                sequence=index,
                            )
                        )

        elif kind == ItemKind.boardgame:
            edition = primary_edition
            if edition is None:
                edition = BoardGameEdition(work_id=entity.id)
                self.db.add(edition)
                await self.db.flush()
            if "edition_title" in update_data:
                edition.edition_title = payload.edition_title
            if "publisher" in update_data:
                edition.publisher = payload.publisher
            if "release_date" in update_data:
                edition.release_date = payload.release_date
            if "catalog_number" in update_data:
                edition.catalog_number = payload.catalog_number
            if "barcode" in update_data:
                edition.barcode = payload.barcode
            if "country" in update_data:
                edition.country = self._normalize_region(payload.country)
            if "language" in update_data:
                edition.language = self._normalize_language(payload.language)
            if "age_rating" in update_data:
                edition.age_rating = payload.age_rating
            if "audience_rating" in update_data:
                edition.audience_rating = payload.audience_rating
            if "release_status" in update_data:
                edition.release_status = self._normalize_release_status(payload.release_status)
            if "page_count" in update_data:
                _set_metadata_value("page_count", payload.page_count)
            if "genres" in update_data:
                _set_metadata_value("genres", self._normalize_text_values(payload.genres))
            if "platforms" in update_data:
                _set_metadata_value("platforms", self._normalize_text_values(payload.platforms))
            if "identifiers" in update_data:
                _set_metadata_value("identifiers", self._normalize_text_values(payload.identifiers))
            if "contributors" in update_data:
                _set_metadata_value("contributors", self._normalize_text_values(payload.contributors))
            if "mechanics" in update_data:
                _set_metadata_value("mechanics", self._normalize_text_values(payload.mechanics))
            if "categories" in update_data:
                _set_metadata_value("categories", self._normalize_text_values(payload.categories))
            if "families" in update_data:
                _set_metadata_value("families", self._normalize_text_values(payload.families))
            if "expansions" in update_data:
                _set_metadata_value("expansions", self._normalize_text_values(payload.expansions))
            if "rankings" in update_data:
                _set_metadata_value("rankings", self._normalize_text_values(payload.rankings))
            if "trailer_urls" in update_data:
                _set_metadata_value("trailer_urls", self._current_link_values(payload.trailer_urls))
            if "external_links" in update_data:
                _set_metadata_value("external_links", self._current_link_values(payload.external_links))

        if "search_aliases" in update_data:
            _set_metadata_value("search_aliases", self._normalize_text_values(payload.search_aliases))
        if "audience_rating" in update_data and kind not in {ItemKind.comic, ItemKind.music}:
            _set_metadata_value("audience_rating", payload.audience_rating)

        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        entity.metadata_json = metadata
        self._audit_recorder(
            action="metadata.correction",
            entity_type=str(kind),
            entity_id=entity.id,
            details={
                "kind": kind,
                "fields": sorted(update_data.keys()),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()
        self.db.expire_all()
        loaded_entity = await self._load_native_catalog_entity(kind, entity.id)
        if loaded_entity is not None:
            await SearchClient().index_documents_best_effort([catalog_search_document(loaded_entity)])
        return await self._item_response_loader(loaded_entity)

    def _validated_physical_format(
        self,
        kind: ItemKind,
        physical_format: str | None,
    ) -> PhysicalFormatConfig:
        if not physical_format:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="physical_format_required",
                detail="physical_format is required when updating a video format",
            )
        if not is_video_item_kind(kind):
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="physical_format_unsupported",
                detail="physical_format is only supported for movie and TV catalog items",
            )
        config = physical_format_for_id(physical_format)
        if config is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="invalid_physical_format",
                detail="physical_format must be one of DVD, Blu-ray, 4K UHD, VHS, LaserDisc, or digital",
            )
        return config

    def _apply_physical_format_to_edition(
        self,
        edition: Any,
        physical_format: PhysicalFormatConfig,
        *,
        item_kind: ItemKind,
    ) -> None:
        edition.format = physical_format.label
        edition.physical_format = physical_format.id
        edition.physical_format_label = physical_format.label
        edition.physical_format_media_family = physical_format.media_family
        edition.physical_format_variant_type = physical_format.variant_type
        edition.metadata_json = self._metadata_with_physical_format(
            edition.metadata_json,
            physical_format,
            item_kind=item_kind,
        )

    def _apply_physical_format_to_variant(
        self,
        variant: Any,
        physical_format: PhysicalFormatConfig,
        *,
        item_kind: ItemKind,
    ) -> None:
        variant.variant_type = physical_format.variant_type
        variant.physical_format = physical_format.id
        variant.physical_format_label = physical_format.label
        variant.physical_format_media_family = physical_format.media_family
        variant.physical_format_variant_type = physical_format.variant_type
        variant.metadata_json = self._metadata_with_physical_format(
            variant.metadata_json,
            physical_format,
            item_kind=item_kind,
        )

    def _metadata_with_physical_format(
        self,
        metadata_json: dict[str, Any] | None,
        physical_format: PhysicalFormatConfig,
        *,
        item_kind: ItemKind,
    ) -> dict[str, Any]:
        return merge_normalized_metadata(
            metadata_json,
            {
                "physical_format": physical_format.id,
                "physical_format_label": physical_format.label,
                "physical_format_media_family": physical_format.media_family,
                "physical_format_variant_type": physical_format.variant_type,
            },
            kind=item_kind,
        )

    def _metadata_with_cover(
        self,
        metadata_json: dict[str, Any] | None,
        source_url: str | None,
        *,
        item_kind: ItemKind,
    ) -> dict[str, Any]:
        return merge_normalized_metadata(
            metadata_json,
            {
                "cover_status": "external_url" if source_url else "missing",
                "cover_source_url": source_url,
                "cover_delivery_url": source_url,
                "cover_storage": (
                    "provider_external_url" if source_url else "generated_client_fallback"
                ),
                "cover_policy": (
                    "external_url_default" if source_url else "generated_cover_fallback"
                ),
            },
            kind=item_kind,
        )

    def _primary_edition_model(self, item: Any) -> Any | None:
        editions = list(item.editions or [])
        return editions[0] if editions else None

    def _primary_variant_model(self, item: Any) -> Any | None:
        for edition in item.editions or []:
            variants = list(edition.variants or [])
            primary = next((variant for variant in variants if variant.is_primary), None)
            if primary is not None:
                return primary
            if variants:
                return variants[0]
        return None

    async def _entity_tag_names(
        self,
        entity_type: str,
        entity_id: UUID,
        tag_kind: str | None = None,
    ) -> list[str]:
        from app.models import EntityTag, Tag

        stmt = (
            select(Tag.name)
            .join(EntityTag, EntityTag.tag_id == Tag.id)
            .where(
                EntityTag.entity_type == entity_type,
                EntityTag.entity_id == entity_id,
            )
            .order_by(Tag.name.asc())
        )
        if tag_kind is not None:
            stmt = stmt.where(Tag.kind == tag_kind)
        rows = await self.db.scalars(stmt)
        return [name for name in rows if isinstance(name, str) and name.strip()]

    async def _replace_entity_tags(
        self,
        entity_type: str,
        entity_id: UUID,
        tag_kind: str,
        names: list[str],
    ) -> None:
        from app.models import EntityTag, Tag

        existing_links = list(
            (
                await self.db.execute(
                    select(EntityTag)
                    .join(Tag, Tag.id == EntityTag.tag_id)
                    .where(
                        EntityTag.entity_type == entity_type,
                        EntityTag.entity_id == entity_id,
                        Tag.kind == tag_kind,
                    )
                )
            ).scalars()
        )
        for link in existing_links:
            await self.db.delete(link)
        await self.db.flush()
        for name in names:
            tag = await self._get_or_create_tag(tag_kind, name)
            self.db.add(EntityTag(entity_type=entity_type, entity_id=entity_id, tag_id=tag.id))
        await self.db.flush()

    def _current_creators(self, item: Any) -> list[dict[str, Any]]:
        entries: list[dict[str, Any]] = []
        for link in list(getattr(item, "creator_links", []) or []):
            person = getattr(link, "person", None)
            name = getattr(person, "name", None)
            if not isinstance(name, str) or not name.strip():
                continue
            role = getattr(link, "role", None)
            entry: dict[str, Any] = {"name": name.strip()}
            if isinstance(role, str) and role.strip():
                entry["role"] = role.strip()
            entries.append(entry)
        return entries

    def _current_characters(self, item: Any) -> list[str]:
        entries: list[str] = []
        for link in list(getattr(item, "character_appearances", []) or []):
            character = getattr(link, "character", None)
            name = getattr(character, "name", None)
            if not isinstance(name, str):
                continue
            value = name.strip()
            if value:
                entries.append(value)
        return entries

    def _current_story_arcs(self, item: Any) -> list[str]:
        rows = sorted(
            getattr(item, "story_arc_items", []) or [],
            key=lambda row: (
                getattr(row, "ordinal", None) is None,
                getattr(row, "ordinal", None),
                str(getattr(row, "id", "")),
            ),
        )
        entries: list[str] = []
        for row in rows:
            story_arc = getattr(row, "story_arc", None)
            name = getattr(story_arc, "name", None)
            if not isinstance(name, str):
                continue
            value = name.strip()
            if value:
                entries.append(value)
        return entries

    def _current_link_payload(self, item: Any, key: str) -> list[dict[str, Any]]:
        values = getattr(item, key, None)
        if not isinstance(values, list):
            return []
        return self._current_link_values(values)

    def _current_link_values(self, values: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for row in values or []:
            if not isinstance(row, dict):
                continue
            url = " ".join(str(row.get("url") or "").split()).strip()
            if not url:
                continue
            entry: dict[str, Any] = {"url": url}
            for field in ("site", "name", "kind", "description"):
                value = " ".join(str(row.get(field) or "").split()).strip()
                if value:
                    entry[field] = value
            result.append(entry)
        return result

    async def _ensure_release_status(self, status_value: str) -> None:
        existing = await self.db.scalar(
            select(ReleaseStatus).where(ReleaseStatus.code == status_value)
        )
        if existing is not None:
            return
        self.db.add(ReleaseStatus(code=status_value, label=status_value))

    async def _ensure_physical_format_ref(self, config: PhysicalFormatConfig) -> None:
        existing = await self.db.get(PhysicalFormatRef, config.id)
        if existing is not None:
            return
        self.db.add(
            PhysicalFormatRef(
                id=config.id,
                label=config.label,
                media_family=config.media_family,
                variant_type=config.variant_type,
            )
        )


    async def _get_or_create_person(self, name: str) -> Person:
        person = await self.db.scalar(select(Person).where(Person.name == name))
        if person is None:
            person = Person(name=name)
            self.db.add(person)
            await self.db.flush()
        return person

    async def _get_or_create_character(self, name: str) -> Character:
        character = await self.db.scalar(select(Character).where(Character.name == name))
        if character is None:
            character = Character(name=name, canonical_name=name.casefold())
            self.db.add(character)
            await self.db.flush()
        return character

    async def _get_or_create_story_arc(self, name: str) -> StoryArc:
        story_arc = await self.db.scalar(select(StoryArc).where(StoryArc.name == name))
        if story_arc is None:
            story_arc = StoryArc(name=name)
            self.db.add(story_arc)
            await self.db.flush()
        return story_arc

    def _normalize_text_values(self, values: list[str] | None) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in values or []:
            value = " ".join(str(raw or "").split()).strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(value)
        return normalized

    def _normalize_optional_text(self, value: str | None) -> str | None:
        normalized = " ".join(str(value or "").split()).strip()
        return normalized or None

    def _normalize_release_status(self, value: str | None) -> str | None:
        normalized = self._normalize_optional_text(value)
        return normalized.lower() if normalized is not None else None

    def _normalize_language(self, value: str | None) -> str | None:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            return None
        lowered = normalized.lower()
        return lowered if _LANGUAGE_RE.match(lowered) else None

    def _normalize_region(self, value: str | None) -> str | None:
        normalized = self._normalize_optional_text(value)
        if normalized is None:
            return None
        upper = normalized.upper()
        return upper if _REGION_RE.match(upper) else None

    def _normalize_tracks(self, values: list[dict[str, Any]] | None) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for raw in values or []:
            if not isinstance(raw, dict):
                continue
            title = " ".join(str(raw.get("title") or "").split()).strip()
            if not title:
                continue
            track: dict[str, Any] = {"title": title}
            position = raw.get("position")
            if isinstance(position, int):
                track["position"] = position
            duration_seconds = raw.get("duration_seconds")
            if isinstance(duration_seconds, int):
                track["duration_seconds"] = duration_seconds
            artist = " ".join(str(raw.get("artist") or "").split()).strip()
            if artist:
                track["artist"] = artist
            disc_number = raw.get("disc_number")
            if isinstance(disc_number, int):
                track["disc_number"] = disc_number
            normalized.append(track)
        return normalized

    def _normalize_admin_tags(self, tags: list[str]) -> list[str]:
        normalized: list[str] = []
        seen: set[str] = set()
        for raw in tags:
            value = " ".join(str(raw or "").split()).strip()
            if not value:
                continue
            key = value.casefold()
            if key in seen:
                continue
            seen.add(key)
            normalized.append(value)
        return normalized

    def _organization_name(self, item: Any, role: str) -> str | None:
        for link in list(getattr(item, "organization_links", []) or []):
            if getattr(link, "role", None) != role:
                continue
            organization = getattr(link, "organization", None)
            name = getattr(organization, "name", None)
            if name:
                return str(name)
        return None

    async def _load_native_catalog_entity(self, kind: ItemKind, entity_id: UUID) -> Any | None:
        model_by_kind = {
            ItemKind.book: BookWork,
            ItemKind.comic: ComicWork,
            ItemKind.manga: MangaWork,
            ItemKind.anime: AnimeSeries,
            ItemKind.movie: MovieWork,
            ItemKind.tv: TVSeries,
            ItemKind.music: MusicRelease,
            ItemKind.game: GameWork,
            ItemKind.boardgame: BoardGameWork,
        }
        model = model_by_kind.get(kind)
        if model is None:
            return None
        stmt = select(model).where(model.id == entity_id).options(*self._native_load_options(kind))
        return await self.db.scalar(stmt)

    def _native_load_options(self, kind: ItemKind) -> list[Any]:
        if kind == ItemKind.book:
            return [
                selectinload(BookWork.editions).selectinload(BookEdition.contributions).selectinload(
                    BookContribution.person
                ),
                selectinload(BookWork.editions).selectinload(BookEdition.identifiers),
                selectinload(BookWork.contributions).selectinload(BookContribution.person),
                selectinload(BookWork.series_memberships).selectinload(BookSeriesMembership.series),
            ]
        if kind in {ItemKind.comic, ItemKind.manga}:
            return [
                selectinload(ComicWork.issues).selectinload(ComicIssue.contributions).selectinload(
                    ComicContribution.person
                ),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
                selectinload(ComicWork.issues).selectinload(ComicIssue.character_appearances).selectinload(
                    ComicCharacterAppearance.character
                ),
                selectinload(ComicWork.issues).selectinload(ComicIssue.story_arc_memberships).selectinload(
                    ComicStoryArcMembership.story_arc
                ),
                selectinload(ComicWork.contributions).selectinload(ComicContribution.person),
            ]
        if kind == ItemKind.game:
            return [selectinload(GameWork.releases)]
        if kind == ItemKind.movie:
            return [
                selectinload(MovieWork.contributions).selectinload(MovieWorkContribution.person),
                selectinload(MovieWork.identifiers),
                selectinload(MovieWork.releases).selectinload(MovieRelease.media),
            ]
        if kind == ItemKind.music:
            return [
                selectinload(MusicRelease.media).selectinload(MusicMedia.tracks),
                selectinload(MusicRelease.contributions).selectinload(MusicReleaseContribution.person),
                selectinload(MusicRelease.identifiers),
            ]
        if kind == ItemKind.tv:
            return [
                selectinload(TVSeries.seasons).selectinload(TVSeason.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.media).selectinload(TVReleaseMedia.episodes),
                selectinload(TVSeries.releases).selectinload(TVRelease.contributions).selectinload(
                    TVReleaseContribution.person
                ),
                selectinload(TVSeries.releases).selectinload(TVRelease.identifiers),
            ]
        if kind == ItemKind.boardgame:
            return [selectinload(BoardGameWork.editions)]
        return []