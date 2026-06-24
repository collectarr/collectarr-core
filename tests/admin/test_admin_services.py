from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException, status

from app.services.admin_domains.catalog import AdminCatalogService
from app.services.admin_domains.overview import (
    _SEARCH_HISTORY,
    AdminOverviewService,
    _meili_document_count,
)
from app.services.admin_domains.support import AdminSupportService


@pytest.mark.asyncio
async def test_catalog_service_catalog_items_uses_loader_for_each_result(monkeypatch):
    seen: dict[str, object] = {}
    items = [SimpleNamespace(id=uuid4()), SimpleNamespace(id=uuid4())]

    class FakeRepository:
        def __init__(self, db):
            seen["db"] = db

        async def search_items(self, query=None, kind=None, limit=25, **filters):
            seen["query"] = query
            seen["kind"] = kind
            seen["limit"] = limit
            seen["filters"] = filters
            return items

    responses = []

    async def fake_item_response_loader(item):
        responses.append(item.id)
        return {"id": str(item.id)}

    monkeypatch.setattr("app.services.admin_domains.catalog.MetadataRepository", FakeRepository)

    service = AdminCatalogService(
        db="db-session",
        item_response_loader=fake_item_response_loader,
        audit_recorder=lambda *args, **kwargs: None,
        reindex_items=lambda item_ids: None,
        sort_key_builder=lambda kind, title, item_number: "sort-key",
        get_or_create_tag=lambda kind, name: None,
    )

    result = await service.catalog_items(
        query="batman",
        limit=7,
        publisher="DC",
        imprint="Black Label",
        catalog_number="ABS-1",
    )

    assert seen == {
        "db": "db-session",
        "query": "batman",
        "kind": None,
        "limit": 7,
        "filters": {
            "publisher": "DC",
            "imprint": "Black Label",
            "subtitle": None,
            "series_group": None,
            "country": None,
            "language": None,
            "age_rating": None,
            "catalog_number": "ABS-1",
            "release_status": None,
        },
    }
    assert responses == [item.id for item in items]
    assert result == [{"id": str(item.id)} for item in items]


def test_support_service_record_admin_audit_normalizes_json_like_values():
    added: list[object] = []

    class FakeDb:
        def add(self, entry):
            added.append(entry)

    entity_id = uuid4()
    happened_at = datetime(2024, 1, 2, 3, 4, 5, tzinfo=UTC)
    service = AdminSupportService(
        db=FakeDb(),
        actor_user_id=uuid4(),
        actor_email="admin@example.com",
    )

    service.record_admin_audit(
        "catalog.update",
        "item",
        entity_id,
        {
            "entity_id": entity_id,
            "happened_at": happened_at,
            "tags": {"featured", "new"},
        },
    )

    assert len(added) == 1
    assert added[0].details_json["entity_id"] == str(entity_id)
    assert added[0].details_json["happened_at"] == happened_at.isoformat()
    assert sorted(added[0].details_json["tags"]) == ["featured", "new"]


def test_support_service_retry_helpers_cover_retryable_and_non_retryable_errors():
    service = AdminSupportService(db=object(), actor_user_id=None, actor_email=None)

    retryable_error = HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="busy")
    non_retryable_error = HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="bad request")

    assert service.backoff_delay(1).total_seconds() == 5
    assert service.backoff_delay(7).total_seconds() == 300
    assert service.is_retryable_ingest_error(retryable_error) is True
    assert service.is_retryable_ingest_error(non_retryable_error) is False
    assert service.is_retryable_ingest_error(RuntimeError("boom")) is False
    assert service.error_message(retryable_error) == "busy"
    assert service.error_message(RuntimeError("boom")) == "boom"


@pytest.mark.parametrize(
    ("stats", "expected"),
    [
        ({"numberOfDocuments": 12}, 12),
        ({"number_of_documents": "14"}, 14),
        (SimpleNamespace(number_of_documents=9), 9),
        (SimpleNamespace(numberOfDocuments="11"), 11),
        (
            SimpleNamespace(
                model_dump=lambda by_alias=True: {"numberOfDocuments": "15"},
            ),
            15,
        ),
        ({"numberOfDocuments": "nope"}, None),
    ],
)
def test_meili_document_count_normalizes_supported_shapes(stats, expected):
    assert _meili_document_count(stats) == expected


@pytest.mark.asyncio
async def test_overview_search_status_reports_health_and_document_count(monkeypatch):
    class FakeIndex:
        def get_stats(self):
            return {"numberOfDocuments": "17"}

    class FakeClientApi:
        def health(self):
            return {"status": "available"}

        def index(self, index_name):
            assert index_name == "admin-items"
            return FakeIndex()

    class FakeSearchClient:
        index_name = "admin-items"

        def __init__(self):
            self.client = FakeClientApi()
            self.index_name = "admin-items"

    monkeypatch.setattr("app.services.admin_domains.overview.SearchClient", FakeSearchClient)

    service = AdminOverviewService(
        db=object(),
        providers=object(),
        provider_search_state=object(),
        provider_preview_state=object(),
        duplicate_group_count=lambda: None,
        ingest_history_reader=lambda: [],
    )

    result = await service.search_status()

    assert result.ok is True
    assert result.index_name == "admin-items"
    assert result.document_count == 17
    assert result.is_empty is False


@pytest.mark.asyncio
async def test_overview_reindex_search_replaces_documents_and_records_history(monkeypatch):
    _SEARCH_HISTORY.clear()
    seen: dict[str, object] = {}

    class FakeSearchClient:
        def __init__(self):
            self.index_name = "admin-items"

        async def configure(self):
            seen["configured"] = True

        async def replace_documents(self, documents):
            seen["documents"] = documents

    monkeypatch.setattr("app.services.admin_domains.overview.SearchClient", FakeSearchClient)

    async def fake_duplicate_group_count():
        return 0

    service = AdminOverviewService(
        db=object(),
        providers=object(),
        provider_search_state=object(),
        provider_preview_state=object(),
        duplicate_group_count=fake_duplicate_group_count,
        ingest_history_reader=lambda: [],
    )

    async def fake_search_documents():
        return [{"id": "1"}, {"id": "2"}]

    monkeypatch.setattr(service, "_search_documents", fake_search_documents)

    result = await service.reindex_search()

    assert result.ok is True
    assert result.index_name == "admin-items"
    assert result.indexed_documents == 2
    assert seen == {"configured": True, "documents": [{"id": "1"}, {"id": "2"}]}
    assert len(service.search_history()) == 1
    assert service.search_history()[0].ok is True
    assert service.search_history()[0].indexed_documents == 2