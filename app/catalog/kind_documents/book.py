"""Book Catalog Item fields and contained edition values."""

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
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN
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
        "imprint", VALUE_TYPE_STRING, "Imprint",
        section=SECTION_PUBLISHING, kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "series_group", VALUE_TYPE_STRING, "Series group",
        section=SECTION_PUBLISHING, kinds=frozenset({ItemKind.book}),
    ),
    MetadataFieldSpec(
        "page_count", VALUE_TYPE_INTEGER, "Page count",
        section=SECTION_PUBLISHING, input=INPUT_NUMBER,
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

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "creators",
            "contributors",
            "description",
            "identifiers",
            "printings",
            "series_memberships",
            "series_title",
            "volume_name",
            "volume_number",
            "isbn",
            "isbn10",
            "isbn13",
            "original_language",
            "first_publication_date",
            "original_publication_date",
            "subjects",
            "distributor",
            "region",
            "edition_statement",
            "dimensions",
            "first_edition",
            "audio_length_minutes",
            "binding",
            "characters",
            "back_cover_image_url",
        }
    ),
    root_value_types={
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
        **COMMON_ROOT_CHILDREN,
        "creators": _BOOK_PERSON,
        "contributors": _BOOK_PERSON,
        "printings": BOOK_PRINTING,
        "series_memberships": BOOK_SERIES_MEMBERSHIP,
        "characters": CHARACTER,
    },
)

__all__ = ["DOCUMENT", "FIELD_SPECS"]
