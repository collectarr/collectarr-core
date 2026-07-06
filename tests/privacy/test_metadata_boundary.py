from dataclasses import fields as dataclass_fields

import pytest
from pydantic import ValidationError

from app import main as app_main
from app import models as app_models
from app.catalog.metadata_fields import METADATA_FIELDS
from app.models.base import Base, ExternalProvider
from app.providers.base import (
    NormalizedBundleRelease,
    NormalizedCredit,
    NormalizedItem,
    NormalizedTrack,
)
from app.proposal_payload import compact_metadata_payload, validate_metadata_payload
from app.schemas.admin import (
    AdminMetadataCorrectionRequest,
    MetadataProposalAdminUpdateRequest,
    ProviderIngestRequest,
)
from app.schemas.metadata_common import MetadataProposalCreate

PERSONAL_FIELD_KEYS = {
    "collection_status",
    "owned",
    "wishlist",
    "my_rating",
    "user_rating",
    "seen_it",
    "viewed",
    "viewing_date",
    "watch_progress",
    "read_it",
    "reading_date",
    "read_times",
    "played",
    "completed",
    "finished",
    "purchase_date",
    "purchase_price",
    "store",
    "sold_date",
    "sold_price",
    "profit",
    "current_value",
    "my_value",
    "market_value",
    "grade",
    "slabbed",
    "cert_number",
    "grading_company",
    "page_quality",
    "local_image_path",
    "local_cover_image_path",
    "local_back_image_path",
    "local_thumbnail_image_path",
    "signed",
    "signed_by",
    "loaned_to",
    "loan_email",
    "loan_address",
    "due_date",
    "return_date",
    "overdue",
    "owner",
    "storage_box",
    "slot",
    "local_tags",
    "custom_field",
    "custom_field_values",
}


def _assert_no_personal_keys(keys: set[str]) -> None:
    assert PERSONAL_FIELD_KEYS.isdisjoint(keys)


def test_metadata_registry_excludes_personal_fields() -> None:
    _assert_no_personal_keys({spec.key for spec in METADATA_FIELDS})


def test_sqlalchemy_models_exclude_personal_fields() -> None:
    _ = app_models
    keys = {column.key for mapper in Base.registry.mappers for column in mapper.columns}
    _assert_no_personal_keys(keys)


def test_provider_normalized_models_exclude_personal_fields() -> None:
    keys = set()
    for cls in (NormalizedItem, NormalizedTrack, NormalizedCredit, NormalizedBundleRelease):
        keys.update(field.name for field in dataclass_fields(cls))
    _assert_no_personal_keys(keys)


def test_openapi_excludes_personal_fields() -> None:
    schema = app_main.app.openapi()
    keys: set[str] = set()
    for component in schema.get("components", {}).get("schemas", {}).values():
        if not isinstance(component, dict):
            continue
        properties = component.get("properties", {})
        if isinstance(properties, dict):
            keys.update(str(key) for key in properties)
    _assert_no_personal_keys(keys)


def test_request_models_forbid_unknown_and_personal_payload_fields() -> None:
    with pytest.raises(ValidationError):
        ProviderIngestRequest(provider=ExternalProvider.comicvine, provider_item_id="123", unexpected=True)

    with pytest.raises(ValidationError):
        AdminMetadataCorrectionRequest(collection_status="owned")

    with pytest.raises(ValidationError):
        MetadataProposalAdminUpdateRequest(metadata_payload={"nested": {"personal": "nope"}})

    with pytest.raises(ValidationError):
        MetadataProposalCreate(
            provider=ExternalProvider.comicvine,
            provider_item_id="123",
            query="spider",
            metadata_payload={"kind": "comic", "nested": {"personal": "nope"}},
        )


def test_metadata_payload_validation_rejects_personal_state_keys() -> None:
    root_payload = compact_metadata_payload(
        {
            "kind": "book",
            "owned": True,
            "wishlist": False,
            "tracking": {"status": "reading"},
        }
    )
    normalized_payload = compact_metadata_payload(
        {
            "kind": "book",
            "normalized": {"owned": True, "wishlist": False, "tracking": {"status": "reading"}},
        }
    )

    assert root_payload is not None
    assert normalized_payload is not None
    with pytest.raises(ValueError):
        validate_metadata_payload(root_payload)
    with pytest.raises(ValueError):
        validate_metadata_payload(normalized_payload)
