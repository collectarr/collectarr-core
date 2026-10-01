import re
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.catalog.catalog_item_schema import (
    catalog_item_payload_contract,
    validate_catalog_item_payload,
)
from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.core.errors import ApiHTTPException
from app.metadata_normalized import (
    NORMALIZED_SCHEMA_VERSION,
    normalized_metadata_issues,
    typed_metadata_payload,
)
from app.models import (
    AnimeItem,
    AnimeItemIdentifier,
    BoardGameItem,
    BoardGameItemIdentifier,
    BookItem,
    BookItemCredit,
    BookItemIdentifier,
    Character,
    ComicItem,
    ComicItemIdentifier,
    EntityAlias,
    EntityLink,
    GameItem,
    GameItemIdentifier,
    MangaItem,
    MangaItemIdentifier,
    MovieItem,
    MusicItem,
    MusicItemDisc,
    MusicItemTrack,
    Person,
    PhysicalFormatRef,
    ReleaseStatus,
    StoryArc,
    TvItem,
    TvItemIdentifier,
    TVRelease,
    TVReleaseContribution,
    TVReleaseMedia,
    TVSeason,
    TVSeries,
)
from app.models.base import ItemKind
from app.models.partial_date import PartialDateValue, partial_date_storage
from app.schemas.admin import (
    AdminMetadataCorrectionRequest,
    AdminNormalizedMetadataDriftReportResponse,
    AdminNormalizedMetadataDriftSample,
)
from app.search.client import SearchClient
from app.search.documents import catalog_search_document
from app.services.catalog_item_search import CatalogItemSearchService

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
        results = await CatalogItemSearchService(self.db).search(
            query=query,
            kind=kind,
            series=series_group,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            country=self._normalize_region(country),
            language=self._normalize_language(language),
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=self._normalize_release_status(release_status),
            limit=limit,
            offset=0,
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
            metadata: dict[str, Any] = {}
            if kind == ItemKind.music:
                tracks: list[dict[str, Any]] = []
                releases = getattr(entity, "releases", []) or []
                for release in releases:
                    for media in sorted(
                        getattr(release, "mediums", []) or [],
                        key=lambda row: (getattr(row, "medium_number", 0), str(getattr(row, "id", ""))),
                    ):
                        for track in sorted(
                            getattr(media, "tracks", []) or [],
                            key=lambda row: (str(getattr(row, "position", "")), str(getattr(row, "id", ""))),
                        ):
                            tracks.append(
                                {
                                    "position": int(track.position) if str(track.position).isdigit() else track.position,
                                    "title": track.title,
                                    "artist": track.artist,
                                    "is_header": track.is_header,
                                    "indent_level": track.indent_level,
                                    "parent_header_id": track.parent_header_id,
                                    "duration_seconds": (
                                        track.duration_ms // 1000 if track.duration_ms is not None else None
                                    ),
                                }
                            )
                if tracks:
                    metadata["tracks"] = tracks
                    metadata["track_count"] = len(tracks)
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
            stored_normalized: dict[str, Any] | None = None
            if stored_normalized is None:
                return
            normalized = stored_normalized
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

        await _scan(BookItem, ItemKind.book, "book_item")
        await _scan(ComicItem, ItemKind.comic, "catalog_comic_item")
        await _scan(MusicItem, ItemKind.music, "catalog_music_item")
        await _scan(GameItem, ItemKind.game, "catalog_game_item")
        await _scan(MovieItem, ItemKind.movie, "catalog_movie_item")
        await _scan(TVSeries, ItemKind.tv, "tv_series")
        await _scan(BoardGameItem, ItemKind.boardgame, "catalog_boardgame_item")

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

        if kind == ItemKind.music and isinstance(entity, MusicItem):
            return await self._update_music_catalog_item(entity, payload)
        if kind == ItemKind.movie and isinstance(entity, MovieItem):
            return await self._update_movie_catalog_item(entity, payload)
        flat_kind_by_type = {
            BookItem: ItemKind.book,
            ComicItem: ItemKind.comic,
            MangaItem: ItemKind.manga,
            AnimeItem: ItemKind.anime,
            GameItem: ItemKind.game,
            BoardGameItem: ItemKind.boardgame,
            TvItem: ItemKind.tv,
        }
        flat_kind = next(
            (root_kind for model, root_kind in flat_kind_by_type.items() if isinstance(entity, model)),
            None,
        )
        if flat_kind is not None:
            return await self._update_flat_catalog_item(entity, flat_kind, payload)

        update_data = payload.model_dump(exclude_unset=True)
        entity_type = {
            ItemKind.anime: "catalog_anime_item",
            ItemKind.tv: "tv_series",
            ItemKind.music: "catalog_music_item",
        }[kind]
        def _current_value(key: str) -> Any:
            value = getattr(entity, key, None)
            if isinstance(value, list):
                return list(value)
            return value

        before: dict[str, Any] = {
            "title": getattr(entity, "title", None),
            "sort_title": getattr(entity, "sort_title", None),
            "subtitle": getattr(entity, "subtitle", None),
            "description": getattr(entity, "description", None),
            "search_aliases": _current_value("search_aliases") or [],
            "genres": _current_value("genres") or [],
            "platforms": _current_value("platforms") or [],
            "identifiers": _current_value("identifiers") or [],
            "company_roles": _current_value("company_roles") or [],
            "age_ratings": _current_value("age_ratings") or [],
            "contributors": _current_value("contributors") or [],
            "mechanics": _current_value("mechanics") or [],
            "categories": _current_value("categories") or [],
            "families": _current_value("families") or [],
            "expansions": _current_value("expansions") or [],
            "rankings": _current_value("rankings") or [],
            "tracks": _current_value("tracks") or [],
            "trailer_urls": self._current_link_payload(entity, "trailer_urls"),
            "external_links": self._current_link_payload(entity, "external_links"),
        }

        def _set_metadata_value(key: str, value: Any) -> None:
            field_by_key = {
                "original_title": "original_title",
                "localized_title": "localized_title",
                "crossover": "crossover",
                "plot_summary": "plot_summary",
                "plot_description": "plot_description",
                "audience_rating": "audience_rating",
            }
            field = field_by_key.get(key, key)
            if hasattr(entity, field):
                setattr(entity, field, value or None)

        def _set_named_field(obj: Any, field: str, value: Any) -> None:
            if hasattr(obj, field):
                setattr(obj, field, value)

        def _set_partial_date(obj: Any, field: str, value: Any) -> None:
            """Persist one lossless partial date plus its concrete projection."""
            parsed = None if value is None else PartialDateValue.model_validate(value)
            if hasattr(obj, f"{field}_parts"):
                setattr(obj, f"{field}_parts", partial_date_storage(parsed))
            if hasattr(obj, field):
                setattr(obj, field, parsed.as_date if parsed is not None else None)

        async def _clear_existing(collection: list[Any]) -> None:
            for row in list(collection):
                await self.db.delete(row)

        async def _replace_string_rows(
            model: Any,
            foreign_key: str,
            value_field: str,
            values: list[str] | None,
            *,
            normalized_field: str = "normalized_value",
            sequence_field: str = "sequence",
        ) -> None:
            await self.db.execute(
                delete(model).where(getattr(model, foreign_key) == entity.id)
            )
            for sequence, value in enumerate(self._normalize_text_values(values)):
                self.db.add(
                    model(
                        **{
                            foreign_key: entity.id,
                            value_field: value,
                            normalized_field: value.casefold(),
                            sequence_field: sequence,
                        }
                    )
                )

        async def _replace_identifier_rows(
            model: Any,
            foreign_key: str,
            values: list[str] | None,
        ) -> None:
            await self.db.execute(
                delete(model).where(getattr(model, foreign_key) == entity.id)
            )
            for index, raw_value in enumerate(self._normalize_text_values(values)):
                if ":" in raw_value:
                    identifier_type, value = raw_value.split(":", 1)
                    identifier_type = identifier_type.strip().lower() or "value"
                    value = value.strip() or raw_value
                else:
                    identifier_type, value = "value", raw_value
                self.db.add(
                    model(
                        **{
                            foreign_key: entity.id,
                            "identifier_type": identifier_type,
                            "value": value,
                            "normalized_value": value.casefold(),
                            "is_primary": index == 0,
                        }
                    )
                )

        async def _set_identifier(
            model: Any,
            foreign_key: str,
            identifier_type: str,
            value: str | None,
            *,
            owner_id: UUID,
        ) -> None:
            await self.db.execute(
                delete(model).where(
                    getattr(model, foreign_key) == owner_id,
                    model.identifier_type == identifier_type,
                )
            )
            clean_value = self._normalize_optional_text(value)
            if clean_value is not None:
                self.db.add(
                    model(
                        **{
                            foreign_key: owner_id,
                            "identifier_type": identifier_type,
                            "value": clean_value,
                            "normalized_value": clean_value.casefold(),
                            "is_primary": False,
                        }
                    )
                )

        async def _replace_aliases(values: list[str] | None) -> None:
            await self.db.execute(
                delete(EntityAlias).where(
                    EntityAlias.entity_type == entity_type,
                    EntityAlias.entity_id == entity.id,
                )
            )
            for position, value in enumerate(self._normalize_text_values(values)):
                self.db.add(
                    EntityAlias(
                        entity_type=entity_type,
                        entity_id=entity.id,
                        alias=value,
                        normalized_alias=value.casefold(),
                        position=position,
                    )
                )

        async def _replace_links(
            trailer_urls: list[dict[str, Any]] | None,
            external_links: list[dict[str, Any]] | None,
        ) -> None:
            await self.db.execute(
                delete(EntityLink).where(
                    EntityLink.entity_type == entity_type,
                    EntityLink.entity_id == entity.id,
                )
            )
            for link_type, values in (
                ("trailer", trailer_urls or []),
                ("external", external_links or []),
            ):
                for position, value in enumerate(values):
                    if not isinstance(value, dict):
                        continue
                    url = self._normalize_optional_text(value.get("url"))
                    if url is None:
                        continue
                    self.db.add(
                        EntityLink(
                            entity_type=entity_type,
                            entity_id=entity.id,
                            link_type=link_type,
                            url=url,
                            site=self._normalize_optional_text(value.get("site")),
                            name=self._normalize_optional_text(value.get("name")),
                            kind=self._normalize_optional_text(value.get("kind")),
                            description=self._normalize_optional_text(value.get("description")),
                            position=position,
                        )
                    )

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
            await _replace_aliases(payload.search_aliases)
        if "synopsis" in update_data:
            _set_named_field(entity, "description", self._normalize_optional_text(payload.synopsis))
        if "crossover" in update_data:
            _set_metadata_value("crossover", self._normalize_optional_text(payload.crossover))
        if "plot_summary" in update_data:
            _set_metadata_value("plot_summary", self._normalize_optional_text(payload.plot_summary))
        if "plot_description" in update_data:
            _set_metadata_value("plot_description", self._normalize_optional_text(payload.plot_description))

        if kind == ItemKind.tv:
            release = next(iter(getattr(entity, "releases", []) or []), None)
            media = primary_media
            if release is None and any(key in update_data for key in ("edition_title", "publisher", "barcode", "physical_format")):
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
                    _set_partial_date(release, "release_date", payload.release_date)
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
                if "cover_image_url" in update_data:
                    release.cover_image_url = payload.cover_image_url
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

        if "audience_rating" in update_data and kind not in {ItemKind.comic, ItemKind.music}:
            _set_named_field(entity, "audience_rating", payload.audience_rating)

        if "trailer_urls" in update_data or "external_links" in update_data:
            await _replace_links(
                payload.trailer_urls if "trailer_urls" in update_data else before["trailer_urls"],
                payload.external_links if "external_links" in update_data else before["external_links"],
            )

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

    async def _update_music_catalog_item(
        self,
        item: MusicItem,
        payload: AdminMetadataCorrectionRequest,
    ) -> Any:
        update_data = payload.model_dump(exclude_unset=True)
        supported_fields = {
            "title", "sort_title", "subtitle", "artist", "release_date",
            "original_release_date", "recording_date", "label", "format",
            "barcode", "catalog_number", "genres", "packaging", "studios",
            "country", "is_live", "sound_types", "vinyl_color",
            "vinyl_weight", "rpm", "extra", "spars", "box_set", "tracks",
            "external_links", "cover_image_url", "thumbnail_image_url",
            "back_cover_image_url",
        }
        unsupported = sorted(set(update_data) - supported_fields)
        if unsupported:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="music_correction_fields_unsupported",
                detail=(
                    "Unsupported Music Catalog Item correction fields: "
                    f"{', '.join(unsupported)}"
                ),
            )

        before = {
            key: getattr(item, key, None)
            for key in update_data
            if key != "tracks"
        }
        before["tracks"] = [
            {
                "title": track.title,
                "artist": track.artist,
                "disc_number": disc.disc_number,
                "position": track.position,
                "duration_seconds": (
                    track.duration_ms // 1000 if track.duration_ms is not None else None
                ),
            }
            for disc in item.discs
            for track in disc.tracks
        ]

        for field in (
            "title", "artist", "sort_title", "subtitle", "label", "format",
            "barcode", "catalog_number", "packaging", "country",
            "is_live", "vinyl_color", "vinyl_weight", "rpm", "extra", "spars",
            "box_set", "cover_image_url", "thumbnail_image_url",
            "back_cover_image_url",
        ):
            if field not in update_data:
                continue
            value = getattr(payload, field)
            if field == "title":
                value = self._normalize_optional_text(value)
                if value is None:
                    raise ApiHTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="music_title_required",
                        detail="Music Catalog Item title must not be empty",
                    )
            elif isinstance(value, str) and field not in {
                "cover_image_url", "thumbnail_image_url", "back_cover_image_url"
            }:
                value = self._normalize_optional_text(value)
            setattr(item, field, value)

        if "genres" in update_data:
            item.genres = self._normalize_text_values(payload.genres)
        if "studios" in update_data:
            item.studios = self._normalize_text_values(payload.studios)
        if "sound_types" in update_data:
            item.sound_types = self._normalize_text_values(payload.sound_types)
        if "external_links" in update_data:
            item.external_links = self._current_link_values(payload.external_links)

        for field in ("release_date", "original_release_date", "recording_date"):
            if field not in update_data:
                continue
            value = getattr(payload, field)
            parsed = PartialDateValue.model_validate(value) if value is not None else None
            setattr(item, f"{field}_parts", partial_date_storage(parsed))
            setattr(item, field, parsed.as_date if parsed is not None else None)

        if "tracks" in update_data:
            old_discs = {disc.disc_number: disc for disc in item.discs}
            tracks_by_disc: dict[int, list[dict[str, Any]]] = {}
            for row in self._normalize_tracks(payload.tracks):
                disc_number = row.get("disc_number", 1)
                if disc_number < 1:
                    raise ApiHTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="invalid_music_disc_number",
                        detail="Track disc_number must be greater than zero",
                    )
                tracks_by_disc.setdefault(disc_number, []).append(row)

            replacement_discs: list[MusicItemDisc] = []
            for disc_number, rows in sorted(tracks_by_disc.items()):
                old_disc = old_discs.get(disc_number)
                disc = MusicItemDisc(
                    disc_number=disc_number,
                    title=old_disc.title if old_disc is not None else None,
                    matrix_number_side_a=(
                        old_disc.matrix_number_side_a if old_disc is not None else None
                    ),
                    matrix_number_side_b=(
                        old_disc.matrix_number_side_b if old_disc is not None else None
                    ),
                    tracks=[],
                )
                for index, row in enumerate(rows):
                    duration = row.get("duration_seconds")
                    disc.tracks.append(
                        MusicItemTrack(
                            position=str(row.get("position", index + 1)),
                            position_order=index,
                            title=row["title"],
                            artist=row.get("artist"),
                            duration_ms=duration * 1000 if isinstance(duration, int) else None,
                        )
                    )
                replacement_discs.append(disc)
            item.discs = replacement_discs

        self._audit_recorder(
            action="metadata.correction",
            entity_type=ItemKind.music.value,
            entity_id=item.id,
            details={
                "kind": ItemKind.music.value,
                "fields": sorted(update_data),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()
        self.db.expire_all()
        loaded_item = await self._load_native_catalog_entity(ItemKind.music, item.id)
        if loaded_item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Music Catalog Item not found after correction",
            )
        await SearchClient().index_documents_best_effort([catalog_search_document(loaded_item)])
        return await self._item_response_loader(loaded_item)

    async def _update_movie_catalog_item(
        self,
        item: MovieItem,
        payload: AdminMetadataCorrectionRequest,
    ) -> Any:
        update_data = payload.model_dump(exclude_unset=True, mode="json")
        if not update_data:
            return await self._item_response_loader(item)

        contract_fields = set(
            catalog_item_payload_contract()["kinds"][ItemKind.movie.value]["properties"]
        )
        unsupported = sorted(set(update_data) - contract_fields)
        if unsupported:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="movie_correction_fields_unsupported",
                detail=(
                    "Unsupported Movie Catalog Item correction fields: "
                    f"{', '.join(unsupported)}"
                ),
            )

        before_payload = {
            **dict(item.details or {}),
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
        }
        try:
            projected = validate_catalog_item_payload(
                ItemKind.movie,
                {**before_payload, **update_data},
            )
        except (TypeError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="movie_correction_payload_invalid",
                detail=str(exc),
            ) from exc
        title = self._normalize_optional_text(projected.get("title"))
        if title is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="movie_title_required",
                detail="Movie Catalog Item title must not be empty",
            )

        item.title = title
        item.sort_key = self._normalize_optional_text(projected.pop("sort_key", None))
        item.barcode = self._normalize_optional_text(projected.pop("barcode", None))
        item.catalog_number = self._normalize_optional_text(
            projected.pop("catalog_number", None)
        )
        # `media` is a contained child table. The admin correction form edits
        # root fields only, so leave those rows to the kind-owned item API.
        projected.pop("media", None)
        projected.pop("title", None)
        item.details = projected

        self._audit_recorder(
            action="metadata.correction",
            entity_type=ItemKind.movie.value,
            entity_id=item.id,
            details={
                "kind": ItemKind.movie.value,
                "fields": sorted(update_data),
                "before": {key: before_payload.get(key) for key in update_data},
                "after": update_data,
            },
        )
        await self.db.commit()
        self.db.expire_all()
        loaded_item = await self._load_native_catalog_entity(ItemKind.movie, item.id)
        if loaded_item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Movie Catalog Item not found after correction",
            )
        await SearchClient().index_documents_best_effort(
            [catalog_search_document(loaded_item)]
        )
        return await self._item_response_loader(loaded_item)

    async def _update_flat_catalog_item(
        self,
        item: Any,
        kind: ItemKind,
        payload: AdminMetadataCorrectionRequest,
    ) -> Any:
        update_data = payload.model_dump(exclude_unset=True, mode="json")
        if not update_data:
            return await self._item_response_loader(item)

        contract_fields = set(
            catalog_item_payload_contract()["kinds"][kind.value]["properties"]
        )
        unsupported = sorted(set(update_data) - contract_fields)
        if unsupported:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="catalog_correction_fields_unsupported",
                detail=(
                    f"Unsupported {kind.value} Catalog Item correction fields: "
                    f"{', '.join(unsupported)}"
                ),
            )

        before_payload = {
            **dict(item.details or {}),
            "title": item.title,
            "sort_key": item.sort_key,
            "barcode": item.barcode,
            "catalog_number": item.catalog_number,
        }
        if hasattr(item, "identifiers"):
            before_payload["identifiers"] = [
                f"{row.identifier_type}: {row.value}" for row in item.identifiers
            ]
        if kind == ItemKind.book:
            before_payload["creators"] = [
                {"name": row.name, "role": row.role}
                for row in item.credits
                if row.credit_type == "creator"
            ]
            before_payload["contributors"] = [
                row.name for row in item.credits if row.credit_type == "contributor"
            ]
        try:
            projected = validate_catalog_item_payload(
                kind,
                {**before_payload, **update_data},
            )
        except (TypeError, ValueError) as exc:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="catalog_correction_payload_invalid",
                detail=str(exc),
            ) from exc

        title = self._normalize_optional_text(projected.get("title"))
        if title is None:
            raise ApiHTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                code="catalog_title_required",
                detail=f"{kind.value} Catalog Item title must not be empty",
            )

        item.title = title
        item.sort_key = self._normalize_optional_text(projected.pop("sort_key", None))
        item.barcode = self._normalize_optional_text(projected.pop("barcode", None))
        item.catalog_number = self._normalize_optional_text(
            projected.pop("catalog_number", None)
        )
        projected.pop("title", None)

        if "identifiers" in update_data:
            identifier_model_by_kind = {
                ItemKind.book: BookItemIdentifier,
                ItemKind.comic: ComicItemIdentifier,
                ItemKind.manga: MangaItemIdentifier,
                ItemKind.anime: AnimeItemIdentifier,
                ItemKind.game: GameItemIdentifier,
                ItemKind.boardgame: BoardGameItemIdentifier,
                ItemKind.tv: TvItemIdentifier,
            }
            identifier_model = identifier_model_by_kind[kind]
            identifiers = []
            seen_identifiers: set[tuple[str, str]] = set()
            for raw_value in self._normalize_text_values(payload.identifiers):
                if ":" in raw_value:
                    identifier_type, value = raw_value.split(":", 1)
                    identifier_type = identifier_type.strip().lower() or "value"
                    value = value.strip() or raw_value
                else:
                    identifier_type, value = "value", raw_value
                normalized_value = "".join(
                    character
                    for character in value.casefold()
                    if character.isalnum()
                )
                if not normalized_value:
                    continue
                identity = (identifier_type, normalized_value)
                if identity in seen_identifiers:
                    continue
                seen_identifiers.add(identity)
                identifiers.append(
                    identifier_model(
                        identifier_type=identifier_type,
                        value=value,
                        normalized_value=normalized_value,
                        is_primary=not identifiers,
                    )
                )
            item.identifiers = identifiers
        projected.pop("identifiers", None)

        if kind == ItemKind.book:
            if "creators" in update_data or "contributors" in update_data:
                retained_credits = [
                    row
                    for row in item.credits
                    if not (
                        ("creators" in update_data and row.credit_type == "creator")
                        or (
                            "contributors" in update_data
                            and row.credit_type == "contributor"
                        )
                    )
                ]
                if "creators" in update_data:
                    for sequence, creator in enumerate(payload.creators or [], start=1):
                        name = self._normalize_optional_text(creator.name)
                        if not name:
                            continue
                        retained_credits.append(
                            BookItemCredit(
                                credit_type="creator",
                                name=name,
                                role=self._normalize_optional_text(creator.role),
                                sequence=sequence,
                            )
                        )
                if "contributors" in update_data:
                    for sequence, raw_name in enumerate(
                        self._normalize_text_values(payload.contributors),
                        start=1,
                    ):
                        retained_credits.append(
                            BookItemCredit(
                                credit_type="contributor",
                                name=raw_name,
                                sequence=sequence,
                            )
                        )
                item.credits = retained_credits
            projected.pop("creators", None)
            projected.pop("contributors", None)

        for key in ("media", "episodes", "seasons", "printings"):
            projected.pop(key, None)
        item.details = projected

        self._audit_recorder(
            action="metadata.correction",
            entity_type=kind.value,
            entity_id=item.id,
            details={
                "kind": kind.value,
                "fields": sorted(update_data),
                "before": {key: before_payload.get(key) for key in update_data},
                "after": update_data,
            },
        )
        await self.db.commit()
        self.db.expire_all()
        loaded_item = await self._load_native_catalog_entity(kind, item.id)
        if loaded_item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail=f"{kind.value} Catalog Item not found after correction",
            )
        await self._reindex_items({item.id})
        return await self._item_response_loader(loaded_item)

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
        link_type = "trailer" if key == "trailer_urls" else "external"
        links = getattr(item, "entity_links", None)
        if isinstance(links, list):
            return self._current_link_values(
                [
                    {
                        "url": link.url,
                        "site": link.site,
                        "name": link.name,
                        "kind": link.kind,
                        "description": link.description,
                    }
                    for link in links
                    if link.link_type == link_type
                ]
            )
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
            recording_id = " ".join(str(raw.get("recording_id") or "").split()).strip()
            if recording_id:
                track["recording_id"] = recording_id
            if raw.get("is_header") is True:
                track["is_header"] = True
            indent_level = raw.get("indent_level")
            if isinstance(indent_level, int) and indent_level >= 0:
                track["indent_level"] = indent_level
            parent_header_id = " ".join(str(raw.get("parent_header_id") or "").split()).strip()
            if parent_header_id:
                track["parent_header_id"] = parent_header_id
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
            ItemKind.book: BookItem,
            ItemKind.comic: ComicItem,
            ItemKind.manga: MangaItem,
            ItemKind.anime: AnimeItem,
            ItemKind.movie: MovieItem,
            ItemKind.tv: TvItem,
            ItemKind.music: MusicItem,
            ItemKind.game: GameItem,
            ItemKind.boardgame: BoardGameItem,
        }
        model = model_by_kind.get(kind)
        if model is None:
            return None
        stmt = select(model).where(model.id == entity_id).options(
            *self._flat_catalog_item_load_options(kind)
        )
        return await self.db.scalar(stmt)

    def _flat_catalog_item_load_options(self, kind: ItemKind) -> list[Any]:
        if kind == ItemKind.book:
            return [
                selectinload(BookItem.printings),
                selectinload(BookItem.credits),
                selectinload(BookItem.identifiers),
            ]
        if kind in {ItemKind.comic, ItemKind.manga, ItemKind.game, ItemKind.boardgame}:
            item_model = {
                ItemKind.comic: ComicItem,
                ItemKind.manga: MangaItem,
                ItemKind.game: GameItem,
                ItemKind.boardgame: BoardGameItem,
            }[kind]
            return [selectinload(item_model.identifiers)]
        if kind == ItemKind.anime:
            return [
                selectinload(AnimeItem.media),
                selectinload(AnimeItem.episodes),
                selectinload(AnimeItem.identifiers),
            ]
        if kind == ItemKind.tv:
            return [
                selectinload(TvItem.seasons),
                selectinload(TvItem.media),
                selectinload(TvItem.episodes),
                selectinload(TvItem.identifiers),
            ]
        if kind == ItemKind.movie:
            return [selectinload(MovieItem.media)]
        if kind == ItemKind.music:
            return [selectinload(MusicItem.discs).selectinload(MusicItemDisc.tracks)]
        return []

    def _native_load_options(self, kind: ItemKind) -> list[Any]:
        if kind in {ItemKind.comic, ItemKind.manga, ItemKind.anime, ItemKind.game, ItemKind.boardgame}:
            return self._flat_catalog_item_load_options(kind)
        if kind == ItemKind.book:
            return [
                selectinload(BookItem.printings),
                selectinload(BookItem.credits),
                selectinload(BookItem.identifiers),
            ]
        if kind == ItemKind.movie:
            return [
                selectinload(MovieItem.media),
            ]
        if kind == ItemKind.music:
            return [
                selectinload(MusicItem.discs).selectinload(MusicItemDisc.tracks),
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
        return []
