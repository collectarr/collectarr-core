import pytest
from pydantic import ValidationError

from app import main as app_main
from app import models as app_models
from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.catalog.metadata_fields import METADATA_FIELDS
from app.models.base import Base, ItemKind
from app.schemas.catalog_item_proposals import CatalogItemProposalCreate

PERSONAL_FIELD_KEYS = {
    "collection_status",
    "owned_copy",
    "owned_item",
    "wishlist",
    "tracking",
    "watch_sessions",
    "listening_sessions",
    "purchase_date",
    "purchase_price",
    "purchase_store",
    "sold_date",
    "sell_price",
    "personal_notes",
    "personal_images",
    "local_image_path",
    "custom_fields",
    "location_id",
    "owner_id",
}


def test_metadata_registry_excludes_personal_fields() -> None:
    assert PERSONAL_FIELD_KEYS.isdisjoint({field.key for field in METADATA_FIELDS})


def test_sqlalchemy_models_exclude_personal_fields() -> None:
    _ = app_models
    keys = {column.key for mapper in Base.registry.mappers for column in mapper.columns}
    assert PERSONAL_FIELD_KEYS.isdisjoint(keys)


def test_openapi_excludes_personal_fields() -> None:
    schema = app_main.app.openapi()
    keys: set[str] = set()
    for component in schema.get("components", {}).get("schemas", {}).values():
        if isinstance(component, dict):
            properties = component.get("properties", {})
            if isinstance(properties, dict):
                keys.update(str(key) for key in properties)
    assert PERSONAL_FIELD_KEYS.isdisjoint(keys)


def test_music_user_proposals_reject_personal_and_unrecognized_data() -> None:
    catalog = {"title": "A source-neutral edition", "artist": "Artist", "artist_credits": [{"id": "artist-credit", "name": "Artist", "sequence": 1}], "credits": [], "genres": [], "extra": [], "external_links": [], "discs": []}
    assert CatalogItemProposalCreate(kind=ItemKind.music, catalog_item=catalog).catalog_item == catalog
    for key in ("owned_copy", "purchase_date", "external_catalog_reference"):
        with pytest.raises(ValueError, match="unrecognized fields"):
            validate_catalog_item_payload(ItemKind.music, {**catalog, key: "private"})
    with pytest.raises(ValidationError):
        CatalogItemProposalCreate(schema_version="v2", kind=ItemKind.music, catalog_item=catalog)
