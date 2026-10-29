from __future__ import annotations

from pydantic import BaseModel, Field

from app.catalog.release_scope import ReleasedCatalogKind


class PhysicalFormatResponse(BaseModel):
    id: str
    label: str
    media_family: str
    variant_type: str
    aliases: list[str] = Field(default_factory=list)


class MediaTypeResponse(BaseModel):
    kind: ReleasedCatalogKind
    singular_label: str
    plural_label: str
    route_segments: list[str]
    is_top_level: bool = True
    physical_formats: list[PhysicalFormatResponse] = Field(default_factory=list)


class MediaCatalogResponse(BaseModel):
    default_kind: ReleasedCatalogKind
    media_types: list[MediaTypeResponse]


class MetadataNormalizedManifestResponse(BaseModel):
    schema_version: int
    common_fields: list[str]
    kind_fields: dict[ReleasedCatalogKind, list[str]]
    value_types: dict[str, str]


class MetadataFieldSpecResponse(BaseModel):
    """A single editable canonical metadata field, rendered from the registry."""

    key: str
    value_type: str
    label: str
    editable: bool
    section: str
    input: str
    kinds: list[ReleasedCatalogKind] = Field(default_factory=list)


class MetadataFieldSchemaResponse(BaseModel):
    """The unified field schema consumed by the admin + app edit surfaces."""

    schema_version: int
    fields: list[MetadataFieldSpecResponse]
    kind_fields: dict[ReleasedCatalogKind, list[str]]
    sections: list[str] = Field(default_factory=list)
