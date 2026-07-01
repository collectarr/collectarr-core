from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models import (
    BookContribution,
    BookEdition,
    BookIdentifier,
    BookSeries,
    BookSeriesMembership,
    BookWork,
    Character,
    CharacterAppearance,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicStoryArcMembership,
    ComicWork,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    Item,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    Organization,
    Person,
    Series,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import NormalizedEpisode, NormalizedSeason, ProviderSearchResult
from app.repositories.metadata import MetadataRepository
from app.schemas import ExternalProviderIdResponse, item_response_from_model
from app.search.documents import (
    book_work_search_document,
    comic_work_search_document,
    item_search_document,
)
from app.services.metadata import MetadataService
from tests.helpers import register_and_login, seed_comic


async def _seed_book_v1() -> tuple[UUID, UUID]:
    async with AsyncSessionLocal() as db:
        person = Person(name="J.R.R. Tolkien")
        db.add(person)
        await db.flush()
        work = BookWork(
            title="The Fellowship of the Ring",
            sort_title="fellowship of the ring",
            description="A hobbit begins the journey.",
            original_language="en",
            first_publication_date=date(1954, 7, 29),
        )
        db.add(work)
        await db.flush()
        series = BookSeries(title="The Lord of the Rings", slug="the-lord-of-the-rings")
        db.add(series)
        await db.flush()
        db.add(
            BookSeriesMembership(
                work_id=work.id,
                series_id=series.id,
                sequence=1,
                display_number="1",
            )
        )
        book_edition = BookEdition(
            work_id=work.id,
            display_title="The Fellowship of the Ring",
            format="Hardcover",
            publication_date=date(1954, 7, 29),
            publisher="George Allen & Unwin",
            language="en",
            page_count=423,
            release_status="released",
        )
        db.add(book_edition)
        await db.flush()
        db.add(
            BookContribution(
                edition_id=book_edition.id,
                person_id=person.id,
                role="author",
                sequence=1,
            )
        )
        db.add(
            BookIdentifier(
                edition_id=book_edition.id,
                identifier_type="isbn13",
                value="9780261103573",
                normalized_value="9780261103573",
                is_primary=True,
                source_provider=ExternalProvider.openlibrary,
            )
        )
        await db.commit()
        return work.id, book_edition.id


async def _seed_comic_v1() -> tuple[UUID, UUID]:
    async with AsyncSessionLocal() as db:
        writer = Person(name="Stan Lee")
        character = Character(name="Spider-Man", canonical_name="spider-man")
        arc = StoryArc(name="The Spider Strikes")
        db.add_all([writer, character, arc])
        await db.flush()
        work = ComicWork(
            title="The Amazing Spider-Man",
            sort_title="amazing spider man",
            description="Peter Parker swings into action.",
            original_language="en",
            first_publication_date=date(1963, 3, 1),
        )
        db.add(work)
        await db.flush()
        issue = ComicIssue(
            work_id=work.id,
            issue_number="1",
            display_title="The Spider Strikes",
            publication_date=date(1963, 3, 1),
            release_date=date(1963, 3, 1),
            publisher="Marvel",
            language="en",
            page_count=32,
            release_status="released",
        )
        db.add(issue)
        await db.flush()
        db.add(
            ComicContribution(
                issue_id=issue.id,
                person_id=writer.id,
                role="writer",
                sequence=1,
            )
        )
        db.add(
            ComicIdentifier(
                issue_id=issue.id,
                identifier_type="provider_item_id",
                value="4000-12345",
                normalized_value="400012345",
                is_primary=True,
                source_provider=ExternalProvider.comicvine,
            )
        )
        db.add(
            ComicCharacterAppearance(
                issue_id=issue.id,
                character_id=character.id,
                role="featured",
            )
        )
        db.add(
            ComicStoryArcMembership(
                issue_id=issue.id,
                story_arc_id=arc.id,
                ordinal=1,
            )
        )
        await db.commit()
        return work.id, issue.id


async def _seed_music_v1() -> UUID:
    async with AsyncSessionLocal() as db:
        artist = Person(name="The Beatles")
        db.add(artist)
        await db.flush()
        release = MusicRelease(
            title="Abbey Road",
            sort_title="abbey road",
            release_type="album",
            release_status="released",
            release_date=date(1969, 9, 26),
            recording_date=date(1969, 2, 22),
            publisher="Apple Records",
            studio="EMI",
            catalog_number="PCS 7088",
            barcode="049800048807",
            country_code="GB",
            language="en",
            extras="Stereo",
        )
        db.add(release)
        await db.flush()
        media = MusicMedia(
            release_id=release.id,
            media_number=1,
            media_type="vinyl",
            title="Side A",
            track_count=2,
            packaging="gatefold",
            sound_type="stereo",
        )
        db.add(media)
        await db.flush()
        db.add_all(
            [
                MusicTrack(
                    media_id=media.id,
                    release_id=release.id,
                    position="A1",
                    title="Come Together",
                    duration_ms=259000,
                ),
                MusicTrack(
                    media_id=media.id,
                    release_id=release.id,
                    position="A2",
                    title="Something",
                    duration_ms=182000,
                ),
                MusicReleaseContribution(
                    release_id=release.id,
                    person_id=artist.id,
                    role="performer",
                    sequence=1,
                ),
                MusicReleaseIdentifier(
                    release_id=release.id,
                    identifier_type="barcode",
                    value="049800048807",
                    normalized_value="049800048807",
                    is_primary=True,
                    source_provider=ExternalProvider.musicbrainz,
                ),
            ]
        )
        await db.commit()
        return release.id


@pytest.mark.asyncio
async def test_media_type_catalog_exposes_provider_defaults_and_formats(client):
    response = await client.get("/metadata/media-types")

    assert response.status_code == 200
    body = response.json()
    assert body["default_kind"] == "comic"
    rows = {item["kind"]: item for item in body["media_types"]}
    assert rows["comic"]["default_provider"] == "gcd"
    assert rows["comic"]["providers"] == ["gcd", "comicvine"]
    assert rows["comic"]["provider_search_policy"] == "core_miss_then_configured_providers"
    assert rows["comic"]["grouping_model"] == "comic_volume"
    assert rows["manga"]["providers"] == ["hardcover", "comicvine", "anilist", "mangadex"]
    assert rows["manga"]["grouping_model"] == "manga_series"
    assert rows["anime"]["providers"] == ["anilist", "tmdb"]
    assert rows["anime"]["grouping_model"] == "series_episode"
    assert rows["tv"]["providers"] == ["tmdb"]
    assert rows["tv"]["grouping_model"] == "series_episode"
    assert "bluray" not in rows
    assert rows["movie"]["providers"] == ["tmdb"]
    assert rows["movie"]["grouping_model"] == "work_release"
    assert [format["id"] for format in rows["movie"]["physical_formats"]] == [
        "dvd",
        "blu-ray",
        "4k-uhd",
        "vhs",
        "laserdisc",
        "digital",
    ]


@pytest.mark.asyncio
async def test_metadata_normalized_manifest_exposes_schema_and_type_map(client):
    response = await client.get("/metadata/normalized-manifest")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 1
    assert "audience_rating" in body["common_fields"]
    assert "genres" in body["kind_fields"]["comic"]
    assert "tracks" in body["kind_fields"]["music"]
    assert body["value_types"]["audience_rating"] == "string"
    assert "nr_discs" not in body["value_types"]
    assert body["value_types"]["genres"] == "string_list"
    assert body["value_types"]["tracks"] == "track_list"


@pytest.mark.asyncio
async def test_metadata_field_schema_exposes_registry(client):
    response = await client.get("/metadata/field-schema")

    assert response.status_code == 200
    body = response.json()
    assert body["schema_version"] == 1

    by_key = {f["key"]: f for f in body["fields"]}
    # Editable-only by default: internal bookkeeping is excluded.
    assert "cover_storage" not in by_key
    assert "associated_image_id" not in by_key
    # Common normalized field.
    assert by_key["audience_rating"]["common"] is True
    assert by_key["audience_rating"]["normalized"] is True
    assert by_key["audience_rating"]["section"] == "regional"
    # Kind-scoped typed normalized fields carry their kinds + types.
    assert by_key["genres"]["typed"] is True
    assert by_key["genres"]["value_type"] == "string_list"
    assert set(by_key["platforms"]["kinds"]) == {"game", "boardgame"}
    assert by_key["tracks"]["value_type"] == "track_list"
    # Editorial fields are exposed with their section + input hint.
    assert by_key["title"]["section"] == "item"
    assert by_key["title"]["normalized"] is False
    assert by_key["synopsis"]["input"] == "multiline"
    assert by_key["release_date"]["value_type"] == "date"
    assert by_key["page_count"]["value_type"] == "integer"

    # Sections are exposed in render order.
    assert "item" in body["sections"]
    assert "internal" not in body["sections"]

    # Per-kind composition.
    assert "audience_rating" in body["kind_fields"]["comic"]
    assert "tracks" in body["kind_fields"]["music"]
    assert "color" in body["kind_fields"]["movie"]
    assert "page_count" in body["kind_fields"]["book"]
    assert "page_count" not in body["kind_fields"]["movie"]
    assert "platforms" not in body["kind_fields"]["comic"]


@pytest.mark.asyncio
async def test_metadata_field_schema_can_include_internal_fields(client):
    response = await client.get("/metadata/field-schema?editable_only=false")

    assert response.status_code == 200
    by_key = {f["key"]: f for f in response.json()["fields"]}
    assert by_key["cover_storage"]["editable"] is False
    assert by_key["cover_storage"]["section"] == "internal"


@pytest.mark.asyncio
async def test_books_v1_work_and_edition_endpoints(client):
    work_id, edition_id = await _seed_book_v1()

    work_response = await client.get(f"/metadata/books/works/{work_id}")
    assert work_response.status_code == 200
    work_body = work_response.json()
    assert work_body["id"] == str(work_id)
    assert work_body["title"] == "The Fellowship of the Ring"
    assert work_body["series"][0]["title"] == "The Lord of the Rings"
    assert len(work_body["editions"]) == 1
    assert work_body["editions"][0]["id"] == str(edition_id)
    assert work_body["editions"][0]["identifiers"][0]["identifier_type"] == "isbn13"

    list_response = await client.get(f"/metadata/books/works/{work_id}/editions")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert len(list_body) == 1
    assert list_body[0]["id"] == str(edition_id)
    assert list_body[0]["contributors"][0]["name"] == "J.R.R. Tolkien"

    edition_response = await client.get(f"/metadata/books/editions/{edition_id}")
    assert edition_response.status_code == 200
    edition_body = edition_response.json()
    assert edition_body["id"] == str(edition_id)
    assert edition_body["publication_date"] == "1954-07-29"
    assert edition_body["identifiers"][0]["value"] == "9780261103573"

    route_response = await client.get(f"/books/{work_id}")
    assert route_response.status_code == 200


@pytest.mark.asyncio
async def test_book_work_search_document_does_not_lazy_load_series():
    work_id, _ = await _seed_book_v1()
    async with AsyncSessionLocal() as db:
        work = await db.scalar(
            select(BookWork)
            .options(selectinload(BookWork.series_memberships))
            .where(BookWork.id == work_id)
        )

    assert work is not None
    document = book_work_search_document(work)
    assert document["series_title"] is None


@pytest.mark.asyncio
async def test_comics_v1_work_and_issue_endpoints(client):
    work_id, issue_id = await _seed_comic_v1()

    work_response = await client.get(f"/metadata/comics/works/{work_id}")
    assert work_response.status_code == 200
    work_body = work_response.json()
    assert work_body["id"] == str(work_id)
    assert work_body["title"] == "The Amazing Spider-Man"
    assert len(work_body["issues"]) == 1
    assert work_body["issues"][0]["id"] == str(issue_id)
    assert work_body["issues"][0]["identifiers"][0]["identifier_type"] == "provider_item_id"

    list_response = await client.get(f"/metadata/comics/works/{work_id}/issues")
    assert list_response.status_code == 200
    list_body = list_response.json()
    assert len(list_body) == 1
    assert list_body[0]["id"] == str(issue_id)
    assert list_body[0]["contributors"][0]["name"] == "Stan Lee"
    assert list_body[0]["characters"][0]["name"] == "Spider-Man"

    issue_response = await client.get(f"/metadata/comics/issues/{issue_id}")
    assert issue_response.status_code == 200
    issue_body = issue_response.json()
    assert issue_body["id"] == str(issue_id)
    assert issue_body["issue_number"] == "1"
    assert issue_body["story_arcs"][0]["name"] == "The Spider Strikes"

    route_response = await client.get(f"/comics/{work_id}")
    assert route_response.status_code == 200
    assert route_response.json()["id"] == str(work_id)


@pytest.mark.asyncio
async def test_music_release_v1_response_includes_contributors_identifiers_and_tracks():
    release_id = await _seed_music_v1()

    async with AsyncSessionLocal() as db:
        release = await MetadataService(db).get_music_release(release_id)

    assert release.id == release_id
    assert release.title == "Abbey Road"
    assert release.track_count == 2
    assert release.contributions[0].name == "The Beatles"
    assert release.contributions[0].role == "performer"
    assert release.identifiers[0].identifier_type == "barcode"
    assert release.identifiers[0].source_provider == ExternalProvider.musicbrainz
    assert release.media[0].tracks[0].title == "Come Together"
    assert release.media[0].tracks[1].position == "A2"


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
    work_id, issue_id = await _seed_comic_v1()

    response = await client.get("/search", params={"q": "The Amazing Spider-Man", "kind": "comic"})
    assert response.status_code == 200
    assert response.json()[0]["title"] == "The Amazing Spider-Man"
    assert response.json()[0]["publisher"] == "Marvel"
    assert response.json()[0]["release_date"] == "1963-03-01"
    assert response.json()[0]["release_year"] == 1963
    assert response.json()[0]["barcode"] == "4000-12345"
    assert response.json()[0]["variant"] == "The Spider Strikes"

    detail = await client.get(f"/metadata/comics/works/{work_id}")
    assert detail.status_code == 200
    assert detail.json()["title"] == "The Amazing Spider-Man"

    issue_detail = await client.get(f"/metadata/comics/issues/{issue_id}")
    assert issue_detail.status_code == 200
    assert issue_detail.json()["display_title"] == "The Spider Strikes"

    generic_detail = await client.get(f"/metadata/comics/works/{work_id}")
    assert generic_detail.status_code == 200
    assert generic_detail.json()["title"] == "The Amazing Spider-Man"

    wrong_media_detail = await client.get(f"/metadata/games/{work_id}")
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
async def test_search_prefers_normalized_relations_over_edition_json(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    work_id, issue_id = await _seed_comic_v1()

    async with AsyncSessionLocal() as db:
        issue = await db.get(ComicIssue, issue_id)
        work = await db.get(ComicWork, work_id)
        assert issue is not None
        assert work is not None
        issue.metadata_json = {
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
                ComicContribution(
                    issue_id=issue.id,
                    person_id=creator.id,
                    role="writer",
                    sequence=1,
                ),
                ComicCharacterAppearance(issue_id=issue.id, character_id=character.id, role="main"),
                ComicStoryArcMembership(issue_id=issue.id, story_arc_id=story_arc.id, ordinal=1),
            ]
        )
        await db.commit()

    response = await client.get("/search", params={"q": "spider", "kind": "comic"})

    assert response.status_code == 200
    assert response.json()

    async with AsyncSessionLocal() as db:
        work = await db.scalar(
            select(ComicWork)
            .options(
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.contributions)
                .selectinload(ComicContribution.person),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.character_appearances)
                .selectinload(ComicCharacterAppearance.character),
                selectinload(ComicWork.issues)
                .selectinload(ComicIssue.story_arc_memberships)
                .selectinload(ComicStoryArcMembership.story_arc),
                selectinload(ComicWork.issues).selectinload(ComicIssue.identifiers),
            )
            .where(ComicWork.id == work_id)
        )

    assert work is not None
    document = comic_work_search_document(work)
    assert document["creators"] == ["Stan Lee"]
    assert "Spider-Man [Peter Parker]" in document["characters"]
    assert "If This Be My Destiny" in document["story_arcs"]


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


def test_item_response_from_model_exposes_normalized_metadata_fields():
    kind_metadata = SimpleNamespace(platforms=["PC", "Xbox One", "PlayStation 4"])
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
        kind_metadata=kind_metadata,
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
            ExternalProviderIdResponse(
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


def test_item_response_from_model_uses_item_level_metadata_without_editions():
    kind_metadata = SimpleNamespace(
        audience_rating="R",
        genres=["Sci-Fi", "Horror"],
        color="Color",
    )
    item = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.movie,
        title="Alien",
        item_number=None,
        sort_key="alien-1979",
        synopsis=None,
        release_type=None,
        season_number=None,
        episode_number=None,
        runtime_minutes=117,
        page_count=None,
        metadata_json={
            "provider": "tmdb",
        },
        original_title="Alien",
        localized_title="Alien: Le huitieme passager",
        search_aliases=["Alien (1979)", "Alien Director's Cut"],
        crossover="Alien Universe",
        plot_summary="A crew faces a hostile life form.",
        plot_description="A deep-space cargo crew discovers an organism that hunts them one by one.",
        trailer_urls=[{"url": "https://youtube.com/watch?v=jQ5lPt9edzQ"}],
        external_links=[{"url": "https://www.imdb.com/title/tt0078748/"}],
        kind_metadata=kind_metadata,
        volume=None,
        editions=[],
        primary_bundle_releases=[],
        organization_links=[],
    )

    response = item_response_from_model(item)

    assert response.localized_title == "Alien: Le huitieme passager"
    assert response.original_title == "Alien"
    assert response.search_aliases == ["Alien (1979)", "Alien Director's Cut"]
    assert response.crossover == "Alien Universe"
    assert response.plot_summary == "A crew faces a hostile life form."
    assert response.plot_description == "A deep-space cargo crew discovers an organism that hunts them one by one."
    assert response.trailer_urls == [{"url": "https://youtube.com/watch?v=jQ5lPt9edzQ"}]
    assert response.external_links == [{"url": "https://www.imdb.com/title/tt0078748/"}]
    assert response.audience_rating == "R"
    assert response.genres == ["Sci-Fi", "Horror"]
    assert response.platforms == []
    assert response.track_count is None
    assert response.tracks == []
    assert response.color == "Color"
    assert response.nr_discs is None
    assert response.screen_ratio is None
    assert response.audio_tracks is None
    assert response.subtitles is None
    assert response.layers is None


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
async def test_get_item_seasons_prefers_catalog_mapped_seasons(client):
    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.tv, title="Example Show")
        show_volume = Volume(series=series, name="Example Show", volume_number=0)
        season_volume = Volume(series=series, name="Season 1", volume_number=1)
        show_item = Item(kind=ItemKind.tv, title="Example Show", volume=show_volume)
        episode_item = Item(
            kind=ItemKind.tv,
            title="Pilot",
            volume=season_volume,
            item_number="1",
            season_number=1,
            episode_number=1,
            runtime_minutes=45,
            metadata_json={"air_date": "2024-01-01"},
        )
        db.add_all([series, show_volume, season_volume, show_item, episode_item])
        await db.flush()
        db.add(
            ExternalProviderId(
                entity_type="item",
                entity_id=show_item.id,
                provider=ExternalProvider.tmdb,
                provider_item_id="tv:100",
            )
        )
        db.add(
            ExternalProviderId(
                entity_type="volume",
                entity_id=season_volume.id,
                provider=ExternalProvider.tmdb,
                provider_item_id="tv:100:season:1",
            )
        )
        db.add(
            ExternalProviderId(
                entity_type="item",
                entity_id=episode_item.id,
                provider=ExternalProvider.tmdb,
                provider_item_id="tv:100:season:1:episode:1",
            )
        )
        await db.commit()
        show_item_id = str(show_item.id)

    token = await register_and_login(client)
    response = await client.get(
        f"/metadata/items/{show_item_id}/seasons",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["season_number"] == 1
    assert body[0]["provider_item_id"] == "tv:100:season:1"
    assert body[0]["episodes"][0]["title"] == "Pilot"
    assert body[0]["episodes"][0]["provider_item_id"] == "tv:100:season:1:episode:1"


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
