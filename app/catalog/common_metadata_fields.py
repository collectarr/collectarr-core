"""Shared source-neutral Catalog Item metadata field specifications."""

from app.catalog.metadata_field_spec import (
    CATALOG_KINDS,
    INPUT_DATE,
    INPUT_LIST,
    INPUT_MULTILINE,
    SECTION_ARTWORK,
    SECTION_INTERNAL,
    SECTION_ITEM,
    SECTION_PUBLISHING,
    SECTION_REGIONAL,
    SECTION_RELATIONS,
    SECTION_TECHNICAL,
    TRAILER_KINDS,
    VALUE_TYPE_LINK_LIST,
    VALUE_TYPE_PARTIAL_DATE,
    VALUE_TYPE_STRING,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

# --- Normalized common fields (shared by every kind) -------------------------
# Internal cover/format bookkeeping that is never edited by hand.
_INTERNAL_COMMON_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec(
        "physical_format_label",
        VALUE_TYPE_STRING,
        "Physical format label",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "physical_format_media_family",
        VALUE_TYPE_STRING,
        "Physical format media family",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "physical_format_variant_type",
        VALUE_TYPE_STRING,
        "Physical format variant type",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "format_templateimage",
        VALUE_TYPE_STRING,
        "Format template image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "format_scaledimage",
        VALUE_TYPE_STRING,
        "Format scaled image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "country_scaledimage",
        VALUE_TYPE_STRING,
        "Country scaled image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "language_scaledimage",
        VALUE_TYPE_STRING,
        "Language scaled image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "audiencerating_templateimage",
        VALUE_TYPE_STRING,
        "Audience rating template image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "region_scaledimage",
        VALUE_TYPE_STRING,
        "Region scaled image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "audio_templateimage",
        VALUE_TYPE_STRING,
        "Audio template image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "associated_image_id",
        VALUE_TYPE_STRING,
        "Associated image",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "cover_delivery_url",
        VALUE_TYPE_STRING,
        "Cover delivery URL",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "cover_policy",
        VALUE_TYPE_STRING,
        "Cover policy",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "cover_source_url",
        VALUE_TYPE_STRING,
        "Cover source URL",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "cover_status",
        VALUE_TYPE_STRING,
        "Cover status",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
    MetadataFieldSpec(
        "cover_storage",
        VALUE_TYPE_STRING,
        "Cover storage",
        kinds=CATALOG_KINDS,
        editable=False,
        section=SECTION_INTERNAL,
    ),
)

# Editable normalized common fields.
_EDITABLE_COMMON_FIELDS: tuple[MetadataFieldSpec, ...] = (
    MetadataFieldSpec(
        "physical_format",
        VALUE_TYPE_STRING,
        "Physical format",
        section=SECTION_PUBLISHING,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
)


# --- Editorial / release fields (not part of normalization) ------------------
# These are source-neutral fields on one concrete Catalog Item. They map to
# canonical root fields rather than normalized metadata JSON.
_EDITORIAL_FIELDS: tuple[MetadataFieldSpec, ...] = (
    # Item identity.
    MetadataFieldSpec(
        "title", VALUE_TYPE_STRING, "Title", section=SECTION_ITEM, kinds=CATALOG_KINDS
    ),
    MetadataFieldSpec(
        "original_title",
        VALUE_TYPE_STRING,
        "Original title",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "localized_title",
        VALUE_TYPE_STRING,
        "Localized title",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "title_extension",
        VALUE_TYPE_STRING,
        "Title extension",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "sort_key",
        VALUE_TYPE_STRING,
        "Sort key",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "search_aliases",
        VALUE_TYPE_STRING_LIST,
        "Search aliases",
        section=SECTION_ITEM,
        input=INPUT_LIST,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "item_number",
        VALUE_TYPE_STRING,
        "Item number",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "series_title",
        VALUE_TYPE_STRING,
        "Series title",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "edition_title",
        VALUE_TYPE_STRING,
        "Edition title",
        section=SECTION_ITEM,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "release_date",
        VALUE_TYPE_PARTIAL_DATE,
        "Release date",
        section=SECTION_ITEM,
        input=INPUT_DATE,
        kinds=CATALOG_KINDS,
    ),
    # Publishing.
    MetadataFieldSpec(
        "publisher",
        VALUE_TYPE_STRING,
        "Publisher",
        section=SECTION_PUBLISHING,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "subtitle", VALUE_TYPE_STRING, "Subtitle", section=SECTION_PUBLISHING, kinds=CATALOG_KINDS
    ),
    MetadataFieldSpec(
        "barcode", VALUE_TYPE_STRING, "Barcode", section=SECTION_PUBLISHING, kinds=CATALOG_KINDS
    ),
    MetadataFieldSpec(
        "variant_name",
        VALUE_TYPE_STRING,
        "Primary variant",
        section=SECTION_PUBLISHING,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    # Technical / release.
    MetadataFieldSpec(
        "catalog_number",
        VALUE_TYPE_STRING,
        "Catalog number",
        section=SECTION_TECHNICAL,
        kinds=CATALOG_KINDS,
    ),
    MetadataFieldSpec(
        "release_status",
        VALUE_TYPE_STRING,
        "Release status",
        section=SECTION_TECHNICAL,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    # Regional.
    MetadataFieldSpec(
        "country", VALUE_TYPE_STRING, "Country", section=SECTION_REGIONAL, kinds=CATALOG_KINDS
    ),
    MetadataFieldSpec(
        "language",
        VALUE_TYPE_STRING,
        "Language",
        section=SECTION_REGIONAL,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "age_rating",
        VALUE_TYPE_STRING,
        "Age rating",
        section=SECTION_REGIONAL,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "audience_rating",
        VALUE_TYPE_STRING,
        "Audience rating",
        section=SECTION_REGIONAL,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "series_tags",
        VALUE_TYPE_STRING_LIST,
        "Series tags",
        section=SECTION_REGIONAL,
        input=INPUT_LIST,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    # Artwork & copy.
    MetadataFieldSpec(
        "cover_image_url",
        VALUE_TYPE_STRING,
        "Cover URL",
        section=SECTION_ARTWORK,
        kinds=CATALOG_KINDS,
    ),
    MetadataFieldSpec(
        "thumbnail_image_url",
        VALUE_TYPE_STRING,
        "Thumbnail URL",
        section=SECTION_ARTWORK,
        kinds=CATALOG_KINDS,
    ),
    MetadataFieldSpec(
        "synopsis",
        VALUE_TYPE_STRING,
        "Synopsis",
        section=SECTION_ARTWORK,
        input=INPUT_MULTILINE,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "plot_summary",
        VALUE_TYPE_STRING,
        "Plot summary",
        section=SECTION_ARTWORK,
        input=INPUT_MULTILINE,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    MetadataFieldSpec(
        "plot_description",
        VALUE_TYPE_STRING,
        "Plot description",
        section=SECTION_ARTWORK,
        input=INPUT_MULTILINE,
        kinds=CATALOG_KINDS - {ItemKind.music},
    ),
    # Relations & lists.
    MetadataFieldSpec(
        "trailer_urls",
        VALUE_TYPE_LINK_LIST,
        "Trailer URLs",
        section=SECTION_RELATIONS,
        input=INPUT_MULTILINE,
        kinds=TRAILER_KINDS,
    ),
    MetadataFieldSpec(
        "external_links",
        VALUE_TYPE_LINK_LIST,
        "External links",
        section=SECTION_RELATIONS,
        input=INPUT_MULTILINE,
        kinds=CATALOG_KINDS,
    ),
)
