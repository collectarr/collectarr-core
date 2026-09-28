import pytest
from pydantic import ValidationError

from app import main as app_main
from app import models as app_models
from app.models.base import Base
from app.schemas.catalog_item_v1 import CatalogItemWriteV1

PERSONAL_FIELD_KEYS = {
    "collection_status",
    "owned",
    "wishlist",
    "my_rating",
    "purchase_date",
    "purchase_price",
    "current_value",
    "loaned_to",
    "owner",
    "location_id",
    "personal_images",
    "custom_fields",
}


def _assert_no_personal_keys(keys: set[str]) -> None:
    assert PERSONAL_FIELD_KEYS.isdisjoint(keys)


def test_sqlalchemy_models_exclude_owned_copy_fields() -> None:
    _ = app_models
    keys = {column.key for mapper in Base.registry.mappers for column in mapper.columns}
    _assert_no_personal_keys(keys)


def test_openapi_exposes_catalog_items_without_provider_routes() -> None:
    schema = app_main.app.openapi()
    paths = set(schema.get("paths", {}))
    assert any("/metadata/catalog-items" in path for path in paths)
    assert not any("provider" in path.casefold() for path in paths)
    assert not any("submission" in path.casefold() for path in paths)

    keys: set[str] = set()
    for component in schema.get("components", {}).get("schemas", {}).values():
        if isinstance(component, dict):
            properties = component.get("properties", {})
            if isinstance(properties, dict):
                keys.update(str(key) for key in properties)
    _assert_no_personal_keys(keys)


def test_catalog_item_write_rejects_owned_copy_fields() -> None:
    with pytest.raises(ValidationError):
        CatalogItemWriteV1(
            details={
                "kind": "book",
                "title": "Dune",
                "collection_status": "owned",
            }
        )
