"""Search the active flattened Catalog Item roots."""

from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import extract, func, literal, or_, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.kind_registry import (
    CATALOG_KIND_DEFINITIONS,
    CATALOG_KINDS_BY_ID,
    CatalogKindDefinition,
)
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.catalog_music_item import MusicItem
from app.models.partial_date import PartialDateValue
from app.schemas.metadata_shared import CatalogSearchItemEnvelope, CatalogSearchPage


class CatalogItemSearchService:
    """Search concrete catalog items without traversing Work or Release nodes."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def search(
        self,
        *,
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
        offset: int = 0,
    ) -> CatalogSearchPage:
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
            return CatalogSearchPage(items=[], next_offset=None, has_more=False)

        roots = [
            definition
            for definition in CATALOG_KIND_DEFINITIONS
            if kind is None or definition.kind is kind
        ]
        if not roots:
            return CatalogSearchPage(items=[], next_offset=None, has_more=False)

        arguments = {
            "query": query,
            "series": series,
            "issue_number": issue_number,
            "publisher": publisher,
            "imprint": imprint,
            "subtitle": subtitle,
            "series_group": series_group,
            "language": language,
            "country": country,
            "age_rating": age_rating,
            "catalog_number": catalog_number,
            "release_status": release_status,
            "year": year,
            "barcode": barcode,
        }
        candidates = union_all(
            *(self._candidate_query(root, arguments) for root in roots)
        ).subquery("catalog_item_search_candidates")
        selected_rows = (
            await self.db.execute(
                select(candidates.c.kind, candidates.c.item_id)
                .order_by(
                    candidates.c.sort_value,
                    candidates.c.title_value,
                    candidates.c.kind,
                    candidates.c.item_id,
                )
                .offset(offset)
                .limit(limit + 1)
            )
        ).all()
        if not selected_rows:
            return CatalogSearchPage(items=[], next_offset=None, has_more=False)

        has_more = len(selected_rows) > limit
        page = selected_rows[:limit]

        ids_by_kind: dict[ItemKind, list[UUID]] = {}
        for kind_value, item_id in page:
            ids_by_kind.setdefault(ItemKind(kind_value), []).append(item_id)

        items_by_kind: dict[ItemKind, dict[UUID, Any]] = {}
        for root in roots:
            ids = ids_by_kind.get(root.kind)
            if not ids:
                continue
            statement = select(root.model).where(root.model.id.in_(ids))
            rows = (await self.db.execute(statement)).scalars().unique().all()
            items_by_kind[root.kind] = {item.id: item for item in rows}

        items = [
            self._to_search_envelope(
                root=CATALOG_KINDS_BY_ID[ItemKind(kind_value)],
                item=items_by_kind.get(ItemKind(kind_value), {}).get(item_id),
            )
            for kind_value, item_id in page
            if items_by_kind.get(ItemKind(kind_value), {}).get(item_id) is not None
        ]
        return CatalogSearchPage(
            items=items,
            next_offset=offset + len(page) if has_more else None,
            has_more=has_more,
        )

    async def lookup_barcode(
        self,
        barcode: str,
        kind: ItemKind | None = None,
    ) -> CatalogSearchItemEnvelope:
        results = await self.search(
            kind=kind,
            barcode=barcode,
            limit=1,
        )
        if results.items:
            return results.items[0]
        raise ApiHTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            code="barcode_not_found",
            detail="Barcode not found",
        )

    def _candidate_query(
        self,
        root: CatalogKindDefinition,
        arguments: dict[str, Any],
    ):
        model = root.model
        query = _trim(arguments.get("query"))
        barcode = _trim(arguments.get("barcode"))
        predicates = []

        if query:
            pattern = f"%{query}%"
            predicates.append(
                or_(
                    model.title.ilike(pattern),
                    self._sort_column(root).ilike(pattern),
                    self._identifier_match(root, query),
                    model.barcode == query,
                    model.catalog_number == query,
                    *(
                        [
                            MusicItem.artist.ilike(pattern),
                            MusicItem.label.ilike(pattern),
                            MusicItem.subtitle.ilike(pattern),
                        ]
                        if root.kind is ItemKind.music
                        else []
                    ),
                )
            )
        if barcode:
            predicates.append(
                or_(
                    model.barcode == barcode,
                    self._identifier_match(root, barcode),
                )
            )

        music_columns = {
            "series": MusicItem.artist,
            "publisher": MusicItem.label,
            "subtitle": MusicItem.subtitle,
            "country": MusicItem.country,
        }
        detail_fields = {
            "series": "series_title",
            "issue_number": "issue_number",
            "publisher": "publisher",
            "imprint": "imprint",
            "subtitle": "subtitle",
            "series_group": "series_group",
            "language": "language",
            "country": "country",
            "age_rating": "age_rating",
            "release_status": "release_status",
        }
        for argument, field in detail_fields.items():
            value = _trim(arguments.get(argument))
            if not value:
                continue
            if root.kind is ItemKind.music:
                expression = music_columns.get(argument)
                if expression is None:
                    continue
                predicates.append(expression.ilike(f"%{value}%"))
            else:
                # Detail filters are picker/filter values, not free-text
                # search. Use JSONB containment so the per-root GIN index can
                # serve them instead of scanning each details document.
                predicates.append(model.details.contains({field: value}))

        catalog_number = _trim(arguments.get("catalog_number"))
        if catalog_number:
            if root.kind is ItemKind.music:
                predicates.append(MusicItem.catalog_number == catalog_number)
            else:
                predicates.append(
                    or_(
                        model.catalog_number == catalog_number,
                        model.details.contains({"catalog_number": catalog_number}),
                    )
                )

        year = arguments.get("year")
        if year is not None:
            if root.kind is ItemKind.music:
                predicates.append(
                    or_(
                        extract("year", MusicItem.release_date) == year,
                        extract("year", MusicItem.original_release_date) == year,
                        extract("year", MusicItem.recording_date) == year,
                        MusicItem.release_date_parts["year"].as_integer() == year,
                        MusicItem.original_release_date_parts["year"].as_integer() == year,
                        MusicItem.recording_date_parts["year"].as_integer() == year,
                    )
                )
            else:
                year_text = str(year)
                predicates.append(
                    or_(
                        model.details.contains({"year_published": year}),
                        model.details.contains({"release_date_parts": {"year": year}}),
                        model.details.contains({"release_date": year_text}),
                    )
                )

        sort_column = self._sort_column(root)
        statement = select(
            literal(root.kind.value).label("kind"),
            model.id.label("item_id"),
            func.lower(func.coalesce(sort_column, model.title)).label("sort_value"),
            func.lower(model.title).label("title_value"),
        )
        if predicates:
            statement = statement.where(*predicates)
        return statement

    @staticmethod
    def _sort_column(root: CatalogKindDefinition):
        if root.search_sort_column is not None:
            return root.search_sort_column
        return root.model.sort_key

    @staticmethod
    def _identifier_match(root: CatalogKindDefinition, value: str):
        if not hasattr(root.model, "details") or "identifiers" not in root.document.children:
            return literal(False)
        normalized = _normalize_identifier(value)
        return root.model.details.contains({"identifiers": [{"normalized_value": normalized}]})

    @staticmethod
    def _to_search_envelope(
        root: CatalogKindDefinition,
        item: Any,
    ) -> CatalogSearchItemEnvelope:
        details = {} if root.kind is ItemKind.music else item.details
        release_date = getattr(item, "release_date", None)
        date_parts_value = getattr(item, "release_date_parts", None)
        if release_date is None:
            release_date = _date(details.get("release_date"))
        if date_parts_value is None:
            date_parts_value = details.get("release_date_parts")
        if date_parts_value is None:
            date_parts_value = details.get("release_date")
        date_parts = _partial_date(date_parts_value)
        cover = getattr(item, "cover_image_url", None) or details.get("cover_image_url")
        thumbnail = getattr(item, "thumbnail_image_url", None) or details.get("thumbnail_image_url")
        kind_data: dict[str, Any] = {"title": item.title}

        def add(name: str, value: Any) -> None:
            if value is None:
                return
            field_name = name
            if name == "variant":
                field_name = "variant_name"
            elif root.kind is ItemKind.music and name == "publisher":
                field_name = "label"
            elif root.kind is ItemKind.music and name == "physical_format":
                field_name = "format"
            if field_name in root.response_model.model_fields and field_name not in {
                "id",
                "kind",
            }:
                kind_data[field_name] = value

        add(
            "synopsis",
            None if root.kind is ItemKind.music else _text(details.get("synopsis")),
        )
        add("cover_image_url", _text(cover))
        add("thumbnail_image_url", _text(thumbnail))
        add("display_title", _text(details.get("display_title")))
        add("edition_title", _text(details.get("edition_title")))
        add(
            "physical_format",
            _text(getattr(item, "format", None) or details.get("physical_format")),
        )
        add("physical_format_label", _text(details.get("physical_format_label")))
        add("artist", _text(getattr(item, "artist", None)))
        add(
            "publisher",
            _text(getattr(item, "label", None) or details.get("publisher")),
        )
        add("release_date", release_date)
        add("release_date_parts", date_parts)
        add("barcode", _text(getattr(item, "barcode", None)))
        add("item_number", _text(details.get("item_number")))
        add("catalog_number", _text(getattr(item, "catalog_number", None)))
        add("series_title", _text(details.get("series_title")))
        add("original_language", _text(details.get("original_language")))
        add("studio", _text(details.get("studio")))
        add("production_companies", _string_list(details.get("production_companies")))
        add("volume_name", _text(details.get("volume_name")))
        add("creators", _object_list(details.get("creators")))
        add("characters", _string_list(details.get("characters")))
        add("character_details", _object_list(details.get("character_details")))
        add("story_arcs", _string_list(details.get("story_arcs")))
        add("platforms", _string_list(details.get("platforms")))
        add(
            "genres",
            _string_list(
                getattr(item, "genres", None)
                if root.kind is ItemKind.music
                else details.get("genres")
            ),
        )
        add("page_count", _integer(details.get("page_count")))
        add("cover_price_cents", _integer(details.get("cover_price_cents")))
        add("currency", _text(details.get("currency")))
        add("country", _text(getattr(item, "country", None) or details.get("country")))
        add("release_status", _text(details.get("release_status")))
        add("language", _text(details.get("language")))
        add("age_rating", _text(details.get("age_rating")))
        add("imprint", _text(details.get("imprint")))
        add("subtitle", _text(getattr(item, "subtitle", None) or details.get("subtitle")))
        add("series_group", _text(details.get("series_group")))

        return CatalogSearchItemEnvelope(
            id=item.id,
            kind=root.kind,
            kind_data=kind_data,
        )


def _trim(value: Any) -> str | None:
    if value is None:
        return None
    result = str(value).strip()
    return result or None


def _normalize_identifier(value: str) -> str:
    return "".join(character for character in value.upper() if character.isalnum())


def _text(value: Any) -> str | None:
    return value.strip() or None if isinstance(value, str) else None


def _integer(value: Any) -> int | None:
    return int(value) if isinstance(value, int) and not isinstance(value, bool) else None


def _string_list(value: Any) -> list[str] | None:
    if not isinstance(value, list):
        return None
    rows = [entry.strip() for entry in value if isinstance(entry, str) and entry.strip()]
    return rows or None


def _object_list(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    rows = [entry for entry in value if isinstance(entry, dict)]
    return rows or None


def _partial_date(value: Any) -> PartialDateValue | None:
    if value is None:
        return None
    try:
        result = PartialDateValue.model_validate(value)
    except TypeError, ValueError:
        return None
    return None if result.is_empty else result


def _date(value: Any) -> date | None:
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
