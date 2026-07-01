from __future__ import annotations

from datetime import date
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.catalog.grouping_models import GroupingModel
from app.models.base import ExternalProvider, ItemKind


class ProviderSearchResultResponse(BaseModel):
    provider: ExternalProvider
    provider_item_id: str
    title: str
    kind: ItemKind
    summary: str | None = None
    image_url: str | None = None
    candidate_type: str | None = None
    series_title: str | None = None
    issue_number: str | None = None
    volume_start_year: int | None = None
    variant_name: str | None = None
    is_variant: bool | None = None
    issue_count: int | None = None
    publisher: str | None = None
    character_preview: list[str] = Field(default_factory=list)
    story_arc_preview: list[str] = Field(default_factory=list)


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
    default_provider: ExternalProvider | None = None
    providers: list[ExternalProvider] = Field(default_factory=list)
    provider_search_policy: str
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


class MetadataFieldSchemaResponse(BaseModel):
    """The unified field schema consumed by the admin + app edit surfaces."""

    schema_version: int
    fields: list[MetadataFieldSpecResponse]
    kind_fields: dict[ItemKind, list[str]]
    sections: list[str] = Field(default_factory=list)


class MetadataProposalCreate(BaseModel):
    provider: ExternalProvider
    provider_item_id: str | None = Field(default=None, max_length=255)
    query: str = Field(min_length=1, max_length=255)
    title: str | None = Field(default=None, max_length=255)
    summary: str | None = None
    image_url: str | None = Field(default=None, max_length=1024)
    metadata_payload: dict[str, Any] | None = None


class MetadataProposalResponse(BaseModel):
    id: UUID
    provider: ExternalProvider
    provider_item_id: str | None
    query: str
    title: str | None
    metadata_payload: dict[str, Any] | None = None
    status: str

    model_config = {"from_attributes": True}


class EpisodeResponse(BaseModel):
    episode_number: int
    title: str
    provider_item_id: str | None = None
    overview: str | None = None
    air_date: date | None = None
    runtime_minutes: int | None = None
    page_count: int | None = None


class SeasonResponse(BaseModel):
    season_number: int
    title: str
    provider_item_id: str | None = None
    overview: str | None = None
    air_date: date | None = None
    episode_count: int | None = None
    poster_url: str | None = None
    episodes: list[EpisodeResponse] = Field(default_factory=list)


class StoryArcResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    publisher: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    item_count: int = 0


class StoryArcFacetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    publisher: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    item_count: int = 0
    item_ids: list[UUID] = Field(default_factory=list)


class StoryArcItemResponse(BaseModel):
    story_arc_id: UUID
    item_id: UUID
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
    api_detail_url: str | None = None
    site_detail_url: str | None = None
    item_count: int = 0


class CreatorFacetResponse(BaseModel):
    id: UUID
    name: str
    description: str | None = None
    image_url: str | None = None
    item_count: int = 0
    item_ids: list[UUID] = Field(default_factory=list)
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
    first_appearance_item_id: UUID | None = None
    appearance_count: int = 0


class CharacterFacetResponse(BaseModel):
    id: UUID
    name: str
    aliases: list[str] = Field(default_factory=list)
    image_url: str | None = None
    item_count: int = 0
    item_ids: list[UUID] = Field(default_factory=list)
    role_counts: dict[str, int] = Field(default_factory=dict)


class FacetItemIdsRequest(BaseModel):
    item_ids: list[UUID] = Field(default_factory=list)


class CharacterAppearanceResponse(BaseModel):
    character_id: UUID
    item_id: UUID
    role: str
    kind: ItemKind
    title: str
    item_number: str | None = None
    series_title: str | None = None
    volume_name: str | None = None
    cover_image_url: str | None = None
