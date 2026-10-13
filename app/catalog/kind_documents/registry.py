"""Composition point for kind-owned Catalog Item document schemas."""

from app.catalog.document_shape import KindDocumentShape
from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS
from app.models.base import ItemKind

DOCUMENTS: dict[ItemKind, KindDocumentShape] = {
    definition.kind: definition.document for definition in CATALOG_KIND_DEFINITIONS
}


def document_for(kind: ItemKind) -> KindDocumentShape:
    try:
        return DOCUMENTS[kind]
    except KeyError as error:
        raise ValueError(f"No Catalog Item document schema for kind: {kind}") from error
