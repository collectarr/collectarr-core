import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import ExternalProviderId, Item, Organization
from app.providers.base import ProviderItem
from app.providers.openlibrary import OpenLibraryProvider
from app.search.client import SearchClient


async def _admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _edition_raw() -> dict:
    return {
        "key": "/books/OL7353617M",
        "title": "The Hobbit",
        "publish_date": "September 21, 1937",
        "publishers": ["George Allen & Unwin"],
        "isbn_13": ["9780618260300"],
        "number_of_pages": 310,
        "physical_format": "Hardcover",
        "covers": [6979861],
        "works": [{"key": "/works/OL262758W"}],
    }


def _work_raw() -> dict:
    return {
        "key": "/works/OL262758W",
        "title": "The Hobbit",
        "description": {"value": "Bilbo Baggins leaves the Shire."},
    }


@pytest.mark.asyncio
async def test_openlibrary_provider_search_normalizes_results(monkeypatch):
    async def fake_request(self, path, params=None):
        assert path == "search.json"
        assert params["q"] == "The Hobbit"
        return {
            "docs": [
                {
                    "key": "/works/OL262758W",
                    "title": "The Hobbit",
                    "author_name": ["J. R. R. Tolkien"],
                    "first_publish_year": 1937,
                    "edition_key": ["OL7353617M"],
                    "publisher": ["George Allen & Unwin"],
                    "cover_i": 6979861,
                }
            ]
        }

    monkeypatch.setattr(OpenLibraryProvider, "_request", fake_request)

    results = await OpenLibraryProvider().search(" The Hobbit ")

    assert len(results) == 1
    assert results[0].provider_item_id == "OL7353617M"
    assert results[0].kind == ItemKind.book
    assert results[0].title == "The Hobbit"
    assert "Tolkien" in results[0].summary
    assert results[0].image_url == "https://covers.openlibrary.org/b/id/6979861-L.jpg"


@pytest.mark.asyncio
async def test_openlibrary_provider_fetches_edition_and_normalizes(monkeypatch):
    async def fake_request(self, path, params=None):
        responses = {
            "books/OL7353617M.json": _edition_raw(),
            "works/OL262758W.json": _work_raw(),
        }
        return responses[path]

    monkeypatch.setattr(OpenLibraryProvider, "_request", fake_request)

    item = await OpenLibraryProvider().get_item("OL7353617M")
    normalized = await OpenLibraryProvider().normalize(item.raw)

    assert item.provider_item_id == "OL7353617M"
    assert normalized.kind == ItemKind.book
    assert normalized.title == "The Hobbit"
    assert normalized.publisher == "George Allen & Unwin"
    assert normalized.release_date.year == 1937
    assert normalized.isbn == "9780618260300"
    assert normalized.page_count == 310
    assert normalized.cover_image_url == "https://covers.openlibrary.org/b/id/6979861-L.jpg"
    assert normalized.provider_ids == {"openlibrary": "OL7353617M"}
    assert normalized.volume_provider_ids == {"openlibrary": "OL262758W"}


@pytest.mark.asyncio
async def test_admin_ingest_upserts_openlibrary_book(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="openlibrary",
            provider_item_id="OL7353617M",
            raw={"edition": _edition_raw(), "work": _work_raw()},
        )

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(OpenLibraryProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "openlibrary", "provider_item_id": "OL7353617M"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "book"
    assert body["item"]["title"] == "The Hobbit"
    assert body["item"]["publisher"] == "George Allen & Unwin"
    assert body["item"]["barcode"] == "9780618260300"

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.book))
        provider_ids = list(
            await db.scalars(
                select(ExternalProviderId.provider_item_id).where(
                    ExternalProviderId.provider == ExternalProvider.openlibrary
                )
            )
        )
        publisher = await db.scalar(select(Organization.name))

    assert item is not None
    assert sorted(provider_ids) == ["OL262758W", "OL7353617M"]
    assert publisher == "George Allen & Unwin"
