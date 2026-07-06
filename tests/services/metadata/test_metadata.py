from datetime import date
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db.session import AsyncSessionLocal
from app.models import (
    BoardGameEdition,
    BoardGameWork,
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
    EntityPerson,
    EntityTag,
    GameRelease,
    GameWork,
    MovieRelease,
    MovieWork,
    MusicMedia,
    MusicRelease,
    MusicReleaseContribution,
    MusicReleaseIdentifier,
    MusicTrack,
    Person,
    StoryArc,
    StoryArcItem,
    Tag,
)
from app.models.base import ExternalProvider, ItemKind
from app.providers.base import ProviderSearchResult
from app.repositories.metadata import MetadataRepository
from app.schemas.metadata_shared import SearchResult
from app.search.documents import (
    boardgame_search_document,
    book_work_search_document,
    comic_work_search_document,
    game_work_search_document,
)
from app.services.facade import MetadataFacade as MetadataService
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


async def _seed_game_v1() -> tuple[UUID, UUID]:
    async with AsyncSessionLocal() as db:
        work = GameWork(
            title="The Legend of Zelda: Breath of the Wild",
            sort_title="legend of zelda breath of the wild",
            description="An open-world adventure.",
            release_date=date(2017, 3, 3),
            original_language="en",
            age_rating="E10+",
            metadata_json={
                "platforms": ["Nintendo Switch", "nintendo switch", "Wii U"],
                "identifiers": ["IGDB:1020", "Nintendo:BOTW", " IGDB:1020 "],
                "company_roles": ["developer", "publisher", "developer"],
                "age_ratings": ["E10+", "E10+"],
            },
        )
        db.add(work)
        await db.flush()
        release = GameRelease(
            work_id=work.id,
            release_title="Nintendo Switch Release",
            platform="Nintendo Switch",
            release_date=date(2017, 3, 3),
            region_code="US",
            format="physical",
            publisher="Nintendo",
            catalog_number="HAC P AABPA",
            barcode="045496590420",
            release_status="released",
            language="en",
        )
        db.add(release)
        await db.commit()
        return work.id, release.id


async def _seed_boardgame_v1() -> tuple[UUID, UUID]:
    async with AsyncSessionLocal() as db:
        work = BoardGameWork(
            title="Catan",
            sort_title="catan",
            description="Settle the island of Catan.",
            release_date=date(1995, 1, 1),
            original_language="de",
            age_rating="8+",
            metadata_json={
                "platforms": ["Base Game", "base game"],
                "identifiers": ["BGG:13", "Kosmos:6995", "BGG:13"],
                "contributors": ["Klaus Teuber", " klaus teuber "],
                "mechanics": ["dice rolling", "resource management"],
                "categories": ["economic", "negotiation", "economic"],
                "families": ["catan", "catan"],
                "expansions": ["Seafarers", "Seafarers"],
                "rankings": ["BGG Rank #1", "BGG Rank #1"],
            },
        )
        db.add(work)
        await db.flush()
        edition = BoardGameEdition(
            work_id=work.id,
            edition_title="First Edition",
            format="box",
            publisher="Kosmos",
            catalog_number="6995",
            barcode="4002051699955",
            release_status="released",
            release_date=date(1995, 1, 1),
            language="de",
            country="DE",
        )
        db.add(edition)
        await db.commit()
        return work.id, edition.id


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
    assert body["value_types"]["audience_rating"] == "string"
    assert "nr_discs" not in body["value_types"]
    assert body["value_types"]["genres"] == "string_list"


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
    assert by_key["audience_rating"]["scope"] == "common"
    assert by_key["audience_rating"]["write_target"] == "kind_specific_table"
    assert by_key["audience_rating"]["source_entity_type"] == "kind"
    assert by_key["audience_rating"]["source_table"] == "kind_specific_table"
    assert by_key["audience_rating"]["is_legacy_projection"] is False
    assert by_key["audience_rating"]["section"] == "regional"
    # Kind-scoped typed normalized fields carry their kinds + types.
    assert by_key["genres"]["typed"] is True
    assert by_key["genres"]["value_type"] == "string_list"
    assert set(by_key["platforms"]["kinds"]) == {"game", "boardgame"}
    assert "identifiers" in by_key
    assert set(by_key["identifiers"]["kinds"]) == {"game", "boardgame"}
    assert set(by_key["company_roles"]["kinds"]) == {"game"}
    assert set(by_key["contributors"]["kinds"]) == {"boardgame"}
    assert set(by_key["mechanics"]["kinds"]) == {"boardgame"}
    assert by_key["genres"]["scope"] == "kind"
    # Editorial fields are exposed with their section + input hint.
    assert by_key["title"]["section"] == "item"
    assert by_key["title"]["normalized"] is False
    assert by_key["title"]["scope"] == "kind"
    assert by_key["title"]["write_target"] == "canonical_kind_table"
    assert by_key["title"]["source_entity_type"] == "item"
    assert by_key["title"]["source_table"] == "items"
    assert by_key["title"]["is_legacy_projection"] is True
    assert by_key["synopsis"]["input"] == "multiline"
    assert by_key["release_date"]["value_type"] == "date"
    assert by_key["page_count"]["value_type"] == "integer"

    # Sections are exposed in render order.
    assert "item" in body["sections"]
    assert "internal" not in body["sections"]

    # Per-kind composition.
    assert "audience_rating" in body["kind_fields"]["comic"]
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


@pytest.mark.asyncio
async def test_books_v1_routes_are_exposed_in_openapi(client):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    paths = body["paths"]
    assert "/metadata/books/works/{work_id}" in paths
    assert "/metadata/books/works/{work_id}/editions" in paths
    assert "/metadata/books/editions/{edition_id}" in paths
    assert "BookWorkV1Response" in body["components"]["schemas"]
    assert "BookEditionV1Response" in body["components"]["schemas"]

@pytest.mark.asyncio
async def test_game_and_boardgame_v1_routes_are_exposed_in_openapi(client):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    body = response.json()
    paths = body["paths"]
    assert "/metadata/games/works/{work_id}" in paths
    assert "/metadata/games/works/{work_id}/releases" in paths
    assert "/metadata/games/releases/{release_id}" in paths
    assert "/metadata/boardgames/works/{work_id}" in paths
    assert "/metadata/boardgames/works/{work_id}/editions" in paths
    assert "/metadata/boardgames/editions/{edition_id}" in paths

    game_schema = body["components"]["schemas"]["GameWorkV1Response"]
    boardgame_schema = body["components"]["schemas"]["BoardGameWorkV1Response"]
    admin_correction_schema = body["components"]["schemas"]["AdminMetadataCorrectionRequest"]
    assert "identifiers" in game_schema["properties"]
    assert "company_roles" in game_schema["properties"]
    assert "contributors" in boardgame_schema["properties"]
    assert "mechanics" in boardgame_schema["properties"]
    assert "identifiers" in admin_correction_schema["properties"]
    assert "contributors" in admin_correction_schema["properties"]
    assert "rankings" in admin_correction_schema["properties"]


@pytest.mark.asyncio
async def test_legacy_metadata_routes_are_not_exposed_in_openapi(client):
    response = await client.get("/openapi.json")

    assert response.status_code == 200
    paths = response.json()["paths"]
    assert "/metadata/{kind}/{id}" not in paths


@pytest.mark.asyncio
async def test_game_boardgame_and_music_typed_routes(client):
    game_work_id, game_release_id = await _seed_game_v1()
    boardgame_work_id, boardgame_edition_id = await _seed_boardgame_v1()
    music_release_id = await _seed_music_v1()

    game_work = await client.get(f"/metadata/games/works/{game_work_id}")
    assert game_work.status_code == 200
    game_work_body = game_work.json()
    assert game_work_body["id"] == str(game_work_id)
    assert game_work_body["platforms"] == ["Nintendo Switch", "Wii U"]
    assert game_work_body["identifiers"] == ["IGDB:1020", "Nintendo:BOTW"]
    assert game_work_body["company_roles"] == ["developer", "publisher"]

    game_releases = await client.get(f"/metadata/games/works/{game_work_id}/releases")
    assert game_releases.status_code == 200
    assert game_releases.json()[0]["id"] == str(game_release_id)

    game_release = await client.get(f"/metadata/games/releases/{game_release_id}")
    assert game_release.status_code == 200
    assert game_release.json()["platform"] == "Nintendo Switch"

    boardgame_work = await client.get(f"/metadata/boardgames/works/{boardgame_work_id}")
    assert boardgame_work.status_code == 200
    boardgame_work_body = boardgame_work.json()
    assert boardgame_work_body["id"] == str(boardgame_work_id)
    assert boardgame_work_body["platforms"] == ["Base Game"]
    assert boardgame_work_body["contributors"] == ["Klaus Teuber"]
    assert boardgame_work_body["mechanics"] == ["dice rolling", "resource management"]
    assert boardgame_work_body["categories"] == ["economic", "negotiation"]
    assert boardgame_work_body["families"] == ["catan"]
    assert boardgame_work_body["expansions"] == ["Seafarers"]
    assert boardgame_work_body["rankings"] == ["BGG Rank #1"]

    boardgame_editions = await client.get(
        f"/metadata/boardgames/works/{boardgame_work_id}/editions"
    )
    assert boardgame_editions.status_code == 200
    assert boardgame_editions.json()[0]["id"] == str(boardgame_edition_id)

    boardgame_edition = await client.get(f"/metadata/boardgames/editions/{boardgame_edition_id}")
    assert boardgame_edition.status_code == 200
    assert boardgame_edition.json()["publisher"] == "Kosmos"

    music_release = await client.get(f"/metadata/music/releases/{music_release_id}")
    assert music_release.status_code == 200
    assert music_release.json()["id"] == str(music_release_id)

    music_media = await client.get(f"/metadata/music/releases/{music_release_id}/media")
    assert music_media.status_code == 200
    assert music_media.json()[0]["tracks"][0]["title"] == "Come Together"

    async with AsyncSessionLocal() as db:
        media_row = await db.scalar(select(MusicMedia).where(MusicMedia.release_id == music_release_id))
        assert media_row is not None
        track_row = await db.scalar(select(MusicTrack).where(MusicTrack.media_id == media_row.id))
        assert track_row is not None

    music_media_detail = await client.get(f"/metadata/music/media/{media_row.id}")
    assert music_media_detail.status_code == 200
    assert music_media_detail.json()["id"] == str(media_row.id)

    music_media_tracks = await client.get(f"/metadata/music/media/{media_row.id}/tracks")
    assert music_media_tracks.status_code == 200
    assert music_media_tracks.json()[0]["position"] == "A1"

    music_track = await client.get(f"/metadata/music/tracks/{track_row.id}")
    assert music_track.status_code == 200
    assert music_track.json()["title"] == "Come Together"


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
async def test_game_and_boardgame_search_documents_expose_kind_metadata_lists():
    game_work_id, _ = await _seed_game_v1()
    boardgame_work_id, _ = await _seed_boardgame_v1()

    async with AsyncSessionLocal() as db:
        game_work = await db.scalar(
            select(GameWork)
            .options(selectinload(GameWork.releases))
            .where(GameWork.id == game_work_id)
        )
        boardgame_work = await db.scalar(
            select(BoardGameWork)
            .options(selectinload(BoardGameWork.editions))
            .where(BoardGameWork.id == boardgame_work_id)
        )

    assert game_work is not None
    assert boardgame_work is not None

    game_document = game_work_search_document(game_work)
    assert game_document["platforms"] == ["Nintendo Switch", "Wii U"]
    assert game_document["identifiers"] == ["IGDB:1020", "Nintendo:BOTW"]
    assert game_document["company_roles"] == ["developer", "publisher"]

    boardgame_document = boardgame_search_document(boardgame_work)
    assert boardgame_document["platforms"] == ["Base Game"]
    assert boardgame_document["identifiers"] == ["BGG:13", "Kosmos:6995"]
    assert boardgame_document["contributors"] == ["Klaus Teuber"]
    assert boardgame_document["mechanics"] == ["dice rolling", "resource management"]
    assert boardgame_document["categories"] == ["economic", "negotiation"]
    assert boardgame_document["families"] == ["catan"]
    assert boardgame_document["expansions"] == ["Seafarers"]
    assert boardgame_document["rankings"] == ["BGG Rank #1"]


@pytest.mark.asyncio
async def test_metadata_repository_search_items_uses_native_book_work():
    work_id, _ = await _seed_book_v1()

    async with AsyncSessionLocal() as db:
        items = await MetadataRepository(db).search_items(query="Fellowship", kind=ItemKind.book, limit=5)

    assert [item.id for item in items] == [work_id]
    assert isinstance(items[0], BookWork)


@pytest.mark.asyncio
async def test_metadata_repository_search_items_uses_native_game_and_boardgame_work():
    game_work_id, _ = await _seed_game_v1()
    boardgame_work_id, _ = await _seed_boardgame_v1()

    async with AsyncSessionLocal() as db:
        game_items = await MetadataRepository(db).search_items(query="Zelda", kind=ItemKind.game, limit=5)
        boardgame_items = await MetadataRepository(db).search_items(query="Catan", kind=ItemKind.boardgame, limit=5)

    assert [item.id for item in game_items] == [game_work_id]
    assert isinstance(game_items[0], GameWork)
    assert [item.id for item in boardgame_items] == [boardgame_work_id]
    assert isinstance(boardgame_items[0], BoardGameWork)


@pytest.mark.asyncio
async def test_metadata_repository_find_item_by_barcode_uses_native_book_work():
    work_id, _ = await _seed_book_v1()

    async with AsyncSessionLocal() as db:
        item = await MetadataRepository(db).find_item_by_barcode("9780261103573", ItemKind.book)

    assert item is not None
    assert item.id == work_id
    assert isinstance(item, BookWork)


@pytest.mark.asyncio
async def test_metadata_repository_find_item_by_barcode_uses_native_game_and_boardgame_work():
    game_work_id, game_release_id = await _seed_game_v1()
    boardgame_work_id, boardgame_edition_id = await _seed_boardgame_v1()

    async with AsyncSessionLocal() as db:
        game_item = await MetadataRepository(db).find_item_by_barcode("045496590420", ItemKind.game)
        boardgame_item = await MetadataRepository(db).find_item_by_barcode("4002051699955", ItemKind.boardgame)

    assert game_item is not None
    assert game_item.id == game_work_id
    assert isinstance(game_item, GameWork)
    assert boardgame_item is not None
    assert boardgame_item.id == boardgame_work_id
    assert isinstance(boardgame_item, BoardGameWork)


@pytest.mark.asyncio
async def test_metadata_service_search_uses_native_anime_branch_without_legacy_fallback(monkeypatch):
    called = {}

    async def fake_search(self, query, kind=None, **kwargs):
        return None

    async def fake_anime_search(self, **kwargs):
        called["anime"] = kwargs
        return [SearchResult(id=uuid4(), kind=ItemKind.anime, title="Anime Result")]

    monkeypatch.setattr("app.search.client.SearchClient.search", fake_search)
    monkeypatch.setattr("app.services.facade.MetadataFacade._search_anime_series", fake_anime_search)

    async with AsyncSessionLocal() as db:
        service = MetadataService(db)
        results = await service.search(query="anime", kind=ItemKind.anime)

    assert results[0].title == "Anime Result"
    assert called["anime"]["query"] == "anime"


@pytest.mark.asyncio
async def test_metadata_service_lookup_barcode_uses_native_music_branch_without_legacy_fallback(monkeypatch):
    release_id = uuid4()
    called = {}

    async def fake_music_by_barcode(self, barcode):
        called["barcode"] = barcode
        return SimpleNamespace(id=release_id, title="Music Result", barcode=barcode)

    def fake_music_result(self, release):
        return SearchResult(id=release.id, kind=ItemKind.music, title=release.title, barcode=release.barcode)

    monkeypatch.setattr("app.services.facade.MetadataFacade._music_release_by_barcode", fake_music_by_barcode)
    monkeypatch.setattr("app.services.facade.MetadataFacade._music_search_result", fake_music_result)

    async with AsyncSessionLocal() as db:
        service = MetadataService(db)
        result = await service.lookup_barcode("1234567890123", ItemKind.music)

    assert result.title == "Music Result"
    assert called["barcode"] == "1234567890123"


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
    item_id, _ = await _seed_comic_v1()

    async with AsyncSessionLocal() as db:
        work = await db.get(ComicWork, item_id)
        assert work is not None
        action = Tag(kind="series_tag:comic", name="Street-level")
        legacy = Tag(kind="series_tag:comic", name="Legacy Hero")
        db.add_all([action, legacy])
        await db.flush()
        db.add_all(
            [
                EntityTag(entity_type="comic_work", entity_id=work.id, tag_id=action.id),
                EntityTag(entity_type="comic_work", entity_id=work.id, tag_id=legacy.id),
            ]
        )
        await db.commit()

    detail_response = await client.get(
        f"/comics/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert detail_response.status_code == 200
    assert "tags" not in detail_response.json()




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
        issue = await db.get(ComicIssue, UUID(edition_id))
        assert issue is not None
        issue.imprint = "Marvel Knights"
        issue.display_title = "Collector Edition"
        issue.region = "US"
        issue.release_status = "released"
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
    assert response.json()[0]["variant"] == "Collector Edition"
    assert response.json()[0]["imprint"] == "Marvel Knights"
    assert response.json()[0]["catalog_number"] == "75960604716100111"


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
async def test_lookup_barcode_uses_comic_issue_cover(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    item_id, issue_id, _ = await seed_comic()
    async with AsyncSessionLocal() as db:
        issue = await db.get(ComicIssue, UUID(issue_id))
        assert issue is not None
        issue.cover_image_url = "https://cdn.example/foil.jpg"
        await db.commit()

    response = await client.get("/barcode/75960604716100111", params={"kind": "comic"})

    assert response.status_code == 200
    assert response.json()["id"] == item_id
    assert response.json()["variant"] == "The Spider Strikes"
    assert response.json()["barcode"] == "75960604716100111"
    assert response.json()["cover_image_url"] == "https://cdn.example/foil.jpg"


@pytest.mark.asyncio
async def test_lookup_video_barcode_matches_physical_editions(client, monkeypatch):
    async def unavailable_search(self, query, kind=None, **kwargs):
        return None

    monkeypatch.setattr("app.search.client.SearchClient.search", unavailable_search)
    async with AsyncSessionLocal() as db:
        work = MovieWork(
            title="Blade Runner",
            sort_title="blade runner",
            original_release_date=date(1982, 6, 25),
        )
        db.add(work)
        await db.flush()
        release = MovieRelease(
            work_id=work.id,
            format="4K Blu-ray",
            region_code="US",
            release_date=date(1982, 6, 25),
            release_type="physical",
            publisher="Warner Bros.",
            distributor="Warner Bros.",
            sku="SKU-4K-001",
            barcode="883-929 087.129",
            metadata_json={"normalized": {"physical_format": "4k-uhd"}},
        )
        db.add(release)
        await db.commit()
        item_id = str(work.id)

    response = await client.get("/barcode/883929087129", params={"kind": "movie"})

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == item_id
    assert body["edition_title"] == "4K Blu-ray"
    assert body["publisher"] == "Warner Bros."
    assert body["release_date"] == "1982-06-25"
    assert body["barcode"] == "883-929 087.129"
    assert body["variant"] == "4K Blu-ray"
    assert body["physical_format"] == "4k-uhd"
    assert body["physical_format_label"] == "4K Blu-ray"

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
async def test_search_document_and_search_result_prefer_item_organization_links():
    loaded = SimpleNamespace(
        id=uuid4(),
        kind=ItemKind.comic,
        title="Invincible",
        item_number="1",
        editions=[],
        organization_links=[
            SimpleNamespace(role="publisher", organization=SimpleNamespace(name="Image Comics")),
            SimpleNamespace(role="imprint", organization=SimpleNamespace(name="Skybound")),
        ],
    )

    service = MetadataService.__new__(MetadataService)
    result = MetadataService._search_result(service, loaded, None, None)

    assert result.title == "Invincible"
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
                StoryArcItem(
                    story_arc_id=story_arc.id,
                    entity_type="comic_work",
                    entity_id=item_uuid,
                    ordinal=1,
                ),
                CharacterAppearance(
                    character_id=character.id,
                    entity_type="comic_work",
                    entity_id=item_uuid,
                    role="main",
                ),
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
    assert arc_items_body[0]["entity_type"] == "comic_work"
    assert arc_items_body[0]["entity_id"] == item_id
    assert arc_items_body[0]["ordinal"] == 1
    assert arc_items_body[0]["series_title"] is None

    arc_facets_response = await client.post(
        "/story-arcs/facets",
        json={"entity_ids": [item_id]},
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
            "entity_ids": [item_id],
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
    assert appearances_body[0]["entity_type"] == "comic_work"
    assert appearances_body[0]["entity_id"] == item_id
    assert appearances_body[0]["role"] == "main"

    character_facets_response = await client.post(
        "/characters/facets",
        json={"entity_ids": [item_id]},
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
            "entity_ids": [item_id],
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
            "first_appearance_entity_type": None,
            "first_appearance_entity_id": None,
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
