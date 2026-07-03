from __future__ import annotations

from typing import Any

from app.catalog.physical_formats import is_video_item_kind, physical_format_for_id
from app.models.base import ItemKind
from app.schemas.metadata_shared import SearchResult, public_item_kind
from app.services.metadata_helpers import _loaded_rows, _model_text_or_metadata, _organization_name


class BundleService:
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
            preferred_format = self._physical_format(preferred_variant.metadata_json, fallback_format=preferred_variant.variant_type, kind=item.kind)
            if preferred_format is not None:
                physical_format_id = preferred_format.id
                physical_format_label = preferred_format.label
        for edition in item.editions:
            edition_title = edition_title or edition.title
            publisher = publisher or edition.publisher
            barcode = barcode or edition.upc or edition.isbn
            physical_format = self._physical_format(edition.metadata_json, fallback_format=edition.format, kind=item.kind)
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
                primary_format = self._physical_format(primary.metadata_json, fallback_format=primary.variant_type, kind=item.kind)
                if primary_format is not None:
                    physical_format_id = physical_format_id or primary_format.id
                    physical_format_label = physical_format_label or primary_format.label
            if publisher is not None and release_date is not None and barcode is not None and variant_name is not None and (not is_video_item_kind(item.kind) or physical_format_label is not None):
                break
        metadata_json = getattr(item, "metadata_json", None)
        metadata = metadata_json if isinstance(metadata_json, dict) else {}
        series_title = getattr(item, "series_title", None) or metadata.get("series_title")
        volume_name = getattr(item, "volume_name", None) or metadata.get("volume_name")
        metadata = getattr(item, "metadata_json", None)
        typed_metadata = dict(metadata.get("normalized") or {}) if isinstance(metadata, dict) else {}
        track_count: int | None = int(typed_metadata["track_count"]) if isinstance(typed_metadata.get("track_count"), int) else None
        tracks: list[dict] | None = typed_metadata.get("tracks") if isinstance(typed_metadata.get("tracks"), list) else None
        catalog_number: str | None = None
        creators: list[dict] | None = None
        characters: list[str] | None = None
        character_details: list[dict] | None = None
        story_arcs: list[str] | None = None
        platforms: list[str] | None = [str(value).strip() for value in typed_metadata.get("platforms", []) if str(value).strip()] if isinstance(typed_metadata.get("platforms"), list) else None
        genres: list[str] | None = [str(value).strip() for value in typed_metadata.get("genres", []) if str(value).strip()] if isinstance(typed_metadata.get("genres"), list) else None
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
        creator_links = sorted(_loaded_rows(item, "creator_links"), key=lambda link: (getattr(link, "created_at", None) is None, getattr(link, "created_at", None), str(getattr(link, "id", "") or "")))
        if creator_links:
            creators = [{"name": link.person.name, "role": link.role, "api_detail_url": _model_text_or_metadata(link.person, "api_detail_url"), "site_detail_url": _model_text_or_metadata(link.person, "site_detail_url"), "image_url": _model_text_or_metadata(link.person, "image_url")} for link in creator_links if getattr(link, "person", None) is not None and getattr(link.person, "name", None)] or None
        character_links = sorted(_loaded_rows(item, "character_appearances"), key=lambda appearance: (str(getattr(appearance, "role", "") or "").casefold(), str(getattr(getattr(appearance, "character", None), "name", "") or "").casefold()))
        if character_links:
            character_details = [{"name": appearance.character.name, "role": appearance.role, "aliases": [str(alias).strip() for alias in (getattr(appearance.character, "aliases", None) or []) if str(alias).strip()], "description": getattr(appearance.character, "description", None), "image_url": getattr(appearance.character, "image_url", None), "first_appearance_entity_type": getattr(appearance.character, "first_appearance_entity_type", None), "first_appearance_entity_id": getattr(appearance.character, "first_appearance_entity_id", None)} for appearance in character_links if getattr(appearance, "character", None) is not None and getattr(appearance.character, "name", None)] or None
            characters = [appearance.character.name for appearance in character_links if getattr(appearance, "character", None) is not None and getattr(appearance.character, "name", None)] or None
        story_arc_links = sorted(_loaded_rows(item, "story_arc_items"), key=lambda link: (getattr(link, "ordinal", None) is None, getattr(link, "ordinal", None) or 0, str(getattr(getattr(link, "story_arc", None), "name", "") or "").casefold()))
        if story_arc_links:
            story_arcs = [link.story_arc.name for link in story_arc_links if getattr(link, "story_arc", None) is not None and getattr(link.story_arc, "name", None)] or None
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
        return SearchResult(id=item.id, kind=public_item_kind(item.kind), title=item.title, item_number=item.item_number, synopsis=item.synopsis, runtime_minutes=runtime_minutes, cover_image_url=cover_url, thumbnail_image_url=thumbnail_url, edition_title=edition_title, physical_format=physical_format_id, physical_format_label=physical_format_label, publisher=publisher, release_date=release_date, release_year=release_year, barcode=barcode, variant=variant_name, crossover=getattr(item, "crossover", None), plot_summary=getattr(item, "plot_summary", None), plot_description=getattr(item, "plot_description", None), series_title=series_title, volume_name=volume_name, track_count=track_count, tracks=tracks, catalog_number=catalog_number, creators=creators, characters=characters, character_details=character_details, story_arcs=story_arcs, platforms=platforms, genres=genres, page_count=page_count, cover_price_cents=cover_price_cents, currency=item_currency, country=country, release_status=release_status, language=language, age_rating=age_rating, imprint=imprint_val, subtitle=subtitle, series_group=series_group)

    def _preferred_variant(self, item, *, query: str | None = None, barcode: str | None = None):
        normalized_barcode = self._normalized_barcode(barcode)
        normalized_query = " ".join(query.split()).casefold() if query else None
        if not normalized_barcode and not normalized_query:
            return None
        for edition in item.editions:
            for variant in edition.variants:
                if normalized_barcode and normalized_barcode in {self._normalized_barcode(variant.barcode), self._normalized_barcode(variant.isbn), self._normalized_barcode(variant.sku)}:
                    return variant
                if normalized_query:
                    values = [variant.name, variant.variant_type, variant.barcode, variant.isbn, variant.sku, variant.platform]
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

    def _physical_format(self, metadata: dict | None, *, fallback_format: str | None, kind: ItemKind):
        config = None
        if isinstance(metadata, dict):
            normalized = metadata.get("normalized")
            if isinstance(normalized, dict) and normalized.get("physical_format"):
                config = physical_format_for_id(str(normalized["physical_format"]))
        if config is None and fallback_format and is_video_item_kind(kind):
            config = physical_format_for_id(fallback_format)
        return config

    def _item_primary_cover_url(self, metadata_json: dict[str, Any] | None) -> str | None:
        metadata = metadata_json if isinstance(metadata_json, dict) else {}
        for key in ("cover_image_url", "image_url", "thumbnail_image_url"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None
