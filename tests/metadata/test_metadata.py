from datetime import date
from uuid import UUID

import pytest

from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import Edition, Item, Variant
from app.repositories.metadata import MetadataRepository
from app.search.documents import item_search_document
from tests.helpers import seed_comic


@pytest.mark.asyncio
async def test_media_type_catalog_exposes_provider_defaults_and_formats(client):
    response = await client.get("/metadata/media-types")

    assert response.status_code == 200
    body = response.json()
    assert body["contract_version"] == 1
    assert body["snapshot_schema_version"] == 1
    assert body["default_kind"] == "comic"
    rows = {item["kind"]: item for item in body["media_types"]}
    assert rows["comic"]["default_provider"] == "gcd"
    assert rows["comic"]["providers"] == ["gcd", "comicvine"]
    assert rows["comic"]["provider_search_policy"] == "core_miss_then_configured_providers"
    assert rows["manga"]["default_provider"] == "anilist"
    assert rows["manga"]["providers"] == ["anilist", "mangadex", "comicvine"]
    assert rows["anime"]["default_provider"] == "anilist"
    assert rows["anime"]["providers"] == ["anilist", "tmdb"]
    assert rows["movie"]["providers"] == ["tmdb"]
    assert [format["id"] for format in rows["movie"]["physical_formats"]] == [
        "dvd",
        "blu-ray",
        "4k-uhd",
        "vhs",
        "laserdisc",
        "digital",
    ]
    assert rows["bluray"]["is_top_level"] is False
    assert rows["bluray"]["legacy_of"] == "movie"


@pytest.mark.asyncio
async def test_search_falls_back_to_postgres(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()

    response = await client.get("/search", params={"q": "spider", "kind": "comic"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == item_id
    assert response.json()[0]["publisher"] == "Marvel"
    assert response.json()[0]["release_date"] == "1963-03-01"
    assert response.json()[0]["release_year"] == 1963
    assert response.json()[0]["barcode"] == "75960604716100111"
    assert response.json()[0]["variant"] == "Cover A"

    detail = await client.get(f"/comics/{item_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "The Amazing Spider-Man"

    singular_alias_detail = await client.get(f"/comic/{item_id}")
    assert singular_alias_detail.status_code == 200
    assert singular_alias_detail.json()["title"] == "The Amazing Spider-Man"

    generic_detail = await client.get(f"/metadata/comic/{item_id}")
    assert generic_detail.status_code == 200
    assert generic_detail.json()["title"] == "The Amazing Spider-Man"

    wrong_media_detail = await client.get(f"/metadata/games/{item_id}")
    assert wrong_media_detail.status_code == 404


@pytest.mark.asyncio
async def test_search_treats_empty_meilisearch_results_as_authoritative(client, monkeypatch):
    async def empty_search(self, query, kind=None, **kwargs):
        return []

    monkeypatch.setattr("app.search.client.SearchClient.search", empty_search)
    await seed_comic()

    response = await client.get("/search", params={"q": "spider", "kind": "comic"})

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.asyncio
async def test_search_supports_comic_filters(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()

    response = await client.get(
        "/search",
        params={
            "kind": "comic",
            "series": "Amazing",
            "issue_number": "1",
            "publisher": "Marvel",
            "year": 1963,
        },
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == item_id
    assert response.json()[0]["publisher"] == "Marvel"
    assert response.json()[0]["release_date"] == "1963-03-01"
    assert response.json()[0]["release_year"] == 1963
    assert response.json()[0]["barcode"] == "75960604716100111"
    assert response.json()[0]["variant"] == "Cover A"


@pytest.mark.asyncio
async def test_search_supports_barcode_filter(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()

    response = await client.get(
        "/search",
        params={"kind": "comic", "barcode": "75960604716100111"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == item_id


@pytest.mark.asyncio
async def test_lookup_comic_by_barcode(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()

    response = await client.get("/barcode/75960604716100111", params={"kind": "comic"})

    assert response.status_code == 200
    assert response.json()["id"] == item_id
    assert response.json()["title"] == "The Amazing Spider-Man"
    assert response.json()["publisher"] == "Marvel"
    assert response.json()["release_date"] == "1963-03-01"
    assert response.json()["release_year"] == 1963
    assert response.json()["barcode"] == "75960604716100111"
    assert response.json()["variant"] == "Cover A"


@pytest.mark.asyncio
async def test_lookup_barcode_prefers_matching_variant_cover(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, edition_id, variant_id = await seed_comic()
    async with AsyncSessionLocal() as db:
        primary = await db.get(Variant, UUID(variant_id))
        assert primary is not None
        primary.cover_image_url = "https://cdn.example/standard.jpg"
        db.add(
            Variant(
                edition_id=UUID(edition_id),
                name="Foil Variant",
                barcode="123456789012",
                cover_image_url="https://cdn.example/foil.jpg",
                is_primary=False,
            )
        )
        await db.commit()

    response = await client.get("/barcode/123456789012", params={"kind": "comic"})

    assert response.status_code == 200
    assert response.json()["id"] == item_id
    assert response.json()["variant"] == "Foil Variant"
    assert response.json()["barcode"] == "123456789012"
    assert response.json()["cover_image_url"] == "https://cdn.example/foil.jpg"


@pytest.mark.asyncio
async def test_lookup_video_barcode_matches_physical_editions(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.movie,
            title="Blade Runner",
            item_number="Final Cut",
        )
        edition = Edition(
            item=item,
            title="Final Cut 4K release",
            format="4K Blu-ray",
            publisher="Warner Bros.",
            upc="883-929 087.129",
            release_date=date(1982, 6, 25),
            metadata_json={"normalized": {"physical_format": "4k-uhd"}},
        )
        variant = Variant(
            edition=edition,
            name="4K UHD",
            sku="SKU-4K-001",
            is_primary=True,
            metadata_json={"normalized": {"physical_format": "4k-uhd"}},
        )
        db.add_all([item, edition, variant])
        await db.commit()
        item_id = str(item.id)

    response = await client.get("/barcode/883929087129", params={"kind": "movie"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == item_id
    assert body["edition_title"] == "Final Cut 4K release"
    assert body["publisher"] == "Warner Bros."
    assert body["release_date"] == "1982-06-25"
    assert body["barcode"] == "883-929 087.129"
    assert body["variant"] == "4K UHD"
    assert body["physical_format"] == "4k-uhd"
    assert body["physical_format_label"] == "4K UHD"

    sku_response = await client.get("/barcode/SKU4K001", params={"kind": "movie"})

    assert sku_response.status_code == 200
    assert sku_response.json()["id"] == item_id


@pytest.mark.asyncio
async def test_lookup_barcode_returns_404_for_unknown_code(client):
    response = await client.get("/barcode/0000000000000", params={"kind": "comic"})

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_search_document_keeps_synopsis_out_of_index():
    item_id, _, _ = await seed_comic()
    async with AsyncSessionLocal() as db:
        item = await MetadataRepository(db).get_item(UUID(item_id), ItemKind.comic)

    assert item is not None
    item.synopsis = "This plot text should stay out of Meilisearch."

    document = item_search_document(item)

    assert "synopsis" not in document
    assert document["barcode"] == "75960604716100111"
    assert document["barcodes"] == ["75960604716100111"]
    assert document["release_date"] == "1963-03-01"
    assert document["release_year"] == 1963
    assert document["variant"] == "Cover A"
