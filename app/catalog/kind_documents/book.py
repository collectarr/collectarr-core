"""Book Catalog Item fields and contained edition values."""

from app.catalog.document_shape import (
    STRING,
    ChildObjectShape,
    KindDocumentShape,
    PERSON,
)
from app.catalog.kind_documents.common import COMMON_ROOT_CHILDREN, PRINTING, SERIES_MEMBERSHIP

_BOOK_PERSON = ChildObjectShape(
    fields=PERSON.fields,
    required=frozenset({"name"}),
    non_empty=frozenset({"name"}),
    nullable=PERSON.nullable,
    allow_string_value=True,
)

DOCUMENT = KindDocumentShape(
    root_fields=frozenset(
        {
            "creators", "contributors", "description", "identifiers", "printings",
            "series_memberships", "series_title", "volume_name", "volume_number",
            "isbn", "isbn10", "isbn13",
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
    },
    children={
        **COMMON_ROOT_CHILDREN,
        "creators": _BOOK_PERSON,
        "contributors": _BOOK_PERSON,
        "printings": PRINTING,
        "series_memberships": SERIES_MEMBERSHIP,
    },
)
