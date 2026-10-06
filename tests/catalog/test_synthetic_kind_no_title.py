"""Tests verifying that generic catalog schema and search do not require or assume title.

A synthetic kind (e.g. specimen_code, epoch, curator) without a canonical title
can be validated, projected, and handled without any universal title contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from app.catalog.catalog_item_schema import (
    _project_object,
    _root_field_schema,
    _root_fields_for_kind,
)
from app.catalog.document_shape import STRING, KindDocumentShape
from app.catalog.metadata_field_spec import MetadataFieldSpec
from app.models.base import ItemKind
from app.schemas.metadata_shared import CatalogSearchItemEnvelope
from app.services.catalog_item_search import CatalogItemSearchService


def test_synthetic_kind_document_shape_and_payload_validation():
    shape = KindDocumentShape(
        root_fields={
            "specimen_code": STRING,
            "epoch": STRING,
            "curator": STRING,
        },
        children={},
        required_root_fields=frozenset({"specimen_code"}),
    )

    field_specs = {
        "specimen_code": MetadataFieldSpec(
            "specimen_code", STRING, "Specimen Code", kinds=frozenset({ItemKind.comic})
        ),
        "epoch": MetadataFieldSpec("epoch", STRING, "Epoch", kinds=frozenset({ItemKind.comic})),
        "curator": MetadataFieldSpec(
            "curator", STRING, "Curator", kinds=frozenset({ItemKind.comic})
        ),
    }

    # 1. Project valid payload without title
    valid_payload = {
        "specimen_code": "SPEC-101",
        "epoch": "Jurassic",
        "curator": "Dr. Alan Grant",
    }
    projected = _project_object(
        valid_payload,
        _root_fields_for_kind(shape, field_specs),
        "catalog_item",
        document=shape,
        field_specs=field_specs,
    )
    assert projected["specimen_code"] == "SPEC-101"
    assert projected["epoch"] == "Jurassic"
    assert projected["curator"] == "Dr. Alan Grant"
    assert "title" not in projected

    # 2. Missing required root field raises
    with pytest.raises(ValueError, match="must include a non-empty specimen_code"):
        _project_object(
            {"epoch": "Cretaceous"},
            _root_fields_for_kind(shape, field_specs),
            "catalog_item",
            document=shape,
            field_specs=field_specs,
        )

    # 3. Root field schema does not enforce minLength on non-required fields
    schema_epoch = _root_field_schema("epoch", shape, field_specs)
    assert schema_epoch == {"anyOf": [{"type": "string"}, {"type": "null"}]}

    # 4. Required root field schema is non-nullable with minLength
    schema_code = _root_field_schema("specimen_code", shape, field_specs)
    assert schema_code == {"type": "string", "minLength": 1}


def test_synthetic_item_search_envelope_without_title():
    synthetic_id = uuid4()
    item = MagicMock()
    item.id = synthetic_id
    # Item explicitly lacks title attribute
    del item.title
    item.specimen_code = "SPEC-404"
    item.epoch = "Triassic"
    item.details = {"curator": "Dr. Ellie Sattler"}

    definition = MagicMock()
    definition.kind = ItemKind.comic
    definition.response_model = MagicMock()
    definition.response_model.model_fields = {"specimen_code", "epoch", "curator"}

    envelope = CatalogItemSearchService._to_search_envelope(definition, item)
    assert envelope.id == synthetic_id
    assert envelope.kind == ItemKind.comic
    assert "title" not in envelope.kind_data
    assert isinstance(envelope, CatalogSearchItemEnvelope)
