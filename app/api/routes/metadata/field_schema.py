from __future__ import annotations

from fastapi import APIRouter, Query

from app.catalog.media_types import top_level_media_types
from app.catalog.metadata_fields import METADATA_FIELDS, MetadataFieldSpec, fields_for_kind
from app.catalog.metadata_legacy_projection import warn_if_legacy_projection_used
from app.catalog.physical_formats import PhysicalFormatConfig
from app.metadata_normalized import NORMALIZED_SCHEMA_VERSION, normalized_metadata_manifest
from app.models.base import ItemKind
from app.schemas import (
    MediaCatalogResponse,
    MediaTypeResponse,
    MetadataFieldSchemaResponse,
    MetadataFieldSpecResponse,
    MetadataNormalizedManifestResponse,
    PhysicalFormatResponse,
    public_item_kind,
)

router = APIRouter(tags=["metadata"])


def _field_spec_response(spec: MetadataFieldSpec) -> MetadataFieldSpecResponse:
    return MetadataFieldSpecResponse(
        key=spec.key,
        value_type=spec.value_type,
        label=spec.label,
        common=spec.common,
        typed=spec.typed,
        normalized=spec.normalized,
        editable=spec.editable,
        scope=spec.scope,
        write_target=spec.write_target,
        section=spec.section,
        input=spec.input,
        kinds=sorted((kind for kind in spec.kinds), key=lambda k: k.value),
    )


@router.get("/metadata/media-types", response_model=MediaCatalogResponse)
async def media_type_catalog() -> MediaCatalogResponse:
    return MediaCatalogResponse(
        default_kind=ItemKind.comic,
        media_types=[_media_type_response(config) for config in top_level_media_types],
    )


@router.get("/metadata/normalized-manifest", response_model=MetadataNormalizedManifestResponse)
async def metadata_normalized_manifest() -> MetadataNormalizedManifestResponse:
    payload = normalized_metadata_manifest()
    kind_fields = {ItemKind(kind): fields for kind, fields in payload["kind_fields"].items()}
    return MetadataNormalizedManifestResponse(
        schema_version=payload["schema_version"],
        common_fields=payload["common_fields"],
        kind_fields=kind_fields,
        value_types=payload["value_types"],
    )


@router.get("/metadata/field-schema", response_model=MetadataFieldSchemaResponse)
async def metadata_field_schema(
    editable_only: bool = Query(default=True),
) -> MetadataFieldSchemaResponse:
    specs = [spec for spec in METADATA_FIELDS if spec.editable or not editable_only]
    warn_if_legacy_projection_used("GET /metadata/field-schema", (spec.key for spec in specs))
    fields = [_field_spec_response(spec) for spec in specs]
    kind_fields = {
        kind: [spec.key for spec in fields_for_kind(kind, editable_only=editable_only)]
        for kind in ItemKind
    }
    sections: list[str] = []
    for spec in specs:
        if spec.section not in sections:
            sections.append(spec.section)
    return MetadataFieldSchemaResponse(
        schema_version=NORMALIZED_SCHEMA_VERSION,
        fields=fields,
        kind_fields=kind_fields,
        sections=sections,
    )


def _media_type_response(config) -> MediaTypeResponse:
    return MediaTypeResponse(
        kind=public_item_kind(config.kind),
        singular_label=config.singular_label,
        plural_label=config.plural_label,
        route_segments=list(config.route_segments),
        default_provider=config.default_provider,
        providers=list(config.providers),
        provider_search_policy=config.provider_search_policy,
        is_top_level=config.is_top_level,
        grouping_model=config.grouping_model,
        physical_formats=[_physical_format_response(row) for row in config.physical_formats],
    )


def _physical_format_response(config: PhysicalFormatConfig) -> PhysicalFormatResponse:
    return PhysicalFormatResponse(
        id=config.id,
        label=config.label,
        media_family=config.media_family,
        variant_type=config.variant_type,
        aliases=list(config.aliases),
    )
