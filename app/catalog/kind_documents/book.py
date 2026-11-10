"""Book Catalog Item fields and contained edition values."""

from dataclasses import replace

from app.catalog.document_shape import (
    BOOLEAN,
    CHARACTER,
    INTEGER,
    PARTIAL_DATE,
    PERSON,
    STRING,
    STRING_LIST,
    ChildObjectShape,
    KindDocumentShape,
)
from app.catalog.kind_documents.common import common_root_children
from app.catalog.metadata_field_spec import (
    INPUT_DATE,
    INPUT_LIST,
    INPUT_NUMBER,
    SECTION_ARTWORK,
    SECTION_PUBLISHING,
    SECTION_REGIONAL,
    SECTION_RELATIONS,
    SECTION_TECHNICAL,
    VALUE_TYPE_BOOLEAN,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_PARTIAL_DATE,
    VALUE_TYPE_STRING,
    VALUE_TYPE_STRING_LIST,
    MetadataFieldSpec,
)
from app.models.base import ItemKind

FIELD_SPECS = (
    MetadataFieldSpec(
        "imprint",
        VALUE_TYPE_STRING,
        "Imprint",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "series_group",
        VALUE_TYPE_STRING,
        "Series group",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "page_count",
        VALUE_TYPE_INTEGER,
        "Page count",
        section=SECTION_PUBLISHING,
        input=INPUT_NUMBER,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "original_language",
        VALUE_TYPE_STRING,
        "Original language",
        section=SECTION_REGIONAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "first_publication_date",
        VALUE_TYPE_PARTIAL_DATE,
        "First publication date",
        section=SECTION_PUBLISHING,
        input=INPUT_DATE,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "original_publication_date",
        VALUE_TYPE_PARTIAL_DATE,
        "Original publication date",
        section=SECTION_PUBLISHING,
        input=INPUT_DATE,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "subjects",
        VALUE_TYPE_STRING_LIST,
        "Subjects",
        section=SECTION_RELATIONS,
        input=INPUT_LIST,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "distributor",
        VALUE_TYPE_STRING,
        "Distributor",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "region",
        VALUE_TYPE_STRING,
        "Region",
        section=SECTION_REGIONAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "edition_statement",
        VALUE_TYPE_STRING,
        "Edition statement",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "dimensions",
        VALUE_TYPE_STRING,
        "Dimensions",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "first_edition", VALUE_TYPE_BOOLEAN, "First edition", kinds=frozenset({ItemKind.book})
    ),
    MetadataFieldSpec(
        "audio_length_minutes",
        VALUE_TYPE_INTEGER,
        "Audio length (minutes)",
        input=INPUT_NUMBER,
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "binding",
        VALUE_TYPE_STRING,
        "Binding",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "back_cover_image_url",
        VALUE_TYPE_STRING,
        "Back cover image URL",
        section=SECTION_ARTWORK,
        kinds=frozenset({ItemKind.book}),
    ),
)

FIELD_SPECS += (
    MetadataFieldSpec(
        "box_set",
        VALUE_TYPE_STRING,
        "Box Set",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "publication_place",
        VALUE_TYPE_STRING,
        "Publication Place",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "printed_by",
        VALUE_TYPE_STRING,
        "Printed By",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "paper_type",
        VALUE_TYPE_STRING,
        "Paper Type",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "number_line",
        VALUE_TYPE_STRING,
        "Number Line",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "original_subtitle",
        VALUE_TYPE_STRING,
        "Original Subtitle",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "original_country",
        VALUE_TYPE_STRING,
        "Original Country",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "original_publisher",
        VALUE_TYPE_STRING,
        "Original Publisher",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "original_publication_place",
        VALUE_TYPE_STRING,
        "Original Publication Place",
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "printing_number",
        VALUE_TYPE_INTEGER,
        "Printing",
        input=INPUT_NUMBER,
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "width_mm",
        VALUE_TYPE_INTEGER,
        "Width (mm)",
        input=INPUT_NUMBER,
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "height_mm",
        VALUE_TYPE_INTEGER,
        "Height (mm)",
        input=INPUT_NUMBER,
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "spine_thickness_mm",
        VALUE_TYPE_INTEGER,
        "Spine Thickness (mm)",
        input=INPUT_NUMBER,
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "weight_grams",
        VALUE_TYPE_INTEGER,
        "Weight (g)",
        input=INPUT_NUMBER,
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "extras",
        VALUE_TYPE_STRING_LIST,
        "Extras",
        input=INPUT_LIST,
        section=SECTION_PUBLISHING,
        kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "audio_abridged",
        VALUE_TYPE_BOOLEAN,
        "Audiobook Abridged",
        section=SECTION_TECHNICAL,
        kinds=frozenset({ItemKind.book}),
    ),
)

_BOOK_PERSON = ChildObjectShape(
    fields=PERSON.fields,
    required=frozenset({"name"}),
    non_empty=frozenset({"name"}),
    nullable=PERSON.nullable,
    allow_string_value=True,
)

BOOK_PRINTING = ChildObjectShape(
    fields={
        "id": STRING,
        "printing_number": INTEGER,
        "title": STRING,
        "release_date": PARTIAL_DATE,
        "publisher": STRING,
        "language": STRING,
        "isbn": STRING,
    },
    nullable=frozenset(
        {
            "id",
            "printing_number",
            "title",
            "release_date",
            "publisher",
            "language",
            "isbn",
        }
    ),
)

BOOK_SERIES_MEMBERSHIP = ChildObjectShape(
    fields={
        "id": STRING,
        "series_id": STRING,
        "sequence": "number",
        "display_number": STRING,
    },
    required=frozenset({"series_id"}),
    non_empty=frozenset({"series_id"}),
    nullable=frozenset({"id", "sequence", "display_number"}),
)

def _validate_book_measurements(payload, path):
    for key in ("printing_number", "width_mm", "height_mm", "spine_thickness_mm", "weight_grams"):
        value = payload.get(key)
        if value is not None and value < 0:
            raise ValueError(f"{path}.{key} must not be negative")


DOCUMENT = KindDocumentShape(
    root_fields={
        "box_set": STRING,
        "publication_place": STRING,
        "printed_by": STRING,
        "paper_type": STRING,
        "number_line": STRING,
        "original_subtitle": STRING,
        "original_country": STRING,
        "original_publisher": STRING,
        "original_publication_place": STRING,
        "printing_number": INTEGER,
        "width_mm": INTEGER,
        "height_mm": INTEGER,
        "spine_thickness_mm": INTEGER,
        "weight_grams": INTEGER,
        "extras": STRING_LIST,
        "audio_abridged": BOOLEAN,
        "description": STRING,
        "series_title": STRING,
        "volume_name": STRING,
        "volume_number": STRING,
        "isbn": STRING,
        "isbn10": STRING,
        "isbn13": STRING,
        "original_language": STRING,
        "first_publication_date": PARTIAL_DATE,
        "original_publication_date": PARTIAL_DATE,
        "subjects": STRING_LIST,
        "distributor": STRING,
        "region": STRING,
        "edition_statement": STRING,
        "dimensions": STRING,
        "first_edition": BOOLEAN,
        "audio_length_minutes": INTEGER,
        "binding": STRING,
        "back_cover_image_url": STRING,
    },
    children={
        **{
            name: replace(
                shape, label={"identifiers": "Identifiers", "external_links": "Links"}[name]
            )
            for name, shape in common_root_children("identifiers", "external_links").items()
        },
        "creators": replace(_BOOK_PERSON, label="Authors"),
        "contributors": replace(_BOOK_PERSON, label="Contributors"),
        "printings": replace(BOOK_PRINTING, label="Printings"),
        "series_memberships": replace(BOOK_SERIES_MEMBERSHIP, label="Series Memberships"),
        "characters": replace(CHARACTER, label="Characters"),
    },
    required_root_fields=frozenset({"title"}),
    validate_document=_validate_book_measurements,
)

__all__ = ["DOCUMENT", "FIELD_SPECS"]
