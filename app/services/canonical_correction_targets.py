from __future__ import annotations

import hashlib
import json
from datetime import date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.catalog.kind_registry import CATALOG_KINDS_BY_ID, catalog_kind_for
from app.catalog.metadata_field_spec import VALUE_TYPE_STRING_LIST
from app.catalog.metadata_fields import (
    canonical_correction_field_spec,
    canonical_entity_type_for_scope,
    fields_for_kind,
)
from app.core.errors import ApiHTTPException
from app.models.base import ItemKind
from app.models.partial_date import PartialDateValue
from app.schemas.canonical_corrections import (
    CanonicalCorrectionFieldResponse,
    CanonicalCorrectionTargetResponse,
)

_MODEL_BY_ENTITY_TYPE: dict[str, type[Any]] = {
    definition.entity_type: definition.model for definition in CATALOG_KINDS_BY_ID.values()
}


def _json_value(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(child) for child in value]
    return value


def _canonical_json(value: Any) -> str:
    return json.dumps(_json_value(value), sort_keys=True, separators=(",", ":"))


def canonical_snapshot_hash(
    *,
    entity_type: str,
    entity_id: UUID,
    scope: str,
    revision: str,
    fields: dict[str, Any],
) -> str:
    payload = {
        "entity_type": entity_type,
        "entity_id": str(entity_id),
        "scope": scope,
        "revision": revision,
        "fields": fields,
    }
    digest = hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def _column_for_field(entity_type: str, key: str, model: type[Any]) -> str | None:
    columns = inspect(model).columns
    direct = {
        "title": ("title", "display_title"),
        "sort_title": ("sort_title",),
        "original_title": ("original_title",),
        "localized_title": ("localized_title",),
        "title_extension": ("title_extension",),
        "sort_key": ("sort_key", "sort_title"),
        "item_number": (
            "issue_number",
            "volume_number",
            "season_number",
            "episode_number",
            "chapter_number",
        ),
        "edition_title": ("display_title", "title"),
        "physical_format": ("physical_format", "format"),
        "format": ("format",),
        "release_date": ("release_date", "publication_date"),
        "original_release_date": ("original_release_date",),
        "publisher": ("publisher",),
        "label": ("label",),
        "packaging": ("packaging",),
        "imprint": ("imprint",),
        "subtitle": ("subtitle",),
        "artist": ("artist",),
        "genres": ("genres",),
        "extra": ("extra",),
        "box_set": ("box_set",),
        "external_links": ("external_links",),
        "cover_image_url": ("cover_image_url",),
        "thumbnail_image_url": ("thumbnail_image_url",),
        "barcode": ("barcode",),
        "variant_name": ("variant_name",),
        "page_count": ("page_count",),
        "catalog_number": ("catalog_number",),
        "release_status": ("release_status", "status"),
        "country": ("country", "region", "region_code", "country_code"),
        "language": ("language", "original_language"),
        "age_rating": ("age_rating",),
        "audience_rating": ("audience_rating",),
    }
    for candidate in direct.get(key, ()):
        if candidate in columns:
            return candidate
    if key == "identifiers" and "details" in columns:
        return None
    if "details" in columns:
        return "details"
    return None


def _music_partial_date_parts(entity: Any, key: str) -> dict[str, int] | None:
    return _parse_partial_date_parts(getattr(entity, key, None))


def _parse_partial_date_parts(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict):
        return None
    if set(value) - {"year", "month", "day"}:
        return None
    if any(not isinstance(part, int) or isinstance(part, bool) for part in value.values()):
        return None
    try:
        parsed = PartialDateValue.model_validate(value)
    except ValueError:
        return None
    return None if parsed.is_empty else parsed.model_dump(exclude_none=True)


class CanonicalField:
    def __init__(
        self,
        key: str,
        label: str,
        value_type: str,
        column: str,
        *,
        json_key: str | None = None,
    ) -> None:
        self.key = key
        self.label = label
        self.value_type = value_type
        self.column = column
        self.json_key = json_key


class CanonicalCorrectionTargetService:
    """Resolve and mutate exact source-neutral canonical targets."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    @staticmethod
    def entity_type_for_scope(kind: ItemKind, scope: str) -> str:
        entity_type = canonical_entity_type_for_scope(kind, scope)
        if entity_type is None:
            raise ApiHTTPException(
                status_code=422,
                code="unknown_canonical_scope",
                detail=f"No canonical entity type exists for {kind.value}/{scope}.",
            )
        return entity_type

    async def snapshot(
        self,
        *,
        kind: ItemKind,
        entity_type: str,
        entity_id: UUID,
        scope: str,
        lock: bool = False,
    ) -> CanonicalCorrectionTargetResponse:
        model = self._model_for_target(kind, entity_type, scope)
        if lock:
            entity = (
                await self.db.execute(select(model).where(model.id == entity_id).with_for_update())
            ).scalar_one_or_none()
        else:
            entity = await self.db.get(model, entity_id)
        if entity is None:
            raise ApiHTTPException(
                status_code=404,
                code="canonical_target_not_found",
                detail=f"Canonical target {entity_type}/{entity_id} was not found.",
            )
        fields = self._field_specs(kind, entity_type, scope, model)
        values = {
            field.key: (
                _music_partial_date_parts(entity, field.key)
                if entity_type == "catalog_music_item"
                and field.key in {"release_date", "original_release_date"}
                else _json_value(
                    getattr(entity, field.column).get(field.json_key)
                    if field.json_key is not None
                    else getattr(entity, field.column)
                )
            )
            for field in fields
        }
        revision = self._revision(entity)
        return CanonicalCorrectionTargetResponse(
            kind=kind,
            entity_type=entity_type,
            entity_id=entity_id,
            scope=scope,
            revision=revision,
            hash=canonical_snapshot_hash(
                entity_type=entity_type,
                entity_id=entity_id,
                scope=scope,
                revision=revision,
                fields=values,
            ),
            fields=values,
            field_schema=[
                CanonicalCorrectionFieldResponse(
                    key=field.key,
                    label=field.label,
                    value_type=field.value_type,
                    scope=scope,
                    entity_type=entity_type,
                )
                for field in fields
            ],
        )

    async def current_and_diff(
        self,
        *,
        kind: ItemKind,
        entity_type: str,
        entity_id: UUID,
        scope: str,
        proposed_fields: dict[str, Any],
        lock: bool = False,
    ) -> tuple[CanonicalCorrectionTargetResponse, dict[str, Any]]:
        current = await self.snapshot(
            kind=kind,
            entity_type=entity_type,
            entity_id=entity_id,
            scope=scope,
            lock=lock,
        )
        allowed = {field.key for field in current.field_schema}
        unknown = sorted(set(proposed_fields) - allowed)
        if unknown:
            raise ApiHTTPException(
                status_code=422,
                code="unsupported_canonical_field",
                detail=f"Fields are not writable on {entity_type}: {unknown}",
            )
        diff = {
            key: {"before": current.fields.get(key), "after": value}
            for key, value in proposed_fields.items()
            if _canonical_json(current.fields.get(key)) != _canonical_json(value)
        }
        if not diff:
            raise ApiHTTPException(
                status_code=422,
                code="canonical_correction_noop",
                detail="The proposed canonical values do not change the current target.",
            )
        return current, diff

    async def apply(
        self,
        *,
        kind: ItemKind,
        entity_type: str,
        entity_id: UUID,
        scope: str,
        fields: dict[str, Any],
    ) -> CanonicalCorrectionTargetResponse:
        model = self._model_for_target(kind, entity_type, scope)
        entity = await self.db.get(model, entity_id)
        if entity is None:
            raise ApiHTTPException(
                status_code=404,
                code="canonical_target_not_found",
                detail=f"Canonical target {entity_type}/{entity_id} was not found.",
            )
        specs = {field.key: field for field in self._field_specs(kind, entity_type, scope, model)}
        for key, value in fields.items():
            field = specs.get(key)
            if field is None:
                raise ApiHTTPException(
                    status_code=422,
                    code="unsupported_canonical_field",
                    detail=f"Field '{key}' is not writable on {entity_type}.",
                )
            if field.value_type == VALUE_TYPE_STRING_LIST:
                if value is None:
                    value = []
                elif not isinstance(value, list) or any(
                    not isinstance(entry, str) for entry in value
                ):
                    raise ApiHTTPException(
                        status_code=422,
                        code="invalid_string_list",
                        detail=f"Field '{key}' must be a list of strings.",
                    )
            if entity_type == "catalog_music_item" and key in {
                "release_date",
                "original_release_date",
            }:
                partial_date = _parse_partial_date_parts(value)
                if value is not None and partial_date is None:
                    raise ApiHTTPException(
                        status_code=422,
                        code="invalid_partial_date",
                        detail=f"Field '{key}' must be a partial-date object.",
                    )
                setattr(entity, key, partial_date)
                continue
            if field.json_key is not None:
                details = dict(getattr(entity, field.column) or {})
                details[field.json_key] = _json_value(value)
                setattr(entity, field.column, details)
                continue
            column = getattr(model, field.column).property.columns[0]
            setattr(entity, field.column, self._coerce(value, column))
        await self.db.flush()
        return await self.snapshot(
            kind=kind, entity_type=entity_type, entity_id=entity_id, scope=scope
        )

    def _model_for_target(self, kind: ItemKind, entity_type: str, scope: str) -> type[Any]:
        definition = catalog_kind_for(kind)
        model = _MODEL_BY_ENTITY_TYPE.get(entity_type)
        if model is None or entity_type != definition.entity_type or scope != "catalog_item":
            raise ApiHTTPException(
                status_code=422,
                code="unknown_canonical_target",
                detail=f"Unknown canonical entity type: {entity_type}",
            )
        if not any(
            canonical_correction_field_spec(kind, field.key) is not None
            for field in fields_for_kind(kind, editable_only=True)
        ):
            raise ApiHTTPException(
                status_code=422,
                code="invalid_canonical_correction_target",
                detail=f"{entity_type} is not a canonical writable target for {kind.value}/{scope}.",
            )
        return model

    @staticmethod
    def _field_specs(
        kind: ItemKind, entity_type: str, scope: str, model: type[Any]
    ) -> list[CanonicalField]:
        result: list[CanonicalField] = []
        if scope != "catalog_item" or catalog_kind_for(kind).entity_type != entity_type:
            return result
        for field in fields_for_kind(kind, editable_only=True):
            spec = canonical_correction_field_spec(kind, field.key)
            if spec is None:
                continue
            column = _column_for_field(entity_type, field.key, model)
            if column is not None:
                result.append(
                    CanonicalField(
                        field.key,
                        field.label,
                        field.value_type,
                        column,
                        json_key=(
                            field.key
                            if column == "details" and "details" in inspect(model).columns
                            else None
                        ),
                    )
                )
        return result

    @staticmethod
    def _revision(entity: Any) -> str:
        updated_at = getattr(entity, "updated_at", None)
        if not isinstance(updated_at, datetime):
            raise ApiHTTPException(
                status_code=500,
                code="canonical_target_missing_revision",
                detail="Canonical target does not expose an authoritative revision.",
            )
        return updated_at.isoformat()

    @staticmethod
    def _coerce(value: Any, column: Any) -> Any:
        if value is None:
            return None
        python_type = getattr(column.type, "python_type", None)
        if python_type is date and isinstance(value, str):
            return date.fromisoformat(value)
        if python_type is int and not isinstance(value, bool):
            return int(value)
        if python_type is str:
            return str(value)
        return value
