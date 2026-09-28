from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.services.admin_domains.overview import (
    _SEARCH_HISTORY,
    AdminOverviewService,
    _meili_document_count,
)
from app.services.admin_domains.support import AdminSupportService
from app.services.typed_values import typed_value_from_row


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
    details = {row.path: typed_value_from_row(row) for row in added[0].details}
    assert details["/entity_id"] == entity_id
    assert details["/happened_at"] == happened_at
    assert sorted(details["/tags"]) == ["featured", "new"]


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
        duplicate_group_count=lambda: None,
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

    catalog_item = CanonicalCatalogItem(
        id=uuid4(),
        kind="book",
        title="Dune",
        sort_title="Dune",
        details={
            "kind": "book",
            "title": "Dune",
            "publisher": "Chilton",
            "publication_date": {"year": 1965},
            "identifiers": [{"identifier_type": "isbn", "value": "9780441172719"}],
        },
    )

    class FakeDb:
        async def scalars(self, statement):
            return [catalog_item]

    service = AdminOverviewService(
        db=FakeDb(),
        duplicate_group_count=fake_duplicate_group_count,
    )

    result = await service.reindex_search()

    assert result.ok is True
    assert result.index_name == "admin-items"
    assert result.indexed_documents == 1
    assert seen["configured"] is True
    document = seen["documents"][0]
    assert document["id"] == str(catalog_item.id)
    assert document["kind"] == "book"
    assert document["title"] == "Dune"
    assert document["publisher"] == "Chilton"
    assert document["release_year"] == 1965
    assert document["barcodes"] == []
    assert len(service.search_history()) == 1
    assert service.search_history()[0].ok is True
    assert service.search_history()[0].indexed_documents == 2
