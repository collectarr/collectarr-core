"""Hardware edition fields; serial numbers never enter the shared catalog."""

from app.catalog.document_shape import PARTIAL_DATE_OBJECT, STRING, KindDocumentShape
from app.catalog.kind_documents.common import common_root_children
from app.catalog.metadata_field_spec import VALUE_TYPE_STRING, MetadataFieldSpec
from app.models.base import ItemKind

FIELD_SPECS = tuple(
    MetadataFieldSpec(key, VALUE_TYPE_STRING, label, kinds=frozenset({ItemKind.game_hardware}))
    for key, label in (("platform", "Platform"), ("hardware_type", "Hardware Type"))
)

DOCUMENT = KindDocumentShape(
    root_fields={"platform": STRING, "hardware_type": STRING, "description": STRING,
                 "release_date_parts": PARTIAL_DATE_OBJECT},
    children=common_root_children("external_links", "trailer_urls"),
    allowed_root_fields=frozenset({
        "title", "sort_key", "platform", "hardware_type", "barcode", "release_date_parts",
        "series_title", "description", "cover_image_url", "external_links", "trailer_urls",
    }),
    rejected_root_fields=frozenset({"serial_number", "serial_no", "completed", "storage_device",
                                   "toy_type", "toy_subtype", "developers", "genres"}),
    required_root_fields=frozenset({"title"}),
    reject_unknown_fields=True,
)

SEARCH_FILTER_FIELDS = ('platform', 'hardware_type')
