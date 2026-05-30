from datetime import date
from uuid import UUID
from uuid import uuid4

from types import SimpleNamespace

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    BundleRelease,
    BundleReleaseItem,
    Character,
    CharacterAppearance,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    Item,
    Organization,
    Person,
    Series,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
)
from app.providers.base import NormalizedEpisode, NormalizedSeason, ProviderSearchResult
from app.repositories.metadata import MetadataRepository
from app.schemas.metadata import ProviderLink, item_response_from_model
from app.search.documents import item_search_document
from app.services.metadata import MetadataService
from tests.helpers import register_and_login, seed_comic


async def _attach_bundle_release(
    item_id: str,
    *,
    title: str = "The Amazing Spider-Man Starter Box",
    barcode: str = "9781300000000",
) -> UUID:
    async with AsyncSessionLocal() as db:
        item = await db.scalar(
            select(Item)
            .options(selectinload(Item.volume).selectinload(Volume.series))
            .where(Item.id == UUID(item_id))
        )
        assert item is not None
        bundle = BundleRelease(
            kind=item.kind,
            title=title,
            bundle_type="box_set",
            primary_item_id=item.id,
            series_id=item.volume.series.id,
            volume_id=item.volume.id,
            format="Paperback",
            variant_type="physical",
            packaging_type="box",
            publisher="Marvel",
            barcode=barcode,
            release_date=date(2025, 1, 15),
        )
        db.add(bundle)
        await db.flush()
        db.add(
            BundleReleaseItem(
                bundle_release_id=bundle.id,
                item_id=item.id,
                role="main",
                sequence_number=1,
                quantity=1,
                is_primary=True,
            )
        )
        await db.commit()
        return bundle.id


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
    assert "manga" not in rows
    assert "anime" not in rows
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
async def test_item_detail_and_series_expose_series_tags(client):
    token = await register_and_login(client)
    item_id, _, _ = await seed_comic()

    async with AsyncSessionLocal() as db:
        item = await db.get(Item, UUID(item_id))
        assert item is not None
        series_id = await db.scalar(
            select(Series.id)
            .join(Volume, Volume.series_id == Series.id)
            .join(Item, Item.volume_id == Volume.id)
            .where(Item.id == UUID(item_id))
        )
        assert series_id is not None
        action = Tag(kind="series_tag:comic", name="Street-level")
        legacy = Tag(kind="series_tag:comic", name="Legacy Hero")
        db.add_all([action, legacy])
        await db.flush()
        db.add_all(
            [
                EntityTag(entity_type="series", entity_id=series_id, tag_id=action.id),
                EntityTag(entity_type="series", entity_id=series_id, tag_id=legacy.id),
            ]
        )
        await db.commit()

    detail_response = await client.get(
        f"/comics/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert detail_response.json()["tags"] == ["Legacy Hero", "Street-level"]



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
    item_id, edition_id, _ = await seed_comic()

    async with AsyncSessionLocal() as db:
        edition = await db.get(Edition, UUID(edition_id))
        assert edition is not None
        edition.imprint = "Marvel Knights"
        edition.subtitle = "Collector Edition"
        edition.series_group = "Spider-Verse"
        edition.region = "US"
        edition.age_rating = "Teen"
        edition.catalog_number = "ASM-001"
        edition.release_status = "released"
        await db.commit()

    response = await client.get(
        "/search",
        params={
            "kind": "comic",
            "series": "Amazing",
            "issue_number": "1",
            "publisher": "Marvel",
            "imprint": "Marvel Knights",
            "subtitle": "Collector Edition",
            "series_group": "Spider-Verse",
            "country": "US",
            "language": "en",
            "age_rating": "Teen",
            "catalog_number": "ASM-001",
            "release_status": "released",
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
    assert response.json()[0]["imprint"] == "Marvel Knights"
    assert response.json()[0]["catalog_number"] == "ASM-001"


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
async def test_search_supports_bundle_release_title(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()
    await _attach_bundle_release(item_id, title="Spider-Verse Collector Box")

    response = await client.get(
        "/search",
        params={"q": "Collector Box", "kind": "comic"},
    )

    assert response.status_code == 200
    assert response.json()[0]["id"] == item_id
    assert response.json()[0]["title"] == "The Amazing Spider-Man"
    assert response.json()[0]["bundle_titles"] == ["Spider-Verse Collector Box"]


@pytest.mark.asyncio
async def test_search_prefers_normalized_relations_over_edition_json(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, edition_id, _ = await seed_comic()

    async with AsyncSessionLocal() as db:
        item = await db.get(Item, UUID(item_id))
        edition = await db.get(Edition, UUID(edition_id))
        assert item is not None
        assert edition is not None
        edition.metadata_json = {
            "normalized": {
                "creators": [{"name": "Stale Writer", "role": "writer"}],
                "characters": ["Old Spider-Man"],
                "story_arcs": ["Outdated Arc"],
            },
            "source": {
                "person_credits": [{"name": "Stale Writer", "role": "writer"}],
                "character_credits": [{"name": "Old Spider-Man"}],
                "story_arc_credits": [{"name": "Outdated Arc"}],
            },
        }
        creator = Person(
            name="Stan Lee",
            metadata_json={
                "api_detail_url": "https://api.example/stan-lee",
                "site_detail_url": "https://example.com/stan-lee",
                "image_url": "https://cdn.example/stan-lee.jpg",
            },
        )
        character = Character(name="Spider-Man [Peter Parker]")
        story_arc = StoryArc(name="If This Be My Destiny", publisher="Marvel")
        db.add_all([creator, character, story_arc])
        await db.flush()
        db.add_all(
            [
                EntityPerson(
                    entity_type="item",
                    entity_id=item.id,
                    person_id=creator.id,
                    role="writer",
                ),
                CharacterAppearance(character_id=character.id, item_id=item.id, role="main"),
                StoryArcItem(story_arc_id=story_arc.id, item_id=item.id, ordinal=1),
            ]
        )
        await db.commit()

    response = await client.get("/search", params={"q": "spider", "kind": "comic"})

    assert response.status_code == 200
    body = response.json()[0]
    assert [(credit["name"], credit["role"]) for credit in body["creators"]] == [
        ("Stan Lee", "writer")
    ]
    assert body["creators"][0]["api_detail_url"] == "https://api.example/stan-lee"
    assert body["characters"] == ["Spider-Man [Peter Parker]"]
    assert body["story_arcs"] == ["If This Be My Destiny"]

    async with AsyncSessionLocal() as db:
        item = await MetadataRepository(db).get_item(UUID(item_id), ItemKind.comic)

    assert item is not None
    document = item_search_document(item)
    assert document["creators"] == ["Stan Lee"]
    assert document["characters"] == ["Spider-Man [Peter Parker]"]
    assert document["story_arcs"] == ["If This Be My Destiny"]


@pytest.mark.asyncio
async def test_lookup_bundle_barcode_returns_primary_item(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, _, _ = await seed_comic()
    await _attach_bundle_release(item_id, barcode="9781300000000")

    response = await client.get("/barcode/9781300000000", params={"kind": "comic"})

    assert response.status_code == 200
    assert response.json()["id"] == item_id
    assert response.json()["title"] == "The Amazing Spider-Man"
    assert response.json()["bundle_titles"] == ["The Amazing Spider-Man Starter Box"]


@pytest.mark.asyncio
async def test_item_bundle_release_endpoints(client):
    token = await register_and_login(client)
    item_id, _, _ = await seed_comic()
    bundle_id = await _attach_bundle_release(item_id)

    list_response = await client.get(
        f"/metadata/items/{item_id}/bundle-releases",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert list_response.status_code == 200
    bundles = list_response.json()
    assert len(bundles) == 1
    assert bundles[0]["id"] == str(bundle_id)
    assert bundles[0]["title"] == "The Amazing Spider-Man Starter Box"
    assert bundles[0]["content_summary"]["total_items"] == 1
    assert bundles[0]["primary_item_id"] == item_id

    detail_response = await client.get(
        f"/metadata/bundle-releases/{bundle_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["id"] == str(bundle_id)
    assert detail["members"][0]["item_id"] == item_id
    assert detail["members"][0]["role"] == "main"
    assert detail["series_title"] == "The Amazing Spider-Man"


@pytest.mark.asyncio
async def test_item_bundle_release_list_returns_404_for_unknown_item(client):
    token = await register_and_login(client)

    response = await client.get(
        f"/metadata/items/{uuid4()}/bundle-releases",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_bundle_release_detail_returns_404_for_unknown_bundle(client):
    token = await register_and_login(client)

    response = await client.get(
        f"/metadata/bundle-releases/{uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 404


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
async def test_barcode_provider_search_returns_musicbrainz_results(client, monkeypatch):
    token = await register_and_login(client)

    async def fake_search_by_barcode(self, barcode, kind=None):
        from app.providers.base import ProviderSearchResult

        return [
            ProviderSearchResult(
                provider="musicbrainz",
                provider_item_id="release-1234",
                title="Test Album",
                kind=ItemKind.music,
                summary="Barcode match",
            )
        ]

    from app.providers.musicbrainz import MusicBrainzProvider

    monkeypatch.setattr(MusicBrainzProvider, "search_by_barcode", fake_search_by_barcode)

    response = await client.get(
        "/barcode/0028948612345/providers",
        headers={"Authorization": f"Bearer {token}"},
        params={"kind": "music"},
    )

    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 1
    assert data[0]["provider"] == "musicbrainz"
    assert data[0]["provider_item_id"] == "release-1234"
    assert data[0]["title"] == "Test Album"


@pytest.mark.asyncio
async def test_barcode_provider_search_uses_query_cache(client, monkeypatch):
    token = await register_and_login(client)
    calls = 0

    async def fake_search_by_barcode(self, barcode, kind=None):
        nonlocal calls
        calls += 1
        from app.providers.base import ProviderSearchResult

        return [
            ProviderSearchResult(
                provider="musicbrainz",
                provider_item_id="release-1234",
                title="Test Album",
                kind=ItemKind.music,
                summary="Barcode match",
            )
        ]

    from app.providers.musicbrainz import MusicBrainzProvider

    monkeypatch.setattr(MusicBrainzProvider, "search_by_barcode", fake_search_by_barcode)

    for _ in range(2):
        response = await client.get(
            "/barcode/0028948612345/providers",
            headers={"Authorization": f"Bearer {token}"},
            params={"kind": "music"},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data) >= 1
        assert data[0]["provider_item_id"] == "release-1234"

    assert calls == 1


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
    assert document["runtime_minutes"] is None
    assert document["variant"] == "Cover A"


@pytest.mark.asyncio
async def test_search_document_indexes_bundle_release_metadata():
    item_id, _, _ = await seed_comic()
    await _attach_bundle_release(
        item_id,
        title="Spider-Verse Collector Box",
        barcode="9781300000000",
    )

    async with AsyncSessionLocal() as db:
        item = await MetadataRepository(db).get_item(UUID(item_id), ItemKind.comic)

    assert item is not None
    document = item_search_document(item)

    assert document["bundle_titles"] == ["Spider-Verse Collector Box"]
    assert len(document["bundle_release_ids"]) == 1
    assert "9781300000000" in document["barcodes"]


def test_item_response_from_model_exposes_normalized_metadata_fields():
    item = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.game,
        title="Mass Effect Legendary Edition",
        item_number=None,
        sort_key=None,
        synopsis=None,
        release_type=None,
        season_number=None,
        episode_number=None,
        runtime_minutes=92,
        page_count=None,
        metadata_json=None,
        volume=SimpleNamespace(
            id=uuid4(),
            name="Legendary Edition",
            volume_number=1,
            start_year=2021,
            series=SimpleNamespace(
                id=uuid4(),
                title="Mass Effect",
            ),
        ),
        organization_links=[
            SimpleNamespace(
                role="publisher",
                organization=SimpleNamespace(name="Electronic Arts"),
            ),
            SimpleNamespace(
                role="imprint",
                organization=SimpleNamespace(name="BioWare"),
            ),
        ],
        editions=[
            SimpleNamespace(
                id=uuid4(),
                title="Standard",
                format="Digital",
                publisher="Stale Publisher",
                isbn=None,
                upc="014633742207",
                language="en",
                region="WW",
                imprint="Stale Imprint",
                subtitle="N7 Collection",
                series_group="Mass Effect Trilogy",
                age_rating="Mature 17+",
                catalog_number="ME-LE-2021",
                release_status="Released",
                release_date=date(2021, 5, 14),
                metadata_json={
                    "provider": "igdb",
                    "provider_item_id": "igdb-123",
                    "normalized": {
                        "catalog_number": "STALE-CATALOG",
                        "release_status": "Stale",
                        "language": "de",
                        "country": "DE",
                        "imprint": "Stale Studio",
                        "subtitle": "Stale Subtitle",
                        "series_group": "Stale Group",
                        "age_rating": "Everyone",
                        "platforms": ["PC", "Xbox One", "PlayStation 4"],
                        "track_count": 2,
                        "tracks": [
                            {
                                "position": 1,
                                "title": "Main Theme",
                                "duration_seconds": 180,
                            },
                            {
                                "position": 2,
                                "title": "Suicide Mission",
                                "duration_seconds": 215,
                                "disc_number": 1,
                            },
                        ],
                    },
                },
                variants=[
                    SimpleNamespace(
                        id=uuid4(),
                        name="Standard",
                        variant_type="digital",
                        sku=None,
                        barcode=None,
                        isbn=None,
                        region=None,
                        platform=None,
                        cover_price_cents=None,
                        currency=None,
                        cover_image_url=None,
                        thumbnail_image_url=None,
                        description=None,
                        metadata_json=None,
                        is_primary=True,
                    )
                ],
                releases=[],
            )
        ],
    )

    response = item_response_from_model(item)

    assert response.publisher == "Electronic Arts"
    assert response.barcode == "014633742207"
    assert response.catalog_number == "ME-LE-2021"
    assert response.track_count == 2
    assert response.tracks == [
        {"position": 1, "title": "Main Theme", "duration_seconds": 180},
        {
            "position": 2,
            "title": "Suicide Mission",
            "duration_seconds": 215,
            "disc_number": 1,
        },
    ]
    assert response.platforms == ["PC", "Xbox One", "PlayStation 4"]
    assert response.release_status == "Released"
    assert response.language == "en"
    assert response.country == "WW"
    assert response.imprint == "BioWare"
    assert response.subtitle == "N7 Collection"
    assert response.series_group == "Mass Effect Trilogy"
    assert response.age_rating == "Mature 17+"
    assert response.runtime_minutes == 92
    assert response.series_title == "Mass Effect"
    assert response.volume_name == "Legendary Edition"
    assert response.editions[0].imprint == "BioWare"
    assert response.editions[0].catalog_number == "ME-LE-2021"
    assert response.editions[0].release_status == "Released"
    assert response.provider_links[0].provider.value == "igdb"
    assert response.provider_links[0].provider_item_id == "igdb-123"


def test_item_response_merges_persisted_provider_link_urls():
    item = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.game,
        title="Mass Effect Legendary Edition",
        item_number=None,
        sort_key=None,
        synopsis=None,
        release_type=None,
        season_number=None,
        episode_number=None,
        runtime_minutes=None,
        page_count=None,
        metadata_json=None,
        volume=None,
        editions=[],
        primary_bundle_releases=[],
    )

    response = item_response_from_model(
        item,
        extra_provider_links=[
            ProviderLink(
                provider=ExternalProvider.igdb,
                entity_type="item",
                provider_item_id="igdb-123",
                site_url="https://www.igdb.com/games/mass-effect-legendary-edition",
                api_url="https://api.igdb.com/v4/games/123",
            )
        ],
    )

    assert [link.model_dump(mode="json") for link in response.provider_links] == [
        {
            "provider": "igdb",
            "entity_type": "item",
            "provider_item_id": "igdb-123",
            "site_url": "https://www.igdb.com/games/mass-effect-legendary-edition",
            "api_url": "https://api.igdb.com/v4/games/123",
        }
    ]


def test_item_response_from_model_synthesizes_video_release_when_missing_editions():
    item_id = uuid4()
    item = SimpleNamespace(
        id=item_id,
        kind=ItemKind.movie,
        title="Spirited Away",
        item_number=None,
        sort_key=None,
        synopsis=None,
        release_type=None,
        season_number=None,
        episode_number=None,
        runtime_minutes=125,
        page_count=None,
        metadata_json={
                "provider": "tmdb",
                "provider_item_id": "movie:129",
                "normalized": {
                    "kind": "movie",
                "release_date": "2001-07-20",
                "language": "ja",
                "country": "JP",
                "cover_image_url": "https://images.example/spirited-away.jpg",
                "thumbnail_image_url": "https://images.example/spirited-away-thumb.jpg",
            },
        },
        volume=None,
        editions=[],
        primary_bundle_releases=[],
    )

    response = item_response_from_model(item)

    assert response.editions == []
    assert response.runtime_minutes == 125
    assert response.language is None
    assert response.country is None


def test_item_response_prefers_organization_links_for_publisher_and_imprint():
    item = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.comic,
        title="Saga #1",
        item_number="1",
        sort_key=None,
        synopsis=None,
        release_type=None,
        season_number=None,
        episode_number=None,
        runtime_minutes=None,
        page_count=32,
        metadata_json=None,
        volume=None,
        primary_bundle_releases=[],
        organization_links=[
            SimpleNamespace(
                role="publisher",
                organization=SimpleNamespace(name="Image Comics"),
            ),
            SimpleNamespace(
                role="imprint",
                organization=SimpleNamespace(name="Skybound"),
            ),
        ],
        editions=[
            SimpleNamespace(
                id=uuid4(),
                title="Issue #1",
                format="Single Issue",
                publisher="Stale Publisher",
                isbn=None,
                upc=None,
                language=None,
                region=None,
                imprint="Stale Imprint",
                subtitle=None,
                series_group=None,
                age_rating=None,
                catalog_number=None,
                release_status=None,
                release_date=date(2012, 3, 14),
                metadata_json=None,
                variants=[],
            )
        ],
    )

    response = item_response_from_model(item)

    assert response.publisher == "Image Comics"
    assert response.imprint == "Skybound"


@pytest.mark.asyncio
async def test_search_document_and_search_result_prefer_item_organization_links():
    async with AsyncSessionLocal() as db:
        item = Item(kind=ItemKind.comic, title="Invincible", item_number="1")
        edition = Edition(item=item, title="Issue #1", publisher="Stale Publisher", imprint="Stale Imprint")
        publisher = Organization(name="Image Comics")
        imprint = Organization(name="Skybound")
        db.add_all([item, edition, publisher, imprint])
        await db.flush()
        db.add_all(
            [
                EntityOrganization(
                    entity_type="item",
                    entity_id=item.id,
                    organization_id=publisher.id,
                    role="publisher",
                ),
                EntityOrganization(
                    entity_type="item",
                    entity_id=item.id,
                    organization_id=imprint.id,
                    role="imprint",
                ),
            ]
        )
        await db.commit()
        loaded = await MetadataRepository(db).get_item(item.id, ItemKind.comic)

    assert loaded is not None
    document = item_search_document(loaded)
    service = MetadataService.__new__(MetadataService)
    result = MetadataService._search_result(service, loaded, None, None)

    assert document["publisher"] == "Image Comics"
    assert document["imprint"] == "Skybound"
    assert result.publisher == "Image Comics"
    assert result.imprint == "Skybound"


def test_search_result_exposes_runtime_minutes():
    service = MetadataService.__new__(MetadataService)
    item = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.movie,
        title="Blade Runner 2049",
        item_number=None,
        synopsis="A young blade runner uncovers a secret.",
        runtime_minutes=164,
        page_count=None,
        editions=[],
        series=None,
        volume=None,
    )

    result = MetadataService._search_result(service, item, None, None)

    assert result.title == "Blade Runner 2049"
    assert result.runtime_minutes == 164


def test_search_result_sorts_bundle_releases_by_known_date_then_title():
    service = MetadataService.__new__(MetadataService)
    item = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.music,
        title="Anthology",
        item_number=None,
        synopsis=None,
        runtime_minutes=None,
        page_count=None,
        editions=[],
        series=None,
        volume=None,
        primary_bundle_releases=[
            SimpleNamespace(id=uuid4(), title="Zulu Box", release_date=None),
            SimpleNamespace(id=uuid4(), title="Bravo Box", release_date=date(2024, 6, 1)),
            SimpleNamespace(id=uuid4(), title="Alpha Box", release_date=date(2024, 6, 1)),
            SimpleNamespace(id=uuid4(), title="Latest Box", release_date=date(2025, 1, 1)),
        ],
    )

    result = MetadataService._search_result(service, item, None, None)

    assert result.bundle_titles == [
        "Latest Box",
        "Alpha Box",
        "Bravo Box",
        "Zulu Box",
    ]


def test_provider_search_query_uses_artist_and_release_for_music():
    service = MetadataService.__new__(MetadataService)

    result = MetadataService._provider_search_query(
        service,
        "Abyss",
        ItemKind.music,
        series="Ad Infinitum",
        issue_number=None,
        year=2024,
    )

    assert result == 'artist:"Ad Infinitum" AND release:"Abyss" AND date:2024'


def test_provider_search_query_prefers_album_field_for_music():
    service = MetadataService.__new__(MetadataService)

    result = MetadataService._provider_search_query(
        service,
        "Ad Infinitum Abyss Napalm Records",
        ItemKind.music,
        series="Ad Infinitum",
        issue_number="Abyss",
        year=2024,
    )

    assert result == 'artist:"Ad Infinitum" AND release:"Abyss" AND date:2024'


@pytest.mark.asyncio
async def test_get_item_volumes_falls_back_to_mangadex_search(client, monkeypatch):
    async def fake_search(self, query, kind=None):
        assert query == "One Piece"
        assert kind == ItemKind.comic
        return [
            ProviderSearchResult(
                provider="mangadex",
                provider_item_id="mangadex-one-piece",
                title="One Piece",
                kind=ItemKind.comic,
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
                        page_count=53,
                    )
                ],
            )
        ]

    monkeypatch.setattr("app.providers.mangadex.MangaDexProvider.search", fake_search)
    monkeypatch.setattr("app.providers.mangadex.MangaDexProvider.get_volumes", fake_get_volumes)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.comic, title="One Piece")
        volume = Volume(
            series=series,
            name="One Piece (1997)",
            volume_number=1,
            start_year=1997,
        )
        item = Item(kind=ItemKind.comic, title="One Piece", volume=volume)
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
    assert body[0]["episodes"][0]["page_count"] == 53
    assert body[0]["episodes"][0]["runtime_minutes"] is None


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
            "image_url": None,
            "description": None,
            "ordinal": 1,
            "publisher": "Marvel",
        }
    ]


@pytest.mark.asyncio
async def test_item_detail_exposes_creator_image_urls(client):
    item_id, _, _ = await seed_comic()
    item_uuid = UUID(item_id)

    async with AsyncSessionLocal() as db:
        creator = Person(
            name="J.R.R. Tolkien",
            metadata_json={
                "image_url": "https://cdn.example/tolkien.jpg",
                "site_detail_url": "https://hardcover.app/authors/tolkien",
            },
        )
        db.add(creator)
        await db.flush()
        db.add(
            EntityPerson(
                entity_type="item",
                entity_id=item_uuid,
                person_id=creator.id,
                role="Author",
            )
        )
        await db.commit()

    token = await register_and_login(client)
    response = await client.get(
        f"/comics/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json()["creators"] == [
        {
            "name": "J.R.R. Tolkien",
            "role": "Author",
            "api_detail_url": None,
            "site_detail_url": "https://hardcover.app/authors/tolkien",
            "image_url": "https://cdn.example/tolkien.jpg",
        }
    ]
