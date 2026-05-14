from datetime import date

import pytest
from sqlalchemy import func, select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.canonical import (
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    Item,
    Organization,
    Person,
    Release,
    Series,
    Tag,
    Variant,
    Volume,
)
from app.providers.base import ProviderItem
from app.providers.comicvine import ComicVineProvider
from app.providers.gcd import GCDProvider
from app.search.client import SearchClient
from app.storage.images import MirroredImage, ImageMirror


async def admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def comicvine_issue_raw() -> dict:
    return {
        "id": 12345,
        "api_detail_url": "https://comicvine.gamespot.com/api/issue/4000-12345/",
        "site_detail_url": "https://comicvine.gamespot.com/amazing-spider-man-1/4000-12345/",
        "name": "The Spider Strikes",
        "issue_number": "1",
        "deck": "Peter Parker begins a new chapter.",
        "description": "<p>Peter Parker faces a new chapter as Spider-Man.</p>",
        "cover_date": "1963-03-01",
        "store_date": "1963-02-10",
        "number_of_pages": 32,
        "person_credits": [
            {"name": "Stan Lee", "role": "Writer"},
            {"name": "Steve Ditko", "role": "Artist"},
        ],
        "character_credits": [{"name": "Spider-Man"}],
        "story_arc_credits": [{"name": "The Spider Strikes"}],
        "image": {"super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"},
        "volume": {
            "id": 6789,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-6789/",
            "name": "The Amazing Spider-Man",
            "publisher": {"name": "Marvel"},
        },
    }


def gcd_issue_raw() -> dict:
    return {
        "api_url": "https://www.comics.org/api/issue/256114/",
        "series_name": "Batman: Dark Victory (1999 series)",
        "descriptor": "12",
        "number": "12",
        "volume": "",
        "variant_name": "",
        "title": "",
        "publication_date": "November 2000",
        "key_date": "2000-11-00",
        "price": "2.95 USD; 4.50 CAD",
        "page_count": "36.000",
        "editing": "Mark Chiarello (editor)",
        "indicia_publisher": "DC Comics",
        "brand_emblem": "DC [bullet]",
        "isbn": "",
        "barcode": "76194122054301211",
        "on_sale_date": "2000-09-20",
        "notes": "",
        "variant_of": None,
        "series": "https://www.comics.org/api/series/6139/",
        "story_set": [
            {
                "type": "cover",
                "title": "Revenge",
                "script": "None",
                "pencils": "Tim Sale",
                "inks": "Tim Sale",
                "colors": "Mark Chiarello",
                "letters": "None",
                "editing": "None",
                "characters": "Two-Face",
                "synopsis": "",
            },
            {
                "type": "comic story",
                "title": "Revenge",
                "script": "Jeph Loeb",
                "pencils": "Tim Sale",
                "inks": "Tim Sale",
                "colors": "Gregory Wright (colors); Heroic Age (separations)",
                "letters": "Richard Starkings",
                "editing": "None",
                "characters": (
                    "Batman [Bruce Wayne]; Dick Grayson; Alfred Pennyworth; Two-Face [Harvey Dent]"
                ),
                "synopsis": "Two-Face seeks revenge.",
            },
        ],
        "cover": "https://files1.comics.org//img/gcd/covers_by_id/237/w400/237538.jpg",
    }


def gcd_variant_issue_raw() -> dict:
    issue = gcd_issue_raw()
    issue.update(
        {
            "api_url": "https://www.comics.org/api/issue/2665653/",
            "series_name": "Absolute Batman (2024 series)",
            "descriptor": "1 [Jim Lee & Scott Williams Cardstock Variant Cover]",
            "number": "1",
            "variant_name": "Jim Lee & Scott Williams Cardstock Variant Cover",
            "variant_of": "https://www.comics.org/api/issue/2663120/",
            "price": "5.99 USD",
            "barcode": "76194138584600121",
            "on_sale_date": "2024-10-09",
            "key_date": "2024-10-00",
            "publication_date": "December 2024",
            "page_count": "52.000",
            "series": "https://www.comics.org/api/series/216143/",
            "cover": "https://files1.comics.org//img/gcd/covers_by_id/1791/w400/1791589.jpg",
        }
    )
    return issue


@pytest.mark.asyncio
async def test_comicvine_provider_normalizes_issue_payload():
    normalized = await ComicVineProvider().normalize(comicvine_issue_raw())

    assert normalized.title == "The Amazing Spider-Man"
    assert normalized.item_number == "1"
    assert normalized.edition_title == "The Spider Strikes"
    assert normalized.publisher == "Marvel"
    assert normalized.release_date == date(1963, 3, 1)
    assert normalized.page_count == 32
    assert normalized.provider_ids == {"comicvine": "4000-12345"}
    assert normalized.volume_provider_ids == {"comicvine": "4050-6789"}
    assert [(credit.name, credit.role) for credit in normalized.creators] == [
        ("Stan Lee", "Writer"),
        ("Steve Ditko", "Artist"),
    ]
    assert [credit.name for credit in normalized.characters] == ["Spider-Man"]
    assert [credit.name for credit in normalized.story_arcs] == ["The Spider Strikes"]
    assert (
        normalized.cover_image_url
        == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    )
    assert normalized.synopsis == "Peter Parker faces a new chapter as Spider-Man."


@pytest.mark.asyncio
async def test_gcd_provider_normalizes_issue_payload():
    normalized = await GCDProvider().normalize(gcd_issue_raw())

    assert normalized.title == "Batman: Dark Victory"
    assert normalized.item_number == "12"
    assert normalized.edition_title == "Standard Edition"
    assert normalized.publisher == "DC Comics"
    assert normalized.release_date == date(2000, 9, 20)
    assert normalized.page_count == 36
    assert normalized.barcode == "76194122054301211"
    assert normalized.cover_price_cents == 295
    assert normalized.currency == "USD"
    assert normalized.provider_ids == {"gcd": "256114"}
    assert normalized.volume_provider_ids == {"gcd": "6139"}
    assert normalized.volume_start_year == 1999
    assert ("Mark Chiarello", "editing") in [
        (credit.name, credit.role) for credit in normalized.creators
    ]
    assert ("Jeph Loeb", "script") in [(credit.name, credit.role) for credit in normalized.creators]
    assert ("Tim Sale", "pencils") in [(credit.name, credit.role) for credit in normalized.creators]
    assert "Batman [Bruce Wayne]" in [credit.name for credit in normalized.characters]
    assert (
        normalized.cover_image_url
        == "https://files1.comics.org//img/gcd/covers_by_id/237/w400/237538.jpg"
    )
    assert normalized.synopsis == "Two-Face seeks revenge."


@pytest.mark.asyncio
async def test_gcd_provider_normalizes_variant_issue_payload():
    normalized = await GCDProvider().normalize(gcd_variant_issue_raw())

    assert normalized.title == "Absolute Batman"
    assert normalized.item_number == "1"
    assert normalized.edition_title == "Standard Edition"
    assert normalized.variant_name == "Jim Lee & Scott Williams Cardstock Variant Cover"
    assert normalized.variant_type == "variant"
    assert normalized.volume_start_year == 2024
    assert normalized.publisher == "DC Comics"
    assert normalized.release_date == date(2024, 10, 9)
    assert normalized.page_count == 52
    assert normalized.barcode == "76194138584600121"
    assert normalized.cover_price_cents == 599
    assert normalized.currency == "USD"
    assert normalized.provider_ids == {"gcd": "2665653"}
    assert normalized.volume_provider_ids == {"gcd": "216143"}
    assert (
        normalized.cover_image_url
        == "https://files1.comics.org//img/gcd/covers_by_id/1791/w400/1791589.jpg"
    )


@pytest.mark.asyncio
async def test_gcd_provider_search_uses_issue_query(monkeypatch):
    async def fake_request(self, path):
        assert path == "series/name/Batman/issue/12/"
        return {
            "results": [
                {
                    "api_url": "https://www.comics.org/api/issue/999999/",
                    "series_name": "Absolute Batman (2024 series)",
                    "descriptor": "12",
                    "publication_date": "November 2025",
                    "price": "4.99 USD",
                    "page_count": "32.000",
                    "variant_of": None,
                },
                {
                    "api_url": "https://www.comics.org/api/issue/256114/",
                    "series_name": "Batman: Dark Victory (1999 series)",
                    "descriptor": "12",
                    "publication_date": "November 2000",
                    "price": "2.95 USD",
                    "page_count": "36.000",
                    "variant_of": None,
                },
            ]
        }

    monkeypatch.setattr(GCDProvider, "_request", fake_request)

    results = await GCDProvider().search("  Batman # 12  ")

    assert len(results) == 2
    assert results[0].provider == "gcd"
    assert results[0].provider_item_id == "256114"
    assert results[0].title == "Batman: Dark Victory (1999 series) #12"
    assert results[0].summary == "November 2000 · 2.95 USD · 36 pages"


@pytest.mark.asyncio
async def test_gcd_provider_search_requires_issue_number():
    results = await GCDProvider().search("Batman")

    assert results == []


@pytest.mark.asyncio
async def test_comicvine_provider_stub_search_uses_stable_slug(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", None)

    results = await ComicVineProvider().search("  Spider-Man: Vol. 2  ")

    assert len(results) == 1
    assert results[0].provider_item_id == "stub-comic-spider-man-vol-2"
    assert results[0].title == "Spider-Man: Vol. 2 (ComicVine stub)"


@pytest.mark.asyncio
async def test_admin_provider_search_uses_provider_results(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_search(self, query):
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    response = await client.post(
        "/admin/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "query": "spider"},
    )

    assert response.status_code == 200
    assert response.json()[0]["provider_item_id"] == "4000-12345"
    assert response.json()[0]["title"] == "The Amazing Spider-Man #1 The Spider Strikes"


@pytest.mark.asyncio
async def test_admin_provider_search_rejects_unconfigured_provider(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    response = await client.post(
        "/admin/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "anilist", "query": "naruto"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provider 'anilist' is not configured"


@pytest.mark.asyncio
async def test_admin_ingest_upserts_comicvine_issue(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    indexed_documents = []

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="comicvine", provider_item_id="4000-12345", raw=comicvine_issue_raw()
        )

    async def fake_index_documents(self, documents):
        indexed_documents.extend(documents)
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "12345"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["title"] == "The Amazing Spider-Man"
    assert body["item"]["item_number"] == "1"
    assert body["item"]["series_title"] == "The Amazing Spider-Man"
    assert body["item"]["volume_name"] == "The Amazing Spider-Man"
    assert body["item"]["volume_start_year"] == 1963
    assert body["item"]["page_count"] == 32
    assert body["item"]["cover_date"] == "1963-03-01"
    assert body["item"]["store_date"] == "1963-02-10"
    assert body["item"]["publisher"] == "Marvel"
    assert body["item"]["creators"] == [
        {
            "name": "Stan Lee",
            "role": "Writer",
            "api_detail_url": None,
            "site_detail_url": None,
        },
        {
            "name": "Steve Ditko",
            "role": "Artist",
            "api_detail_url": None,
            "site_detail_url": None,
        },
    ]
    assert body["item"]["characters"][0]["name"] == "Spider-Man"
    assert body["item"]["story_arcs"][0]["name"] == "The Spider Strikes"
    assert body["item"]["provider_links"][0] == {
        "provider": "comicvine",
        "entity_type": "item",
        "provider_item_id": "4000-12345",
        "site_url": "https://comicvine.gamespot.com/amazing-spider-man-1/4000-12345/",
        "api_url": "https://comicvine.gamespot.com/api/issue/4000-12345/",
    }
    assert body["item"]["editions"][0]["publisher"] == "Marvel"
    assert (
        body["item"]["editions"][0]["variants"][0]["cover_image_url"]
        == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    )
    assert body["item"]["editions"][0]["variants"][0]["thumbnail_image_url"] is None
    assert indexed_documents == [
        {
            "id": body["item_id"],
            "kind": "comic",
            "title": "The Amazing Spider-Man",
            "item_number": "1",
            "cover_image_url": "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
            "thumbnail_image_url": None,
            "publisher": "Marvel",
            "release_date": "1963-03-01",
            "region": "US",
            "release_year": 1963,
            "barcode": None,
            "barcodes": [],
            "variant": "Cover A",
            "variant_names": ["Cover A"],
            "series_title": "The Amazing Spider-Man",
            "volume_name": "The Amazing Spider-Man",
            "creators": ["Stan Lee", "Steve Ditko"],
            "characters": ["Spider-Man"],
            "story_arcs": ["The Spider Strikes"],
        }
    ]

    second_response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "4000-12345"},
    )
    assert second_response.status_code == 201
    assert second_response.json()["created"] is False
    assert second_response.json()["item_id"] == body["item_id"]

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Item)) == 1
        assert await db.scalar(select(func.count()).select_from(Series)) == 1
        assert await db.scalar(select(func.count()).select_from(Volume)) == 1
        assert await db.scalar(select(func.count()).select_from(Variant)) == 1
        assert await db.scalar(select(func.count()).select_from(Release)) == 1
        assert await db.scalar(select(func.count()).select_from(Organization)) == 1
        assert await db.scalar(select(func.count()).select_from(EntityOrganization)) == 1
        assert await db.scalar(select(func.count()).select_from(Person)) == 2
        assert await db.scalar(select(func.count()).select_from(EntityPerson)) == 2
        assert await db.scalar(select(func.count()).select_from(Tag)) == 2
        assert await db.scalar(select(func.count()).select_from(EntityTag)) == 2
        provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id).order_by(
                ExternalProviderId.provider_item_id
            )
        )
        assert list(provider_ids) == ["4000-12345", "4050-6789"]
        publisher = await db.scalar(select(Organization.name))
        assert publisher == "Marvel"
        roles = await db.scalars(select(EntityPerson.role).order_by(EntityPerson.role))
        assert list(roles) == ["Artist", "Writer"]
        tags = await db.scalars(select(Tag.name).order_by(Tag.kind, Tag.name))
        assert list(tags) == ["Spider-Man", "The Spider Strikes"]
        cover = await db.scalar(select(Variant.cover_image_key))
        assert cover is None
        thumbnail = await db.scalar(select(Variant.thumbnail_image_key))
        assert thumbnail is None


@pytest.mark.asyncio
async def test_admin_ingest_upserts_gcd_issue_with_bibliographic_fields(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    indexed_documents = []

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="gcd", provider_item_id="256114", raw=gcd_issue_raw())

    async def fake_index_documents(self, documents):
        indexed_documents.extend(documents)
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "provider_item_id": "256114"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["title"] == "Batman: Dark Victory"
    assert body["item"]["item_number"] == "12"
    assert body["item"]["series_title"] == "Batman: Dark Victory"
    assert body["item"]["volume_start_year"] == 1999
    assert body["item"]["publisher"] == "DC Comics"
    assert body["item"]["editions"][0]["release_date"] == "2000-09-20"
    assert body["item"]["barcode"] == "76194122054301211"
    assert body["item"]["cover_price_cents"] == 295
    assert body["item"]["currency"] == "USD"
    assert body["item"]["provider_links"][0]["provider"] == "gcd"
    assert body["item"]["provider_links"][0]["provider_item_id"] == "256114"
    variant = body["item"]["editions"][0]["variants"][0]
    assert variant["name"] == "Cover A"
    assert variant["barcode"] == "76194122054301211"
    assert variant["cover_price_cents"] == 295
    assert variant["currency"] == "USD"
    assert (
        variant["cover_image_url"]
        == "https://files1.comics.org//img/gcd/covers_by_id/237/w400/237538.jpg"
    )
    assert indexed_documents[0]["barcode"] == "76194122054301211"
    assert indexed_documents[0]["barcodes"] == ["76194122054301211"]
    assert indexed_documents[0]["variant"] == "Cover A"

    async with AsyncSessionLocal() as db:
        provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id).order_by(
                ExternalProviderId.provider_item_id
            )
        )
        assert list(provider_ids) == ["256114", "6139"]


@pytest.mark.asyncio
async def test_admin_ingest_reuses_existing_gcd_volume_provider_link(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    primary_issue = gcd_variant_issue_raw()
    primary_issue.update(
        {
            "api_url": "https://www.comics.org/api/issue/2663120/",
            "descriptor": "1 [Nick Dragotta Cover]",
            "variant_name": "Nick Dragotta Cover",
            "variant_of": None,
            "price": "4.99 USD",
            "barcode": "76194138584600111",
            "page_count": "48.000",
        }
    )
    variant_issue = gcd_variant_issue_raw()
    issues = {"2663120": primary_issue, "2665653": variant_issue}

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="gcd", provider_item_id=provider_item_id, raw=issues[provider_item_id]
        )

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    for provider_item_id in issues:
        response = await client.post(
            "/admin/providers/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "gcd", "provider_item_id": provider_item_id},
        )

        assert response.status_code == 201
        assert response.json()["created"] is True

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Item)) == 2
        assert await db.scalar(select(func.count()).select_from(Volume)) == 1
        provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id).order_by(
                ExternalProviderId.provider_item_id
            )
        )
        assert list(provider_ids) == ["216143", "2663120", "2665653"]


@pytest.mark.asyncio
async def test_admin_ingest_can_mirror_provider_cover_when_enabled(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "mirror_provider_images", True)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="comicvine", provider_item_id="4000-12345", raw=comicvine_issue_raw()
        )

    async def fake_index_documents(self, documents):
        return True

    async def fake_mirror_cover(self, source_url, provider, provider_item_id):
        assert source_url == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
        return MirroredImage(
            key="covers/comicvine/4000-12345/cover.webp",
            url="http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.webp",
            content_type="image/webp",
        )

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fake_mirror_cover)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "12345"},
    )

    assert response.status_code == 201
    body = response.json()
    variant = body["item"]["editions"][0]["variants"][0]
    assert (
        variant["cover_image_url"]
        == "http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.webp"
    )
    assert variant["thumbnail_image_url"] is None

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(Variant.cover_image_key)) == (
            "covers/comicvine/4000-12345/cover.webp"
        )
        assert await db.scalar(select(Variant.thumbnail_image_key)) is None
