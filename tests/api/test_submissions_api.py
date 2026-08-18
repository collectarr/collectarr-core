import pytest
from pydantic import ValidationError

from app.schemas.metadata_submissions import (
    MetadataSubmissionRequest,
    MetadataSubmissionResponse,
)


def test_metadata_submission_request_serialization() -> None:
    req = MetadataSubmissionRequest(
        schema_version="v1",
        provider="openlibrary",
        provider_item_id="OL12345M",
        kind="book",
        normalized={
            "title": "Clean Architecture",
            "publisher": "Prentice Hall",
        },
        provenance={"fetched_at": "2026-08-18T00:00:00Z"},
    )
    d = req.model_dump()
    assert d["schema_version"] == "v1"
    assert d["provider"] == "openlibrary"
    assert d["provider_item_id"] == "OL12345M"
    assert d["kind"] == "book"
    assert d["normalized"]["title"] == "Clean Architecture"


def test_metadata_submission_response_structure() -> None:
    res = MetadataSubmissionResponse(
        status="canonical_write",
        kind="book",
        created=True,
        message="Write completed",
    )
    assert res.status == "canonical_write"
    assert res.kind == "book"
    assert res.created is True
