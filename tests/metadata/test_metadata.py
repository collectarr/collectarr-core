from datetime import date
from uuid import UUID

import pytest

from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import (
    Character,
    CharacterAppearance,
    Edition,
    Item,
    Series,
    StoryArc,
    StoryArcItem,
    Variant,
    Volume,
)
from app.providers.base import NormalizedEpisode, NormalizedSeason, ProviderSearchResult
from app.repositories.metadata import MetadataRepository
from app.search.documents import item_search_document
from tests.helpers import register_and_login, seed_comic


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
    assert rows["manga"]["default_provider"] == "mangadex"
    assert rows["manga"]["providers"] == ["mangadex", "anilist", "comicvine"]
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


@pytest.mark.asyncio
async def test_get_item_volumes_falls_back_to_mangadex_search(client, monkeypatch):
    async def fake_search(self, query, kind=None):
        assert query == "One Piece"
        assert kind == ItemKind.manga
        return [
            ProviderSearchResult(
                provider="mangadex",
                provider_item_id="mangadex-one-piece",
                title="One Piece",
                kind=ItemKind.manga,
            )
        ]

    async def fake_get_volumes(self, provider_item_id):
        assert provider_item_id == "mangadex-one-piece"
        return [
            NormalizedSeason(
                season_number=1,
                title="Volume 1",
                episode_count=1,
                episodes=[
                    NormalizedEpisode(
                        episode_number=1,
                        title="Romance Dawn",
                        runtime_minutes=53,
                    )
                ],
            )
        ]

    monkeypatch.setattr("app.providers.mangadex.MangaDexProvider.search", fake_search)
    monkeypatch.setattr("app.providers.mangadex.MangaDexProvider.get_volumes", fake_get_volumes)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.manga, title="One Piece")
        volume = Volume(
            series=series,
            name="One Piece (1997)",
            volume_number=1,
            start_year=1997,
        )
        item = Item(kind=ItemKind.manga, title="One Piece", volume=volume)
        edition = Edition(item=item, title="Tankobon", format="Manga")
        variant = Variant(edition=edition, name="Standard", is_primary=True)
        db.add_all([series, volume, item, edition, variant])
        await db.commit()
        item_id = str(item.id)

    token = await register_and_login(client)
    response = await client.get(
        f"/metadata/items/{item_id}/volumes",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["title"] == "Volume 1"
    assert body[0]["episode_count"] == 1
    assert body[0]["episodes"][0]["title"] == "Romance Dawn"


@pytest.mark.asyncio
async def test_story_arc_and_character_browse_endpoints(client):
    item_id, _, _ = await seed_comic()
    item_uuid = UUID(item_id)

    async with AsyncSessionLocal() as db:
        story_arc = StoryArc(name="The Night Gwen Stacy Died", publisher="Marvel")
        character = Character(
            name="Spider-Man",
            aliases=["Peter Parker"],
            description="Friendly neighborhood hero.",
            image_url="https://example.test/spider-man.jpg",
        )
        db.add_all([story_arc, character])
        await db.flush()
        db.add_all(
            [
                StoryArcItem(story_arc_id=story_arc.id, item_id=item_uuid, ordinal=1),
                CharacterAppearance(character_id=character.id, item_id=item_uuid, role="main"),
            ]
        )
        await db.commit()
        story_arc_id = str(story_arc.id)
        character_id = str(character.id)

    token = await register_and_login(client)
    headers = {"Authorization": f"Bearer {token}"}

    arcs_response = await client.get(
        "/story-arcs",
        params={"q": "gwen"},
        headers=headers,
    )
    assert arcs_response.status_code == 200
    arcs_body = arcs_response.json()
    assert len(arcs_body) == 1
    assert arcs_body[0]["id"] == story_arc_id
    assert arcs_body[0]["name"] == "The Night Gwen Stacy Died"
    assert arcs_body[0]["item_count"] == 1

    arc_items_response = await client.get(
        f"/story-arcs/{story_arc_id}/items",
        headers=headers,
    )
    assert arc_items_response.status_code == 200
    arc_items_body = arc_items_response.json()
    assert len(arc_items_body) == 1
    assert arc_items_body[0]["item_id"] == item_id
    assert arc_items_body[0]["ordinal"] == 1
    assert arc_items_body[0]["series_title"] == "The Amazing Spider-Man"

    arc_facets_response = await client.post(
        "/story-arcs/facets",
        json={"item_ids": [item_id]},
        headers=headers,
    )
    assert arc_facets_response.status_code == 200
    arc_facets_body = arc_facets_response.json()
    assert arc_facets_body == [
        {
            "id": story_arc_id,
            "name": "The Night Gwen Stacy Died",
            "description": None,
            "publisher": "Marvel",
            "start_date": None,
            "end_date": None,
            "item_count": 1,
            "item_ids": [item_id],
        }
    ]

    characters_response = await client.get(
        "/characters",
        params={"q": "spider"},
        headers=headers,
    )
    assert characters_response.status_code == 200
    characters_body = characters_response.json()
    assert len(characters_body) == 1
    assert characters_body[0]["id"] == character_id
    assert characters_body[0]["name"] == "Spider-Man"
    assert characters_body[0]["appearance_count"] == 1

    appearances_response = await client.get(
        f"/characters/{character_id}/appearances",
        headers=headers,
    )
    assert appearances_response.status_code == 200
    appearances_body = appearances_response.json()
    assert len(appearances_body) == 1
    assert appearances_body[0]["item_id"] == item_id
    assert appearances_body[0]["role"] == "main"

    character_facets_response = await client.post(
        "/characters/facets",
        json={"item_ids": [item_id]},
        headers=headers,
    )
    assert character_facets_response.status_code == 200
    character_facets_body = character_facets_response.json()
    assert character_facets_body == [
        {
            "id": character_id,
            "name": "Spider-Man",
            "aliases": ["Peter Parker"],
            "image_url": "https://example.test/spider-man.jpg",
            "item_count": 1,
            "item_ids": [item_id],
            "role_counts": {"main": 1},
        }
    ]

    detail_response = await client.get(f"/comics/{item_id}", headers=headers)
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert detail_body["characters"] == [
        {
            "name": "Spider-Man",
            "role": "main",
            "api_detail_url": None,
            "site_detail_url": None,
            "aliases": ["Peter Parker"],
            "description": "Friendly neighborhood hero.",
            "image_url": "https://example.test/spider-man.jpg",
            "first_appearance_item_id": None,
        }
    ]
    assert detail_body["story_arcs"] == [
        {
            "name": "The Night Gwen Stacy Died",
            "role": None,
            "api_detail_url": None,
            "site_detail_url": None,
            "description": None,
            "ordinal": 1,
            "publisher": "Marvel",
        }
    ]
