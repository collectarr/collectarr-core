"""Metadata field specifications shared by print-oriented kinds."""

from app.catalog.metadata_field_spec import (
    INPUT_NUMBER,
    PRINT_KINDS,
    SECTION_PUBLISHING,
    VALUE_TYPE_INTEGER,
    VALUE_TYPE_STRING,
    MetadataFieldSpec,
)

FIELD_SPECS = (
    MetadataFieldSpec("imprint", VALUE_TYPE_STRING, "Imprint",
                      section=SECTION_PUBLISHING, kinds=PRINT_KINDS),
    MetadataFieldSpec("series_group", VALUE_TYPE_STRING, "Series group",
                      section=SECTION_PUBLISHING, kinds=PRINT_KINDS),
    MetadataFieldSpec("page_count", VALUE_TYPE_INTEGER, "Page count",
                      section=SECTION_PUBLISHING, input=INPUT_NUMBER,
                      kinds=PRINT_KINDS),
)

__all__ = ["FIELD_SPECS"]
