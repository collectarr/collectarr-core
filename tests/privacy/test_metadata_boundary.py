import pytest
from pydantic import ValidationError

from app import main as app_main
from app import models as app_models
from app.catalog.catalog_item_schema import validate_catalog_item_payload
from app.catalog.metadata_fields import METADATA_FIELDS
from app.models.base import Base, ItemKind
from app.schemas.catalog_item_proposals import (
    CatalogItemProposalCreate,
    CatalogItemProposalUpdate,
)

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


def test_user_proposals_project_only_kind_owned_catalog_data() -> None:
    accepted = CatalogItemProposalCreate(
        kind=ItemKind.book,
        catalog_item={
            "title": "A source-neutral edition",
            "contributors": [{"name": "A. Writer", "role": "author"}],
        },
    )
    assert accepted.catalog_item["title"] == "A source-neutral edition"

    submitted = {
        "title": "A source-neutral edition",
        "contributors": [
            {
                "name": "A. Writer",
                "role": "author",
                "provider_ids": {"external": "1"},
            }
        ],
        "owned_copy": {"condition": "mint"},
        "purchase_date": "2026-01-01",
        "provider_item_id": "external-1",
    }
    projected = validate_catalog_item_payload(ItemKind.book, submitted)
    assert projected == {
        "title": "A source-neutral edition",
        "contributors": [{"name": "A. Writer", "role": "author"}],
    }
    accepted_with_local_fields = CatalogItemProposalCreate(
        kind=ItemKind.book,
        catalog_item=submitted,
    )
    assert accepted_with_local_fields.catalog_item == projected

    with pytest.raises(ValidationError):
        CatalogItemProposalUpdate(catalog_item={"purchase_date": "2026-01-01"})
