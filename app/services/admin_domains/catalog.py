from collections.abc import Awaitable, Callable
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import select

from app.catalog.physical_formats import (
    PhysicalFormatConfig,
    is_video_item_kind,
    physical_format_for_id,
)
from app.core.errors import ApiHTTPException
from app.metadata_normalized import merge_normalized_metadata, set_normalized_metadata
from app.models.base import ItemKind
from app.models.canonical import BundleReleaseItem, Edition, EntityOrganization, Item, Organization, Series, Variant
from app.repositories.metadata import MetadataRepository
from app.schemas.admin import (
    AdminBundleReleaseCorrectionRequest,
    AdminMetadataCorrectionRequest,
    AdminSeriesTagsUpdateRequest,
)
from app.schemas.metadata import (
    BundleReleaseDetailResponse,
    SeriesResponse,
    bundle_release_detail_from_model,
    bundle_release_member_sort_key,
)
from app.search.client import SearchClient
from app.search.documents import item_search_document


class AdminCatalogService:
    def __init__(
        self,
        *,
        db: Any,
        item_response_loader: Callable[[Item], Awaitable[Any]],
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
        items = await MetadataRepository(self.db).search_items(
            query=query,
            kind=kind,
            limit=limit,
            publisher=publisher,
            imprint=imprint,
            subtitle=subtitle,
            series_group=series_group,
            country=country,
            language=language,
            age_rating=age_rating,
            catalog_number=catalog_number,
            release_status=release_status,
        )
        return [await self._item_response_loader(item) for item in items]

    async def update_catalog_item(
        self,
        item_id: UUID,
        payload: AdminMetadataCorrectionRequest,
        kind: ItemKind | None = None,
    ) -> Any:
        item = await MetadataRepository(self.db).get_item(item_id, kind)
        if item is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="metadata_item_not_found",
                detail="Item not found",
            )
        update_data = payload.model_dump(exclude_unset=True)
        before = {
            "title": item.title,
            "item_number": item.item_number,
            "synopsis": item.synopsis,
            "edition_title": None,
            "page_count": item.page_count,
            "runtime_minutes": item.runtime_minutes,
            "publisher": None,
            "release_date": None,
            "imprint": None,
            "subtitle": None,
            "series_group": None,
            "country": None,
            "language": None,
            "age_rating": None,
            "catalog_number": None,
            "release_status": None,
            "variant_name": None,
            "barcode": None,
            "cover_image_url": None,
            "thumbnail_image_url": None,
        }
        if "title" in update_data and payload.title is not None:
            item.title = payload.title
        if "item_number" in update_data:
            item.item_number = payload.item_number
        if "synopsis" in update_data:
            item.synopsis = payload.synopsis
        if "page_count" in update_data:
            item.page_count = payload.page_count
        if "runtime_minutes" in update_data:
            item.runtime_minutes = payload.runtime_minutes
        item.sort_key = self._sort_key_builder(item.kind, item.title, item.item_number)

        edition = self._primary_edition_model(item)
        physical_format = None
        if "physical_format" in update_data:
            physical_format = self._validated_physical_format(
                item.kind,
                payload.physical_format,
            )
        if edition is not None:
            edition_metadata = dict(edition.metadata_json or {})
            normalized_metadata = dict(edition_metadata.get("normalized") or {})
            before["edition_title"] = edition.title
            before["publisher"] = self._organization_name(item, "publisher") or edition.publisher
            before["release_date"] = edition.release_date
            before["imprint"] = self._organization_name(item, "imprint") or edition.imprint
            before["subtitle"] = edition.subtitle
            before["series_group"] = edition.series_group
            before["country"] = edition.region
            before["language"] = edition.language
            before["age_rating"] = edition.age_rating
            before["catalog_number"] = edition.catalog_number
            before["release_status"] = edition.release_status
            if "edition_title" in update_data:
                edition.title = payload.edition_title
            if "publisher" in update_data:
                edition.publisher = payload.publisher
            if "release_date" in update_data:
                edition.release_date = payload.release_date
            if "imprint" in update_data:
                edition.imprint = payload.imprint
            if "series_group" in update_data:
                edition.series_group = payload.series_group
            if "subtitle" in update_data:
                edition.subtitle = payload.subtitle
            if "country" in update_data:
                edition.region = payload.country
            if "language" in update_data:
                edition.language = payload.language
            if "age_rating" in update_data:
                edition.age_rating = payload.age_rating
            if "catalog_number" in update_data:
                edition.catalog_number = payload.catalog_number
            if "release_status" in update_data:
                edition.release_status = payload.release_status
            cleaned_metadata = set_normalized_metadata(edition_metadata, normalized_metadata)
            if cleaned_metadata != dict(edition.metadata_json or {}):
                edition.metadata_json = cleaned_metadata
            if physical_format is not None:
                self._apply_physical_format_to_edition(edition, physical_format)
            if "publisher" in update_data:
                await self._replace_item_organization_link(item.id, "publisher", payload.publisher)
            if "imprint" in update_data:
                await self._replace_item_organization_link(item.id, "imprint", payload.imprint)

        variant = self._primary_variant_model(item)
        if variant is not None:
            before["variant_name"] = variant.name
            before["barcode"] = variant.barcode
            before["cover_image_url"] = variant.cover_image_url
            before["thumbnail_image_url"] = variant.thumbnail_image_url
            if "variant_name" in update_data and payload.variant_name is not None:
                variant.name = payload.variant_name
            if "barcode" in update_data:
                variant.barcode = payload.barcode
            if "cover_image_url" in update_data:
                variant.cover_image_url = payload.cover_image_url
                variant.metadata_json = self._metadata_with_cover(
                    variant.metadata_json,
                    payload.cover_image_url,
                )
            if "thumbnail_image_url" in update_data:
                variant.thumbnail_image_url = payload.thumbnail_image_url
            if physical_format is not None:
                self._apply_physical_format_to_variant(variant, physical_format)

        metadata = dict(item.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        item.metadata_json = metadata
        self._audit_recorder(
            action="metadata.correction",
            entity_type="item",
            entity_id=item.id,
            details={
                "kind": item.kind,
                "fields": sorted(update_data.keys()),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()
        loaded_item = await MetadataRepository(self.db).get_item(item.id)
        if loaded_item:
            await SearchClient().index_documents_best_effort([item_search_document(loaded_item)])
        return await self._item_response_loader(loaded_item)

    async def update_series_tags(
        self,
        series_id: UUID,
        payload: AdminSeriesTagsUpdateRequest,
    ) -> SeriesResponse:
        series = await self.db.get(Series, series_id)
        if series is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="series_not_found",
                detail="Series not found",
            )

        before = await self._entity_tag_names("series", series.id, self._series_tag_kind(series.kind))
        normalized_tags = self._normalize_admin_tags(payload.tags)
        await self._replace_entity_tags(
            entity_type="series",
            entity_id=series.id,
            tag_kind=self._series_tag_kind(series.kind),
            names=normalized_tags,
        )

        metadata = dict(series.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = ["tags"]
        series.metadata_json = metadata
        self._audit_recorder(
            action="metadata.series_tags_update",
            entity_type="series",
            entity_id=series.id,
            details={
                "kind": series.kind,
                "fields": ["tags"],
                "before": {"tags": before},
                "after": {"tags": normalized_tags},
            },
        )
        await self.db.commit()

        from app.services.metadata import MetadataService

        return await MetadataService(self.db).get_series(series.id)

    async def update_bundle_release(
        self,
        bundle_release_id: UUID,
        payload: AdminBundleReleaseCorrectionRequest,
    ) -> BundleReleaseDetailResponse:
        bundle = await MetadataRepository(self.db).get_bundle_release(bundle_release_id)
        if bundle is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="bundle_release_not_found",
                detail="Bundle release not found",
            )
        update_data = payload.model_dump(exclude_unset=True)
        bundle_items = list(bundle.items or [])
        before = {
            "title": bundle.title,
            "bundle_type": bundle.bundle_type,
            "format": bundle.format,
            "variant_type": bundle.variant_type,
            "packaging_type": bundle.packaging_type,
            "region": bundle.region,
            "language": bundle.language,
            "publisher": bundle.publisher,
            "sku": bundle.sku,
            "barcode": bundle.barcode,
            "release_date": bundle.release_date,
            "cover_image_url": bundle.cover_image_url,
            "thumbnail_image_url": bundle.thumbnail_image_url,
            "primary_item_id": bundle.primary_item_id,
            "members": [
                {
                    "id": member.id,
                    "item_id": member.item_id,
                    "role": member.role,
                    "sequence_number": member.sequence_number,
                    "disc_number": member.disc_number,
                    "disc_label": member.disc_label,
                    "quantity": member.quantity,
                    "is_primary": member.is_primary,
                }
                for member in sorted(bundle_items, key=bundle_release_member_sort_key)
            ],
        }

        for field in (
            "title",
            "bundle_type",
            "format",
            "variant_type",
            "packaging_type",
            "region",
            "language",
            "publisher",
            "sku",
            "barcode",
            "release_date",
            "cover_image_url",
            "thumbnail_image_url",
        ):
            if field in update_data:
                setattr(bundle, field, update_data[field])

        affected_item_ids = {member.item_id for member in bundle_items}
        if "members" in update_data:
            members_payload = payload.members or []
            if not members_payload:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="bundle_members_required",
                    detail="Bundle release updates must keep at least one member",
                )
            existing_members = {member.id: member for member in bundle_items}
            payload_existing_ids = [member.id for member in members_payload if member.id is not None]
            if len(payload_existing_ids) != len(set(payload_existing_ids)):
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="duplicate_bundle_member_reference",
                    detail="Bundle member updates cannot reference the same membership row twice",
                )
            primary_members = [member for member in members_payload if member.is_primary]
            if len(primary_members) != 1:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="invalid_bundle_primary_member",
                    detail="Exactly one bundle member must be marked as primary",
                )
            requested_item_ids = {
                member.item_id for member in members_payload if member.item_id is not None
            }
            requested_item_ids.update(
                existing_members[member_id].item_id
                for member_id in payload_existing_ids
                if member_id in existing_members
            )
            if not requested_item_ids:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="bundle_members_required",
                    detail="Bundle release updates must keep at least one member",
                )
            item_result = await self.db.execute(
                select(Item).where(Item.id.in_(requested_item_ids))
            )
            available_items = {item.id: item for item in item_result.scalars().all()}
            missing_item_ids = sorted(
                str(item_id) for item_id in requested_item_ids if item_id not in available_items
            )
            if missing_item_ids:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="bundle_member_item_not_found",
                    detail=f"Bundle member items not found: {', '.join(missing_item_ids)}",
                )

            kept_member_ids: set[UUID] = set()
            member_keys: set[tuple[UUID, str, int | None, int | None]] = set()
            primary_member_model: BundleReleaseItem | None = None
            for member_payload in members_payload:
                if member_payload.id is not None:
                    member = existing_members.get(member_payload.id)
                    if member is None:
                        raise ApiHTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="bundle_member_mismatch",
                            detail="Bundle member updates must reference valid membership rows",
                        )
                    kept_member_ids.add(member.id)
                    if member_payload.item_id is not None and member_payload.item_id != member.item_id:
                        member.item_id = member_payload.item_id
                        member.item = available_items[member_payload.item_id]
                else:
                    if member_payload.item_id is None:
                        raise ApiHTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            code="bundle_member_item_required",
                            detail="New bundle members must include item_id",
                        )
                    member = BundleReleaseItem(
                        bundle_release_id=bundle.id,
                        item_id=member_payload.item_id,
                        item=available_items[member_payload.item_id],
                    )
                    self.db.add(member)
                    if bundle.items is None:
                        bundle.items = []
                    bundle.items.append(member)
                member.role = member_payload.role
                member.sequence_number = member_payload.sequence_number
                member.disc_number = member_payload.disc_number
                member.disc_label = member_payload.disc_label
                member.quantity = member_payload.quantity
                member.is_primary = member_payload.is_primary
                member_key = (
                    member.item_id,
                    member.role,
                    member.disc_number,
                    member.sequence_number,
                )
                if member_key in member_keys:
                    raise ApiHTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        code="duplicate_bundle_member",
                        detail="Bundle members must remain unique by item, role, disc, and sequence",
                    )
                member_keys.add(member_key)
                if member.is_primary:
                    primary_member_model = member

            for member_id, member in existing_members.items():
                if member_id in kept_member_ids:
                    continue
                if member in bundle.items:
                    bundle.items.remove(member)
                await self.db.delete(member)

            if primary_member_model is None:
                raise ApiHTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    code="invalid_bundle_primary_member",
                    detail="Exactly one bundle member must be marked as primary",
                )
            primary_member = primary_member_model
            bundle.primary_item_id = primary_member.item_id
            bundle.primary_item = primary_member.item

        metadata = dict(bundle.metadata_json or {})
        metadata["admin_corrected_at"] = datetime.now(UTC).isoformat()
        metadata["admin_corrected_fields"] = sorted(update_data.keys())
        bundle.metadata_json = metadata
        self._audit_recorder(
            action="metadata.bundle_correction",
            entity_type="bundle_release",
            entity_id=bundle.id,
            details={
                "kind": bundle.kind,
                "fields": sorted(update_data.keys()),
                "before": before,
                "after": update_data,
            },
        )
        await self.db.commit()

        loaded_bundle = await MetadataRepository(self.db).get_bundle_release(bundle.id)
        if loaded_bundle is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="bundle_release_not_found",
                detail="Bundle release not found after update",
            )
        await self._reindex_items(affected_item_ids | {member.item_id for member in loaded_bundle.items})
        return bundle_release_detail_from_model(loaded_bundle)

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
        edition: Edition,
        physical_format: PhysicalFormatConfig,
    ) -> None:
        edition.format = physical_format.label
        edition.metadata_json = self._metadata_with_physical_format(
            edition.metadata_json,
            physical_format,
        )

    def _apply_physical_format_to_variant(
        self,
        variant: Variant,
        physical_format: PhysicalFormatConfig,
    ) -> None:
        variant.variant_type = physical_format.variant_type
        variant.metadata_json = self._metadata_with_physical_format(
            variant.metadata_json,
            physical_format,
        )

    def _metadata_with_physical_format(
        self,
        metadata_json: dict[str, Any] | None,
        physical_format: PhysicalFormatConfig,
    ) -> dict[str, Any]:
        return merge_normalized_metadata(
            metadata_json,
            {
                "physical_format": physical_format.id,
                "physical_format_label": physical_format.label,
                "physical_format_media_family": physical_format.media_family,
                "physical_format_variant_type": physical_format.variant_type,
            },
        )

    def _metadata_with_cover(
        self,
        metadata_json: dict[str, Any] | None,
        source_url: str | None,
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
        )

    def _primary_edition_model(self, item: Item) -> Edition | None:
        editions = list(item.editions or [])
        return editions[0] if editions else None

    def _primary_variant_model(self, item: Item) -> Variant | None:
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
        from app.models.canonical import EntityTag, Tag

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
        from app.models.canonical import EntityTag, Tag

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

    def _series_tag_kind(self, kind: ItemKind) -> str:
        return f"series_tag:{kind.value}"

    def _organization_name(self, item: Item, role: str) -> str | None:
        for link in list(getattr(item, "organization_links", []) or []):
            if getattr(link, "role", None) != role:
                continue
            organization = getattr(link, "organization", None)
            name = getattr(organization, "name", None)
            if name:
                return str(name)
        return None

    async def _replace_item_organization_link(
        self,
        item_id: UUID,
        role: str,
        name: str | None,
    ) -> None:
        existing = list(
            (
                await self.db.execute(
                    select(EntityOrganization).where(
                        EntityOrganization.entity_type == "item",
                        EntityOrganization.entity_id == item_id,
                        EntityOrganization.role == role,
                    )
                )
            ).scalars()
        )
        for link in existing:
            await self.db.delete(link)
        value = " ".join(str(name or "").split()).strip()
        if not value:
            await self.db.flush()
            return
        organization = await self.db.scalar(select(Organization).where(Organization.name == value))
        if organization is None:
            organization = Organization(name=value)
            self.db.add(organization)
            await self.db.flush()
        self.db.add(
            EntityOrganization(
                entity_type="item",
                entity_id=item_id,
                organization_id=organization.id,
                role=role,
            )
        )
        await self.db.flush()