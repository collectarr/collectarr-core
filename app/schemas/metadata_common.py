from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field

from app.catalog.grouping_models import GroupingModel
from app.models.base import ItemKind
from app.models.partial_date import PartialDateValue


class PhysicalFormatResponse(BaseModel):
    id: str
    label: str
    media_family: str
    variant_type: str
    aliases: list[str] = Field(default_factory=list)


class MediaTypeResponse(BaseModel):
    kind: ItemKind
    singular_label: str
    plural_label: str
    route_segments: list[str]
    is_top_level: bool = True
    grouping_model: GroupingModel
    physical_formats: list[PhysicalFormatResponse] = Field(default_factory=list)


class MediaCatalogResponse(BaseModel):
    default_kind: ItemKind
    media_types: list[MediaTypeResponse]


class MetadataNormalizedManifestResponse(BaseModel):
    schema_version: int
    common_fields: list[str]
    kind_fields: dict[ItemKind, list[str]]
    value_types: dict[str, str]


class MetadataFieldOwnershipResponse(BaseModel):
    """The authoritative source boundary for one kind-specific field view."""

    scope: str
    source_entity_type: str
    source_table: str
    write_target: str


class MetadataFieldSpecResponse(BaseModel):
    """A single editable canonical metadata field, rendered from the registry."""

    key: str
    value_type: str
    label: str
    common: bool
    typed: bool
    normalized: bool
    editable: bool
    section: str
    input: str
    kinds: list[ItemKind] = Field(default_factory=list)
    ownership_by_kind: dict[ItemKind, MetadataFieldOwnershipResponse] = Field(
        default_factory=dict
    )


class MetadataFieldSchemaResponse(BaseModel):
    """The unified field schema consumed by the admin + app edit surfaces."""

    schema_version: int
    fields: list[MetadataFieldSpecResponse]
    kind_fields: dict[ItemKind, list[str]]
    sections: list[str] = Field(default_factory=list)


class EpisodeResponse(BaseModel):
    episode_number: int
    title: str
    overview: str | None = None
    air_date: date | None = None
    air_date_parts: PartialDateValue | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None


class SeasonResponse(BaseModel):
    season_number: int
    title: str
    overview: str | None = None
    air_date: date | None = None
    air_date_parts: PartialDateValue | None = None
    episode_count: int | None = None
    poster_url: str | None = None
    episodes: list[EpisodeResponse] = Field(default_factory=list)


class StoryArcResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    publisher: str | None = None
    start_date: date | None = None
    start_date_parts: PartialDateValue | None = None
    end_date: date | None = None
    end_date_parts: PartialDateValue | None = None
    item_count: int = 0


class StoryArcFacetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    publisher: str | None = None
    start_date: date | None = None
    start_date_parts: PartialDateValue | None = None
    end_date: date | None = None
    end_date_parts: PartialDateValue | None = None
    item_count: int = 0
    entity_ids: list[UUID] = Field(default_factory=list)


class StoryArcItemResponse(BaseModel):
    story_arc_id: UUID
    entity_type: str
    entity_id: UUID
    ordinal: int | None = None
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None


class CreatorResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    image_url: str | None = None
    item_count: int = 0


class CreatorFacetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    image_url: str | None = None
    item_count: int = 0
    entity_ids: list[UUID] = Field(default_factory=list)
    role_counts: dict[str, int] = Field(default_factory=dict)


class CreatorCreditResponse(BaseModel):
    creator_id: UUID
    item_id: UUID
    role: str
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None


class CharacterResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    image_url: str | None = None
    first_appearance_entity_type: str | None = None
    first_appearance_entity_id: UUID | None = None
    appearance_count: int = 0


class CharacterFacetResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    image_url: str | None = None
    item_count: int = 0
    entity_ids: list[UUID] = Field(default_factory=list)
    role_counts: dict[str, int] = Field(default_factory=dict)

class FacetEntityIdsRequest(BaseModel):
    entity_ids: list[UUID] = Field(default_factory=list)


class CharacterAppearanceResponse(BaseModel):
    character_id: UUID
    entity_type: str
    entity_id: UUID
    role: str
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None
