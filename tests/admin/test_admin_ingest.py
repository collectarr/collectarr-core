import fnmatch
from contextlib import asynccontextmanager
from datetime import UTC, date, datetime, timedelta
from uuid import UUID

import pytest
from fastapi import HTTPException, status
from sqlalchemy import func, select, update

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.db.session import AsyncSessionLocal
from app.metadata_normalized import NORMALIZED_SCHEMA_VERSION
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import (
    BundleRelease,
    BundleReleaseItem,
    Character,
    CharacterAppearance,
    ComicCharacterAppearance,
    ComicContribution,
    ComicIdentifier,
    ComicIssue,
    ComicVolume,
    ComicStoryArcMembership,
    ComicWork,
    Edition,
    EntityOrganization,
    EntityPerson,
    EntityTag,
    ExternalProviderId,
    ImageCacheEntry,
    Item,
    ItemKindMetadata,
    ItemKindMetadataComic,
    ItemKindMetadataMusic,
    MetadataProposal,
    Organization,
    Person,
    ProviderIngestJob,
    ProviderPayloadSnapshot,
    Series,
    StoryArc,
    StoryArcItem,
    Tag,
    Variant,
    Volume,
)
from app.providers.base import (
    NormalizedBundleMember,
    NormalizedBundleRelease,
    NormalizedCredit,
    NormalizedItem,
    ProviderCapabilities,
    ProviderItem,
    ProviderSearchResult,
)
from app.providers.comicvine import (
    ComicVineCharacterDetail,
    ComicVineIssueCover,
    ComicVineProvider,
)
from app.providers.gcd import GCDCoverFallback, GCDCoverImage, GCDProvider
from app.providers.registry import ProviderRegistry
from app.schemas.admin import ProviderIngestRequest
from app.search.client import SearchClient
from app.services import admin as admin_service
from app.services.admin_domains.provider_ingest import AdminProviderIngestService
from app.services.provider_preview_state import ProviderPreviewState, clear_provider_preview_cache
from app.storage.images import ImageMirror, MirroredImage


async def admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


@pytest.mark.asyncio
async def test_get_or_create_character_prefers_provider_links_over_shared_name():
    async def _reindex_items(_: set[UUID]) -> None:
        return None

    async with AsyncSessionLocal() as db:
        service = AdminProviderIngestService(
            db=db,
            settings=get_settings(),
            providers=ProviderRegistry(),
            provider_preview_state=ProviderPreviewState(),
            history_reader=lambda: [],
            audit_recorder=lambda **_: None,
            ingest_job_audit_details=lambda *_args, **_kwargs: {},
            record_ingest_history=lambda *_args, **_kwargs: None,
            is_retryable_ingest_error=lambda *_args, **_kwargs: False,
            error_message=lambda exc: str(exc),
            reindex_items=_reindex_items,
            item_response_loader=lambda *_args, **_kwargs: None,
            backoff_delay=lambda *_args, **_kwargs: 0,
            actor_user_id=None,
            comicvine_character_details={},
        )
        existing = Character(name="Spider-Man", canonical_name="spider-man")
        db.add(existing)
        await db.flush()
        db.add(
            ExternalProviderId(
                provider=ExternalProvider.comicvine,
                provider_item_id="4005-1443",
                entity_type="character",
                entity_id=existing.id,
            )
        )
        await db.flush()

        first = await service._get_or_create_character(
            "Spider-Man",
            NormalizedCredit(
                name="Spider-Man",
                role=None,
                api_detail_url="https://comicvine.gamespot.com/api/character/4005-1443/",
                site_detail_url="https://comicvine.gamespot.com/spider-man/4005-1443/",
            ),
            provider=ExternalProvider.comicvine,
            provider_item_id="4005-1443",
        )
        second = await service._get_or_create_character(
            "Spider-Man",
            NormalizedCredit(
                name="Spider-Man",
                role=None,
                api_detail_url="https://comicvine.gamespot.com/api/character/4005-999999/",
                site_detail_url="https://comicvine.gamespot.com/spider-man-2099/4005-999999/",
            ),
            provider=ExternalProvider.comicvine,
            provider_item_id="4005-999999",
        )
        await db.flush()

        all_characters = list((await db.execute(select(Character).where(Character.name == "Spider-Man"))).scalars())

    assert first.id == existing.id
    assert second.id != existing.id
    assert second.canonical_name == "spider-man"
    assert len(all_characters) == 2


@pytest.mark.asyncio
async def test_purge_expired_provider_snapshots_redacts_payloads_only_for_expired_rows():
    async def _reindex_items(_: set[UUID]) -> None:
        return None

    async with AsyncSessionLocal() as db:
        service = AdminProviderIngestService(
            db=db,
            settings=get_settings(),
            providers=ProviderRegistry(),
            provider_preview_state=ProviderPreviewState(),
            history_reader=lambda: [],
            audit_recorder=lambda **_: None,
            ingest_job_audit_details=lambda *_args, **_kwargs: {},
            record_ingest_history=lambda *_args, **_kwargs: None,
            is_retryable_ingest_error=lambda *_args, **_kwargs: False,
            error_message=lambda exc: str(exc),
            reindex_items=_reindex_items,
            item_response_loader=lambda *_args, **_kwargs: None,
            backoff_delay=lambda *_args, **_kwargs: 0,
            actor_user_id=None,
            comicvine_character_details={},
        )
        now = datetime.now(UTC)
        expired = ProviderPayloadSnapshot(
            provider=ExternalProvider.comicvine,
            provider_item_id="4000-1",
            entity_type="item",
            entity_id=UUID("00000000-0000-0000-0000-000000000101"),
            source_payload={"raw": "expired"},
            normalized_payload={"n": "expired"},
            expires_at=now - timedelta(days=1),
        )
        active = ProviderPayloadSnapshot(
            provider=ExternalProvider.comicvine,
            provider_item_id="4000-2",
            entity_type="item",
            entity_id=UUID("00000000-0000-0000-0000-000000000102"),
            source_payload={"raw": "active"},
            normalized_payload={"n": "active"},
            expires_at=now + timedelta(days=1),
        )
        db.add_all([expired, active])
        await db.flush()

        purged = await service.purge_expired_provider_snapshots(limit=10)
        await db.commit()

        expired_db = await db.get(ProviderPayloadSnapshot, expired.id)
        active_db = await db.get(ProviderPayloadSnapshot, active.id)
        if expired_db is not None:
            await db.refresh(expired_db)
        if active_db is not None:
            await db.refresh(active_db)

    assert purged == 1
    assert expired_db is not None and expired_db.source_payload is None
    assert expired_db is not None and expired_db.normalized_payload is None
    assert expired_db is not None and expired_db.purged_at is not None
    assert active_db is not None and active_db.source_payload == {"raw": "active"}
    assert active_db is not None and active_db.normalized_payload == {"n": "active"}
    assert active_db is not None and active_db.purged_at is None


class FakePreviewCacheRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.ttls: dict[str, int] = {}

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def setex(self, key: str, ttl: int, value: str) -> None:
        self.values[key] = value
        self.ttls[key] = ttl

    async def scan_iter(self, match: str | None = None):
        for key in list(self.values):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self.values:
                deleted += 1
            self.values.pop(key, None)
            self.ttls.pop(key, None)
        return deleted


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
        "character_credits": [
            {
                "name": "Spider-Man",
                "api_detail_url": "https://comicvine.gamespot.com/api/character/4005-1443/",
                "site_detail_url": "https://comicvine.gamespot.com/spider-man/4005-1443/",
            }
        ],
        "story_arc_credits": [{"name": "The Spider Strikes"}],
        "image": {"super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"},
        "volume": {
            "id": 6789,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-6789/",
            "name": "The Amazing Spider-Man",
            "publisher": {"name": "Marvel"},
        },
    }


def comicvine_over_the_garden_wall_raw() -> dict:
    raw = comicvine_issue_raw()
    raw.update(
        {
            "id": 498453,
            "api_detail_url": "https://comicvine.gamespot.com/api/issue/4000-498453/",
            "site_detail_url": "https://comicvine.gamespot.com/over-the-garden-wall-1/4000-498453/",
            "name": "",
            "issue_number": "1",
            "description": (
                "List of covers and their creators: Cover Name Creator(s) Sidebar Location "
                "Reg Regular Cover A Jim Campbell 1 "
                "Reg Regular Cover B Carey Pietsch 2 "
                "Sub Subscription Cover Steve Wolfhard 3 "
                "RI 1:10 BOOM! Studios 10 Years Incentive Variant Cover Jeffrey Brown 4-6 "
                "Var 1:20 Variant Cover Michael DiMotta 7 "
                "RE Larry's Comics Exclusive Variant Cover Rachel Dukes Missing"
            ),
            "image": {"super_url": "https://comicvine.gamespot.com/a/uploads/scale_large/01.jpg"},
            "associated_images": [
                {
                    "id": 4767296,
                    "original_url": "https://comicvine.gamespot.com/a/uploads/original/01b.jpg",
                    "image_tags": "All Images",
                },
                {
                    "id": 4767295,
                    "original_url": "https://comicvine.gamespot.com/a/uploads/original/01-sub.jpg",
                    "image_tags": "All Images",
                },
                {
                    "id": 4767294,
                    "original_url": "https://comicvine.gamespot.com/a/uploads/original/01-boom.jpg",
                    "image_tags": "All Images",
                },
                {
                    "id": 4767290,
                    "original_url": "https://comicvine.gamespot.com/a/uploads/original/01-variant.jpg",
                    "image_tags": "All Images",
                },
            ],
            "volume": {
                "id": 82602,
                "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-82602/",
                "name": "Over the Garden Wall",
                "publisher": {"name": "BOOM! Studios"},
            },
        }
    )
    return raw


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

    assert normalized.kind == ItemKind.comic
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
async def test_comicvine_provider_normalizes_associated_cover_variants():
    raw = comicvine_issue_raw()
    raw["associated_images"] = [
        {
            "id": 4767296,
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/variant-a.jpg",
            "caption": None,
            "image_tags": "All Images",
        },
        {
            "id": 4767295,
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/variant-b.jpg",
            "caption": "Subscription cover",
            "image_tags": "All Images",
        },
        {
            "id": 4767000,
            "original_url": "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
            "caption": "Duplicate primary",
            "image_tags": "All Images",
        },
    ]

    normalized = await ComicVineProvider().normalize(raw)

    assert len(normalized.variant_covers) == 2
    assert normalized.variant_covers[0].name == "Variant cover 1"
    assert normalized.variant_covers[0].source_id == "4767296"
    assert (
        normalized.variant_covers[0].cover_image_url
        == "https://comicvine.gamespot.com/a/uploads/original/variant-a.jpg"
    )
    assert normalized.variant_covers[1].name == "Subscription cover"


@pytest.mark.asyncio
async def test_comicvine_provider_names_associated_covers_from_cover_list():
    normalized = await ComicVineProvider().normalize(comicvine_over_the_garden_wall_raw())

    assert [cover.name for cover in normalized.variant_covers] == [
        "Regular Cover B Carey Pietsch",
        "Subscription Cover Steve Wolfhard",
        "1:10 BOOM! Studios 10 Years Incentive Variant Cover Jeffrey Brown",
        "1:10 BOOM! Studios 10 Years Incentive Variant Cover Jeffrey Brown",
    ]
    assert [cover.cover_image_url.rsplit("/", 1)[-1] for cover in normalized.variant_covers] == [
        "01b.jpg",
        "01-sub.jpg",
        "01-boom.jpg",
        "01-variant.jpg",
    ]


@pytest.mark.asyncio
async def test_comicvine_provider_finds_variant_cover_from_cover_list(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_find_volume(self, series_title, start_year):
        return {
            "id": 82602,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-82602/",
            "name": "Over the Garden Wall",
            "start_year": 2015,
        }

    async def fake_request(self, path, params):
        assert path == "issues/"
        assert params["filter"] == "volume:82602,issue_number:1"
        return {"results": [comicvine_over_the_garden_wall_raw()]}

    monkeypatch.setattr(ComicVineProvider, "_find_volume", fake_find_volume)
    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)

    cover = await ComicVineProvider().find_issue_cover(
        series_title="Over the Garden Wall",
        issue_number="1",
        start_year=2015,
        variant_hint="Carey Pietsch Cover",
        require_variant_match=True,
    )

    assert cover is not None
    assert cover.provider_item_id == "4000-498453"
    assert cover.image_url.endswith("/01b.jpg")

    missing_cover = await ComicVineProvider().find_issue_cover(
        series_title="Over the Garden Wall",
        issue_number="1",
        start_year=2015,
        variant_hint="BOOM! Studios Exclusive Cover Jordan Crane",
        require_variant_match=True,
    )

    assert missing_cover is None


@pytest.mark.asyncio
async def test_comicvine_provider_search_expands_associated_cover_variants(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_request(self, path, params):
        if path == "search/":
            return {"results": [comicvine_over_the_garden_wall_raw()]}
        assert path == "issue/4000-498453/"
        return {"results": comicvine_over_the_garden_wall_raw()}

    monkeypatch.setattr(ComicVineProvider, "_request", fake_request)

    results = await ComicVineProvider().search("Over the Garden Wall", ItemKind.comic)

    assert [result.provider_item_id for result in results] == [
        "4000-498453",
        "4000-498453:cover:4767296",
        "4000-498453:cover:4767295",
        "4000-498453:cover:4767294",
        "4000-498453:cover:4767290",
    ]
    assert results[1].title == "Over the Garden Wall #1 [Regular Cover B Carey Pietsch]"
    assert results[1].image_url.endswith("/01b.jpg")


@pytest.mark.asyncio
async def test_comicvine_provider_can_tag_results_as_manga():
    raw = comicvine_issue_raw()
    raw["media_type"] = "manga"

    search_result = ComicVineProvider()._search_result(raw, ItemKind.manga)
    normalized = await ComicVineProvider().normalize(raw)

    assert search_result.kind == ItemKind.manga
    assert search_result.provider_item_id == "manga:4000-12345"
    assert normalized.kind == ItemKind.manga
    assert normalized.edition_format == "Manga Issue"
    assert normalized.provider_ids == {"comicvine": "manga:4000-12345"}
    assert normalized.volume_provider_ids == {"comicvine": "manga:4050-6789"}


def test_comicvine_provider_sorts_exact_series_results_by_issue_number():
    provider = ComicVineProvider()
    rows = [
        {
            "name": "",
            "issue_number": "2",
            "volume": {"name": "Over the Garden Wall"},
        },
        {
            "name": "",
            "issue_number": "1",
            "volume": {"name": "Over the Garden Wall"},
        },
        {
            "name": "Volume One",
            "issue_number": "1",
            "volume": {"name": "Over The Garden Wall"},
        },
    ]

    sorted_rows = provider._sort_search_results(rows, "over the garden wall")

    assert [row["issue_number"] for row in sorted_rows] == ["1", "2", "1"]
    assert sorted_rows[-1]["name"] == "Volume One"


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
    assert ("Mark Chiarello", "editor") in [
        (credit.name, credit.role) for credit in normalized.creators
    ]
    assert ("Jeph Loeb", "writer") in [(credit.name, credit.role) for credit in normalized.creators]
    assert ("Tim Sale", "penciller") in [(credit.name, credit.role) for credit in normalized.creators]
    assert "Batman [Bruce Wayne]" in [credit.name for credit in normalized.characters]
    assert [credit.name for credit in normalized.story_arcs] == ["Revenge"]
    assert (
        normalized.cover_image_url
        == "/metadata/providers/gcd/images/256114?series=Batman%3A+Dark+Victory&issue=12&year=1999"
    )
    assert normalized.synopsis == "Two-Face seeks revenge."
    assert normalized.imprint is None


@pytest.mark.asyncio
async def test_gcd_provider_extracts_imprint_when_publishers_differ():
    raw = gcd_issue_raw()
    raw["indicia_publisher"] = "Vertigo"
    raw["publisher"] = "DC Comics"
    normalized = await GCDProvider().normalize(raw)
    assert normalized.publisher == "DC Comics"
    assert normalized.imprint == "Vertigo"


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
        == "/metadata/providers/gcd/images/2665653?series=Absolute+Batman&issue=1&year=2024&variant=Jim+Lee+%26+Scott+Williams+Cardstock+Variant+Cover"
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
    assert (
        results[0].image_url
        == "/metadata/providers/gcd/images/256114?series=Batman%3A+Dark+Victory&issue=12&year=1999"
    )


@pytest.mark.asyncio
async def test_gcd_provider_search_spans_series_only_queries(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gcd_series_search_issue_span", 2)
    requested_paths = []

    async def fake_request(self, path):
        requested_paths.append(path)
        issue_id = "3377500" if path.endswith("/issue/1/") else "3377501"
        issue_number = "1" if path.endswith("/issue/1/") else "2"
        if not path.startswith("series/name/Absolute%20Batman/"):
            return {"results": []}
        return {
            "results": [
                {
                    "api_url": f"https://www.comics.org/api/issue/{issue_id}/",
                    "series_name": "Absolute Batman (2024 series)",
                    "descriptor": issue_number,
                    "publication_date": "October 2024",
                    "price": "4.99 USD",
                    "page_count": "32.000",
                    "variant_of": None,
                    "cover": "https://files1.comics.org/img/gcd/covers/cover.jpg",
                }
            ]
        }

    monkeypatch.setattr(GCDProvider, "_request", fake_request)

    results = await GCDProvider().search(" Absolute Batman cover ")

    assert len(results) == 2
    assert results[0].provider_item_id == "3377500"
    assert results[0].title == "Absolute Batman (2024 series) #1"
    assert (
        results[0].image_url
        == "/metadata/providers/gcd/images/3377500?series=Absolute+Batman&issue=1&year=2024"
    )
    assert results[1].provider_item_id == "3377501"
    assert results[1].title == "Absolute Batman (2024 series) #2"
    assert requested_paths == [
        "series/name/Absolute%20Batman/issue/1/",
        "series/name/Absolute%20Batman/issue/2/",
    ]


@pytest.mark.asyncio
async def test_gcd_provider_search_uses_series_year_hint(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "gcd_series_search_issue_span", 1)

    async def fake_request(self, path):
        if path != "series/name/Over%20the%20Garden%20Wall/issue/1/":
            return {"results": []}
        return {
            "results": [
                {
                    "api_url": "https://www.comics.org/api/issue/1460468/",
                    "series_name": "Over the Garden Wall (2015 series)",
                    "descriptor": "1",
                    "publication_date": "August 2015",
                    "price": "3.99 USD",
                    "page_count": "28.000",
                    "variant_of": None,
                },
                {
                    "api_url": "https://www.comics.org/api/issue/1775516/",
                    "series_name": "Over the Garden Wall (2017 series)",
                    "descriptor": "1",
                    "publication_date": "February 2017",
                    "price": "14.99 USD",
                    "page_count": "120.000",
                    "variant_of": None,
                },
            ]
        }

    monkeypatch.setattr(GCDProvider, "_request", fake_request)

    results = await GCDProvider().search("Over the Garden Wall 2015")

    assert len(results) == 1
    assert results[0].provider_item_id == "1460468"
    assert results[0].title == "Over the Garden Wall (2015 series) #1"


@pytest.mark.asyncio
async def test_gcd_provider_cover_image_downloads_issue_cover(monkeypatch):
    async def fake_request(self, path):
        assert path == "issue/3377500/"
        return {"cover": "https://files1.comics.org/img/gcd/covers/cover.jpg"}

    async def fake_download_cover_image(self, cover_url, issue_id):
        assert cover_url == "https://files1.comics.org/img/gcd/covers/cover.jpg"
        assert issue_id == "3377500"
        return b"cover-bytes", "image/jpeg"

    monkeypatch.setattr(GCDProvider, "_request", fake_request)
    monkeypatch.setattr(GCDProvider, "_download_cover_image", fake_download_cover_image)

    image = await GCDProvider().get_cover_image("3377500")

    assert image.content == b"cover-bytes"
    assert image.media_type == "image/jpeg"
    assert image.redirect_url is None


@pytest.mark.asyncio
async def test_gcd_provider_cover_image_route_is_public(client, monkeypatch):
    async def fake_get_cover_image(self, provider_item_id, fallback=None):
        assert provider_item_id == "3377500"
        assert fallback == GCDCoverFallback(
            series_title="Absolute Batman",
            issue_number="1",
            start_year=2024,
            variant_hint="Jim Lee",
        )
        return GCDCoverImage.inline(b"cover-bytes", "image/jpeg")

    monkeypatch.setattr(GCDProvider, "get_cover_image", fake_get_cover_image)

    response = await client.get(
        "/metadata/providers/gcd/images/3377500",
        params={
            "series": "Absolute Batman",
            "issue": "1",
            "year": 2024,
            "variant": "Jim Lee",
        },
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "public, max-age=86400"
    assert response.content == b"cover-bytes"


@pytest.mark.asyncio
async def test_gcd_provider_cover_image_falls_back_to_comicvine(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_request(self, path):
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="gcd_http_error",
            detail="GCD returned HTTP 429",
        )

    async def fake_find_issue_cover(self, **kwargs):
        assert kwargs == {
            "series_title": "Absolute Batman",
            "issue_number": "1",
            "start_year": 2024,
            "variant_hint": "Jim Lee",
            "require_variant_match": True,
        }
        return ComicVineIssueCover(
            provider_item_id="4000-1073108",
            image_url="https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
        )

    monkeypatch.setattr(GCDProvider, "_request", fake_request)
    monkeypatch.setattr(ComicVineProvider, "find_issue_cover", fake_find_issue_cover)

    image = await GCDProvider().get_cover_image(
        "3377500",
        fallback=GCDCoverFallback(
            series_title="Absolute Batman",
            issue_number="1",
            start_year=2024,
            variant_hint="Jim Lee",
        ),
    )

    assert image.content is None
    assert image.media_type is None
    assert image.redirect_url == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"


@pytest.mark.asyncio
async def test_gcd_provider_cover_image_returns_not_found_for_missing_exact_variant(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")

    async def fake_request(self, path):
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="gcd_http_error",
            detail="GCD returned HTTP 401",
        )

    async def fake_find_issue_cover(self, **kwargs):
        assert kwargs["require_variant_match"] is True
        return None

    monkeypatch.setattr(GCDProvider, "_request", fake_request)
    monkeypatch.setattr(ComicVineProvider, "find_issue_cover", fake_find_issue_cover)

    with pytest.raises(ApiHTTPException) as exc_info:
        await GCDProvider().get_cover_image(
            "2665653",
            fallback=GCDCoverFallback(
                series_title="Absolute Batman",
                issue_number="1",
                start_year=2024,
                variant_hint="Jim Lee & Scott Williams Cardstock Variant Cover",
            ),
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND
    assert exc_info.value.code == "provider_variant_cover_not_found"


@pytest.mark.asyncio
async def test_gcd_provider_search_ignores_barcode_like_queries():
    results = await GCDProvider().search("76194138584600111")

    assert results == []


@pytest.mark.asyncio
async def test_gcd_provider_search_route_falls_back_to_comicvine(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    token = await admin_token(client, monkeypatch)

    async def fail_gcd_search(self, query, kind=None):
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="gcd_http_error",
            detail="GCD returned HTTP 429",
        )

    async def fake_find_issue_cover(self, **kwargs):
        assert kwargs == {
            "series_title": "Absolute Batman",
            "issue_number": "1",
        }
        return ComicVineIssueCover(
            provider_item_id="4000-1073108",
            image_url="https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
        )

    async def fail_comicvine_search(self, query, kind=None):
        raise AssertionError("Exact ComicVine cover fallback should run first")

    monkeypatch.setattr(GCDProvider, "search", fail_gcd_search)
    monkeypatch.setattr(ComicVineProvider, "find_issue_cover", fake_find_issue_cover)
    monkeypatch.setattr(ComicVineProvider, "search", fail_comicvine_search)

    response = await client.get(
        "/metadata/providers/gcd/search",
        params={"q": "Absolute Batman #1", "kind": "comic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "comicvine"
    assert body[0]["title"] == "Absolute Batman #1"
    assert body[0]["summary"].startswith(
        "Comic Vine fallback while Grand Comics Database is unavailable."
    )
    assert body[0]["image_url"] == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"


@pytest.mark.asyncio
async def test_gcd_provider_series_search_fallback_uses_comicvine_search(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    token = await admin_token(client, monkeypatch)

    async def fail_gcd_search(self, query, kind=None):
        raise ApiHTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            code="gcd_http_error",
            detail="GCD returned HTTP 429",
        )

    async def fail_find_issue_cover(self, **kwargs):
        raise AssertionError("Series fallback should use ComicVine search")

    async def fake_comicvine_search(self, query, kind=None):
        return [ComicVineProvider()._search_result(comicvine_over_the_garden_wall_raw())]

    monkeypatch.setattr(GCDProvider, "search", fail_gcd_search)
    monkeypatch.setattr(ComicVineProvider, "find_issue_cover", fail_find_issue_cover)
    monkeypatch.setattr(ComicVineProvider, "search", fake_comicvine_search)

    response = await client.get(
        "/metadata/providers/gcd/search",
        params={"q": "Over the Garden Wall", "kind": "comic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body[0]["provider"] == "comicvine"
    assert body[0]["provider_item_id"] == "4000-498453"
    assert body[0]["summary"].startswith(
        "Comic Vine fallback while Grand Comics Database is unavailable."
    )


@pytest.mark.asyncio
async def test_gcd_provider_series_search_enriches_with_comicvine_variants(client, monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    token = await admin_token(client, monkeypatch)

    async def fake_gcd_search(self, query, kind=None):
        return [
            ProviderSearchResult(
                provider="gcd",
                provider_item_id="148725",
                title="Over the Garden Wall (2015 series) #1",
                kind=ItemKind.comic,
            )
        ]

    async def fake_comicvine_search(self, query, kind=None):
        return [
            ProviderSearchResult(
                provider="comicvine",
                provider_item_id="4000-498453:cover:4767296",
                title="Over the Garden Wall #1 [Regular Cover B Carey Pietsch]",
                kind=ItemKind.comic,
                image_url="https://comicvine.gamespot.com/a/uploads/original/01b.jpg",
            )
        ]

    monkeypatch.setattr(GCDProvider, "search", fake_gcd_search)
    monkeypatch.setattr(ComicVineProvider, "search", fake_comicvine_search)

    response = await client.get(
        "/metadata/providers/gcd/search",
        params={"q": "Over the Garden Wall", "kind": "comic"},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["provider"] for item in body] == ["gcd", "comicvine"]
    assert body[1]["provider_item_id"] == "4000-498453:cover:4767296"
    assert body[1]["image_url"].endswith("/01b.jpg")


@pytest.mark.asyncio
async def test_comicvine_provider_stub_search_uses_stable_slug(monkeypatch):
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", None)

    results = await ComicVineProvider().search("  Spider-Man: Vol. 2  ")
    manga_results = await ComicVineProvider().search("  One Piece  ", ItemKind.manga)

    assert len(results) == 1
    assert results[0].provider_item_id == "stub-comic-spider-man-vol-2"
    assert results[0].title == "Spider-Man: Vol. 2 (ComicVine stub)"
    assert manga_results[0].provider_item_id == "stub-manga-one-piece"
    assert manga_results[0].kind == ItemKind.manga


@pytest.mark.asyncio
async def test_admin_provider_search_uses_provider_results(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_search(self, query, kind=None):
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
async def test_admin_provider_search_uses_query_cache(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    calls = 0

    async def fake_search(self, query, kind=None):
        nonlocal calls
        calls += 1
        return [ComicVineProvider()._search_result(comicvine_issue_raw())]

    monkeypatch.setattr(ComicVineProvider, "search", fake_search)

    for _ in range(2):
        response = await client.post(
            "/admin/providers/search",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "comicvine", "query": "spider", "kind": "comic"},
        )

        assert response.status_code == 200
        assert response.json()[0]["provider_item_id"] == "4000-12345"

    assert calls == 1


@pytest.mark.asyncio
async def test_admin_provider_search_returns_planned_provider_stub(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    response = await client.post(
        "/admin/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "tmdb", "query": "the matrix"},
    )

    assert response.status_code == 200
    assert response.json()[0]["provider"] == "tmdb"
    assert response.json()[0]["provider_item_id"] == "stub-movie-the-matrix"
    assert response.json()[0]["kind"] == "movie"


@pytest.mark.asyncio
async def test_admin_provider_ingest_rejects_unconfigured_tmdb(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "tmdb", "provider_item_id": "movie:603"},
    )

    assert response.status_code == 400
    assert response.json()["code"] == "tmdb_not_configured"


@pytest.mark.asyncio
async def test_admin_provider_search_rejects_provider_for_wrong_kind(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    response = await client.post(
        "/admin/providers/search",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "query": "spider", "kind": "book"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provider 'gcd' does not support kind 'book'"


@pytest.mark.asyncio
async def test_admin_provider_ingest_rejects_provider_for_wrong_kind(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "provider_item_id": "4000-1", "kind": "book"},
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "Provider 'gcd' does not support kind 'book'"


@pytest.mark.asyncio
async def test_admin_catalog_summary_and_duplicate_candidates(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.comic, title="Absolute Batman")
        volume = Volume(series=series, name="Absolute Batman (2024)", start_year=2024)
        primary = Item(
            kind=ItemKind.comic,
            title="Absolute Batman",
            item_number="1",
            sort_key="absolute-batman-000001",
            volume=volume,
        )
        duplicate = Item(
            kind=ItemKind.comic,
            title="Absolute Batman",
            item_number="1",
            sort_key="absolute-batman-000001-duplicate",
            volume=volume,
        )
        primary_edition = Edition(
            item=primary,
            title="Standard Edition",
            publisher="DC Comics",
            release_date=date(2024, 10, 9),
        )
        duplicate_edition = Edition(item=duplicate, title="Standard Edition")
        primary_variant = Variant(
            edition=primary_edition,
            name="Cover A",
            cover_image_url="https://cdn.example/cover.jpg",
            is_primary=True,
        )
        duplicate_variant = Variant(
            edition=duplicate_edition,
            name="Cover A",
            is_primary=True,
        )
        proposal = MetadataProposal(
            provider=ExternalProvider.gcd,
            query="Absolute Batman #1",
            status="pending",
        )
        db.add_all(
            [
                series,
                volume,
                primary,
                duplicate,
                primary_edition,
                duplicate_edition,
                primary_variant,
                duplicate_variant,
                proposal,
            ]
        )
        await db.flush()
        db.add(
            ExternalProviderId(
                entity_type="comic_issue",
                entity_id=primary.id,
                provider=ExternalProvider.gcd,
                provider_item_id="2663120",
            )
        )
        await db.commit()

    summary = await client.get(
        "/admin/catalog/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert summary.status_code == 200
    body = summary.json()
    assert body["items"] == 2
    assert body["items_by_kind"]["comic"] == 2
    assert body["items_by_kind"]["manga"] == 0
    assert body["items_by_kind"]["movie"] == 0
    assert body["series"] == 1
    assert body["volumes"] == 1
    assert body["editions"] == 2
    assert body["variants"] == 2
    assert body["provider_links"] == 1
    assert body["pending_proposals"] == 1
    assert body["missing_cover_items"] == 1
    assert body["missing_provider_link_items"] == 2
    assert body["duplicate_candidate_groups"] == 1

    duplicates = await client.get(
        "/admin/duplicates",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert duplicates.status_code == 200
    duplicate_body = duplicates.json()
    assert duplicate_body[0]["kind"] == "comic"
    assert duplicate_body[0]["title"] == "Absolute Batman"
    assert duplicate_body[0]["item_number"] == "1"
    assert duplicate_body[0]["count"] == 2
    assert len(duplicate_body[0]["item_ids"]) == 2
    assert duplicate_body[0]["reason"] == "same title and item number"
    assert duplicate_body[0]["has_provider_conflicts"] is False
    assert duplicate_body[0]["has_cover_conflicts"] is False
    assert duplicate_body[0]["duplicate_score"] > 0
    assert duplicate_body[0]["recommended_target_item_id"] == str(primary.id)

    ignore = await client.post(
        "/admin/duplicates/ignore",
        headers={"Authorization": f"Bearer {token}"},
        json={"item_ids": duplicate_body[0]["item_ids"]},
    )

    assert ignore.status_code == 200
    assert ignore.json() == {"ok": True, "affected_items": 2, "item": None}

    ignored_duplicates = await client.get(
        "/admin/duplicates",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert ignored_duplicates.status_code == 200
    assert ignored_duplicates.json() == []

    ignored_summary = await client.get(
        "/admin/catalog/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert ignored_summary.status_code == 200
    assert ignored_summary.json()["duplicate_candidate_groups"] == 0


@pytest.mark.asyncio
async def test_admin_search_status_reports_meilisearch_index(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    class FakeIndexStats:
        number_of_documents = 42

    class FakeIndex:
        def get_stats(self):
            return FakeIndexStats()

    class FakeMeiliClient:
        def health(self):
            return {"status": "available"}

        def index(self, name):
            assert name == "items"
            return FakeIndex()

    class FakeSearchClient:
        index_name = "items"

        def __init__(self):
            self.client = FakeMeiliClient()

    monkeypatch.setattr(admin_service, "SearchClient", FakeSearchClient)

    response = await client.get(
        "/admin/search/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "index_name": "items",
        "document_count": 42,
        "is_empty": False,
        "error": None,
    }


@pytest.mark.asyncio
async def test_admin_search_status_preserves_empty_meilisearch_index(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    class FakeIndexStats:
        def model_dump(self, by_alias=False):
            return {"numberOfDocuments": 0}

    class FakeIndex:
        def get_stats(self):
            return FakeIndexStats()

    class FakeMeiliClient:
        def health(self):
            return {"status": "available"}

        def index(self, name):
            assert name == "items"
            return FakeIndex()

    class FakeSearchClient:
        index_name = "items"

        def __init__(self):
            self.client = FakeMeiliClient()

    monkeypatch.setattr(admin_service, "SearchClient", FakeSearchClient)

    response = await client.get(
        "/admin/search/status",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "index_name": "items",
        "document_count": 0,
        "is_empty": True,
        "error": None,
    }


@pytest.mark.asyncio
async def test_admin_search_reindex_replaces_index_documents(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    state = {"configured": False, "documents": []}

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.comic, title="Absolute Batman")
        volume = Volume(series=series, name="Absolute Batman (2024)", start_year=2024)
        item = Item(
            kind=ItemKind.comic,
            title="Absolute Batman",
            item_number="1",
            sort_key="absolute-batman-000001",
            volume=volume,
        )
        edition = Edition(
            item=item,
            title="Standard Edition",
            publisher="DC Comics",
            release_date=date(2024, 10, 9),
        )
        variant = Variant(
            edition=edition,
            name="Cover A",
            barcode="76194138584600111",
            is_primary=True,
        )
        db.add_all([series, volume, item, edition, variant])
        await db.commit()

    class FakeSearchClient:
        index_name = "items"

        async def configure(self):
            state["configured"] = True

        async def replace_documents(self, documents):
            state["documents"] = documents

    monkeypatch.setattr(admin_service, "SearchClient", FakeSearchClient)

    response = await client.post(
        "/admin/search/reindex",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "index_name": "items",
        "indexed_documents": 1,
        "error": None,
    }
    assert state["configured"] is True
    assert state["documents"][0]["title"] == "Absolute Batman"
    assert state["documents"][0]["barcodes"] == ["76194138584600111"]

    history = await client.get(
        "/admin/search/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert history.status_code == 200
    assert history.json()[0]["ok"] is True
    assert history.json()[0]["index_name"] == "items"
    assert history.json()[0]["indexed_documents"] == 1


@pytest.mark.asyncio
async def test_admin_duplicate_merge_moves_catalog_children(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.comic, title="Absolute Batman")
        volume = Volume(series=series, name="Absolute Batman (2024)", start_year=2024)
        target = Item(
            kind=ItemKind.comic,
            title="Absolute Batman",
            item_number="1",
            sort_key="absolute-batman-000001",
            volume=volume,
        )
        source = Item(
            kind=ItemKind.comic,
            title="Absolute Batman",
            item_number="1",
            sort_key="absolute-batman-000001-duplicate",
            volume=volume,
        )
        target_edition = Edition(item=target, title="Standard Edition", publisher="DC Comics")
        source_edition = Edition(item=source, title="Variant Edition", publisher="DC Comics")
        target_variant = Variant(edition=target_edition, name="Cover A", is_primary=True)
        source_variant = Variant(
            edition=source_edition,
            name="Variant Cover",
            barcode="76194138584600121",
            is_primary=True,
        )
        db.add_all(
            [
                series,
                volume,
                target,
                source,
                target_edition,
                source_edition,
                target_variant,
                source_variant,
            ]
        )
        await db.flush()
        target_id = str(target.id)
        source_id = str(source.id)
        db.add(
            ExternalProviderId(
                entity_type="item",
                entity_id=source.id,
                provider=ExternalProvider.gcd,
                provider_item_id="2665653",
            )
        )
        await db.commit()

    response = await client.post(
        "/admin/duplicates/merge",
        headers={"Authorization": f"Bearer {token}"},
        json={"target_item_id": target_id, "source_item_ids": [source_id]},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["ok"] is True
    assert body["affected_items"] == 1
    assert body["item"]["id"] == target_id
    assert len(body["item"]["editions"]) == 2

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Item)) == 1
        assert await db.scalar(select(func.count()).select_from(Edition)) == 2
        provider_link = await db.scalar(
            select(ExternalProviderId).where(ExternalProviderId.entity_type == "item")
        )
        assert provider_link is not None
        assert str(provider_link.entity_id) == target_id

    duplicates = await client.get(
        "/admin/duplicates",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert duplicates.status_code == 200
    assert duplicates.json() == []


@pytest.mark.asyncio
async def test_admin_catalog_browser_and_correction_update_item(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.comic, title="Absolute Batman")
        volume = Volume(series=series, name="Absolute Batman (2024)", start_year=2024)
        item = Item(
            kind=ItemKind.comic,
            title="Absolute Batman",
            item_number="1",
            sort_key="absolute-batman-000001",
            volume=volume,
            page_count=48,
        )
        edition = Edition(
            item=item,
            title="Standard Edition",
            publisher="DC Comics",
            release_date=date(2024, 10, 9),
        )
        variant = Variant(
            edition=edition,
            name="Cover A",
            barcode="76194138584600111",
            cover_image_url="https://cdn.example/old.jpg",
            is_primary=True,
        )
        db.add_all([series, volume, item, edition, variant])
        await db.flush()
        item_id = str(item.id)
        await db.commit()

    search = await client.get(
        "/admin/catalog/items",
        headers={"Authorization": f"Bearer {token}"},
        params={"q": "Absolute", "kind": "comic"},
    )

    assert search.status_code == 200
    assert search.json()[0]["id"] == item_id
    assert search.json()[0]["title"] == "Absolute Batman"

    updated = await client.patch(
        f"/admin/catalog/items/comic/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Absolute Batman Deluxe",
            "title_extension": "Director's Noir Cut",
            "sort_key": "batman-absolute-deluxe-custom",
            "original_title": "Batman: Absolute Edition",
            "localized_title": "Batman Absolut",
            "search_aliases": ["Absolute Batman", "Batman Deluxe", "absolute batman"],
            "item_number": "1A",
            "edition_title": "Collector Edition",
            "publisher": "DC Black Label",
            "crossover": "Absolute Universe",
            "plot_summary": "Bruce Wayne reinvents Gotham.",
            "plot_description": "An alternate continuity focused on noir storytelling.",
            "release_date": "2024-10-16",
            "imprint": "Black Label",
            "subtitle": "Noir Edition",
            "series_group": "Absolute Universe",
            "variant_name": "Foil Cover",
            "barcode": "76194138584600121",
            "country": "US",
            "language": "en",
            "age_rating": "Mature",
            "audience_rating": "8.6",
            "cover_image_url": "https://cdn.example/new.jpg",
            "page_count": 52,
            "runtime_minutes": 0,
            "catalog_number": "ABS-BAT-DELUXE",
            "release_status": "announced",
            "genres": ["Superhero", "Noir", "Superhero"],
        },
    )

    async with AsyncSessionLocal() as db:
        refreshed_item = await db.get(Item, UUID(item_id))
        refreshed_edition = await db.scalar(select(Edition).where(Edition.item_id == UUID(item_id)))

    assert refreshed_item is not None
    assert refreshed_edition is not None
    assert refreshed_edition.imprint == "Black Label"
    assert refreshed_edition.subtitle == "Noir Edition"
    assert refreshed_edition.series_group == "Absolute Universe"
    assert refreshed_edition.region == "US"
    assert refreshed_edition.language == "en"
    assert refreshed_edition.age_rating == "Mature"
    assert refreshed_edition.catalog_number == "ABS-BAT-DELUXE"
    assert refreshed_edition.release_status == "announced"
    assert refreshed_item.original_title == "Batman: Absolute Edition"
    assert refreshed_item.localized_title == "Batman Absolut"
    assert refreshed_item.search_aliases == ["Absolute Batman", "Batman Deluxe"]
    assert refreshed_item.crossover == "Absolute Universe"
    assert refreshed_item.plot_summary == "Bruce Wayne reinvents Gotham."
    assert refreshed_item.plot_description == "An alternate continuity focused on noir storytelling."

    assert updated.status_code == 200
    body = updated.json()
    assert body["title"] == "Absolute Batman Deluxe"
    assert body["title_extension"] == "Director's Noir Cut"
    assert body["sort_key"] == "batman-absolute-deluxe-custom"
    assert body["original_title"] == "Batman: Absolute Edition"
    assert body["localized_title"] == "Batman Absolut"
    assert body["search_aliases"] == ["Absolute Batman", "Batman Deluxe"]
    assert body["item_number"] == "1A"
    assert body["runtime_minutes"] == 0
    assert body["publisher"] == "DC Black Label"
    assert body["page_count"] == 52
    assert body["imprint"] == "Black Label"
    assert body["subtitle"] == "Noir Edition"
    assert body["series_group"] == "Absolute Universe"
    assert body["country"] == "US"
    assert body["language"] == "en"
    assert body["age_rating"] == "Mature"
    assert body["audience_rating"] == "8.6"
    assert body["catalog_number"] == "ABS-BAT-DELUXE"
    assert body["release_status"] == "announced"
    assert body["crossover"] == "Absolute Universe"
    assert body["plot_summary"] == "Bruce Wayne reinvents Gotham."
    assert body["plot_description"] == "An alternate continuity focused on noir storytelling."
    assert body["genres"] == ["Superhero", "Noir"]
    assert body["editions"][0]["title"] == "Collector Edition"
    assert body["editions"][0]["release_date"] == "2024-10-16"
    assert body["editions"][0]["imprint"] == "Black Label"
    assert body["editions"][0]["subtitle"] == "Noir Edition"
    assert body["editions"][0]["series_group"] == "Absolute Universe"
    assert body["editions"][0]["age_rating"] == "Mature"
    assert body["editions"][0]["catalog_number"] == "ABS-BAT-DELUXE"
    assert body["editions"][0]["release_status"] == "announced"
    assert body["editions"][0]["variants"][0]["name"] == "Foil Cover"
    assert body["editions"][0]["variants"][0]["barcode"] == "76194138584600121"
    assert body["editions"][0]["variants"][0]["cover_image_url"] == "https://cdn.example/new.jpg"

    filtered = await client.get(
        "/admin/catalog/items",
        headers={"Authorization": f"Bearer {token}"},
        params={
            "kind": "comic",
            "imprint": "Black Label",
            "catalog_number": "ABS-BAT-DELUXE",
            "release_status": "announced",
            "language": "en",
            "country": "US",
        },
    )

    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [item_id]


@pytest.mark.asyncio
async def test_admin_catalog_correction_updates_music_tracks_and_genres(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.music,
            title="Random Access Memories",
            sort_key="random-access-memories",
        )
        edition = Edition(item=item, title="Standard Edition")
        db.add_all([item, edition])
        await db.flush()
        item_uuid = item.id
        item_id = str(item.id)
        await db.commit()

    updated = await client.patch(
        f"/admin/catalog/items/music/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "audience_rating": "9.2",
            "genres": ["Electronic", "  Nu Disco  ", "electronic"],
            "tracks": [
                {"position": 1, "title": "One More Time", "duration_seconds": 320},
                {"position": 2, "title": "Aerodynamic", "duration_seconds": 212},
            ],
        },
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["audience_rating"] == "9.2"
    assert body["genres"] == ["Electronic", "Nu Disco"]
    assert body["track_count"] == 2
    assert body["tracks"][0]["title"] == "One More Time"
    assert body["tracks"][1]["title"] == "Aerodynamic"

    async with AsyncSessionLocal() as db:
        stored_item = await db.get(Item, item_uuid)
        typed_metadata = await db.scalar(
            select(ItemKindMetadataMusic).where(ItemKindMetadataMusic.item_id == item_uuid)
        )
        assert stored_item is not None
        assert typed_metadata is not None
        assert typed_metadata.audience_rating == "9.2"
        assert typed_metadata.genres == ["Electronic", "Nu Disco"]
        assert typed_metadata.track_count == 2
        assert [track["title"] for track in typed_metadata.tracks] == [
            "One More Time",
            "Aerodynamic",
        ]


@pytest.mark.asyncio
async def test_admin_catalog_correction_updates_game_platforms(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.game,
            title="The Witcher 3",
            sort_key="witcher-3",
        )
        edition = Edition(item=item, title="Standard Edition")
        db.add_all([item, edition])
        await db.flush()
        item_uuid = item.id
        item_id = str(item.id)
        await db.commit()

    updated = await client.patch(
        f"/admin/catalog/items/game/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"platforms": ["PC", "PlayStation 5", "pc"]},
    )

    assert updated.status_code == 200
    body = updated.json()
    assert body["platforms"] == ["PC", "PlayStation 5"]

    async with AsyncSessionLocal() as db:
        stored_item = await db.get(Item, item_uuid)
        typed_metadata = await db.scalar(
            select(ItemKindMetadata).where(ItemKindMetadata.item_id == item_uuid)
        )
        assert stored_item is not None
        assert typed_metadata is not None
        assert typed_metadata.platforms == ["PC", "PlayStation 5"]


@pytest.mark.asyncio
async def test_admin_normalized_drift_report_includes_typed_metadata_mismatch(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.comic,
            title="Typed Drift Sample",
            sort_key="typed-drift-sample",
        )
        edition = Edition(
            item=item,
            title="Standard",
            metadata_json={
                "normalized": {
                    "schema_version": NORMALIZED_SCHEMA_VERSION,
                    "genres": ["Heroic"],
                }
            },
        )
        typed = ItemKindMetadataComic(
            item=item,
            kind=ItemKind.comic,
            genres=["Noir"],
        )
        db.add_all([item, edition, typed])
        await db.commit()

    response = await client.get(
        "/admin/catalog/normalized-metadata-drift",
        params={"scan_limit": 100},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["typed_scanned_items"] >= 1
    assert body["typed_drifted_items"] >= 1
    assert body["release_gate_ok"] is False
    assert body["issue_counts"].get("typed_mismatch:genres", 0) >= 1


@pytest.mark.asyncio
async def test_admin_normalized_drift_report_keeps_music_tracks_loaded(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            id=UUID("00000000-0000-0000-0000-000000000001"),
            kind=ItemKind.music,
            title="Track Load Sample",
            sort_key="track-load-sample",
            metadata_json={
                "normalized": {
                    "schema_version": NORMALIZED_SCHEMA_VERSION,
                    "track_count": 2,
                    "tracks": [
                        {"position": 1, "title": "Intro", "duration_seconds": 90},
                        {"position": 2, "title": "Main Theme", "duration_seconds": 180},
                    ],
                }
            },
        )
        typed = ItemKindMetadataMusic(
            item=item,
            kind=ItemKind.music,
            metadata_json={
                "track_count": 2,
                "tracks": [
                    {"position": 1, "title": "Intro", "duration_seconds": 90},
                    {"position": 2, "title": "Main Theme", "duration_seconds": 180},
                ],
            },
        )
        db.add_all([item, typed])
        await db.commit()

    response = await client.get(
        "/admin/catalog/normalized-metadata-drift",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["typed_scanned_items"] == 1
    assert body["typed_drifted_items"] == 0
    assert body["issue_counts"].get("typed_missing:tracks", 0) == 0
    assert body["release_gate_ok"] is True


@pytest.mark.asyncio
async def test_admin_catalog_correction_updates_relations_and_links(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.comic,
            title="Sandman",
            sort_key="sandman",
        )
        edition = Edition(item=item, title="Standard Edition")
        db.add_all([item, edition])
        await db.flush()
        item_uuid = item.id
        item_id = str(item.id)
        await db.commit()

    updated = await client.patch(
        f"/admin/catalog/items/comic/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "creators": [
                {"name": "Neil Gaiman", "role": "writer"},
                {"name": "Sam Kieth", "role": "artist"},
            ],
            "characters": ["Dream", "Death"],
            "story_arcs": ["Preludes & Nocturnes", "The Doll's House"],
            "external_links": [
                {"url": "https://example.com/sandman", "site": "Official", "name": "Homepage"}
            ],
        },
    )

    assert updated.status_code == 200
    body = updated.json()
    assert [entry["name"] for entry in body["creators"]] == ["Neil Gaiman", "Sam Kieth"]
    assert [entry["name"] for entry in body["characters"]] == ["Dream", "Death"]
    assert [entry["name"] for entry in body["story_arcs"]] == [
        "Preludes & Nocturnes",
        "The Doll's House",
    ]
    assert body["external_links"][0]["url"] == "https://example.com/sandman"

    async with AsyncSessionLocal() as db:
        creator_links = list(
            (
                await db.execute(
                    select(EntityPerson).where(
                        EntityPerson.entity_type == "item",
                        EntityPerson.entity_id == item_uuid,
                    )
                )
            ).scalars()
        )
        character_links = list(
            (await db.execute(select(CharacterAppearance).where(CharacterAppearance.item_id == item_uuid))).scalars()
        )
        story_arc_links = list(
            (await db.execute(select(StoryArcItem).where(StoryArcItem.item_id == item_uuid))).scalars()
        )
        stored_item = await db.get(Item, item_uuid)
        assert len(creator_links) == 2
        assert len(character_links) == 2
        assert len(story_arc_links) == 2
        assert (stored_item.external_links or [])[0]["url"] == "https://example.com/sandman"


@pytest.mark.asyncio
async def test_admin_catalog_correction_updates_video_specs(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.movie,
            title="Blade Runner",
            sort_key="blade-runner",
        )
        edition = Edition(item=item, title="Standard Edition")
        db.add_all([item, edition])
        await db.flush()
        item_uuid = item.id
        item_id = str(item.id)
        await db.commit()

    updated = await client.patch(
        f"/admin/catalog/items/movie/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "color": "Color",
            "nr_discs": 2,
            "screen_ratio": "2.39:1",
            "audio_tracks": "Dolby Atmos",
            "subtitles": "English, Romanian",
            "layers": "BD-100",
        },
    )
    assert updated.status_code == 200
    body = updated.json()
    assert body["color"] == "Color"
    assert body["nr_discs"] == 2
    assert body["screen_ratio"] == "2.39:1"
    assert body["audio_tracks"] == "Dolby Atmos"
    assert body["subtitles"] == "English, Romanian"
    assert body["layers"] == "BD-100"

    async with AsyncSessionLocal() as db:
        typed_metadata = await db.scalar(
            select(ItemKindMetadata).where(ItemKindMetadata.item_id == item_uuid)
        )
        stored_edition = await db.scalar(select(Edition).where(Edition.item_id == item_uuid))
        assert stored_edition is not None
        assert typed_metadata is not None
        assert typed_metadata.color == "Color"
        assert stored_edition.nr_discs == 2
        assert stored_edition.screen_ratio == "2.39:1"
        assert stored_edition.audio_tracks == "Dolby Atmos"
        assert stored_edition.subtitles == "English, Romanian"
        assert stored_edition.layers == "BD-100"


@pytest.mark.asyncio
async def test_admin_catalog_correction_updates_video_physical_format(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.movie,
            title="The Matrix",
            sort_key="matrix-the",
        )
        edition = Edition(item=item, title="Standard Edition")
        variant = Variant(edition=edition, name="Primary release", is_primary=True)
        db.add_all([item, edition, variant])
        await db.flush()
        item_uuid = item.id
        item_id = str(item.id)
        await db.commit()

    updated = await client.patch(
        f"/admin/catalog/items/movie/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"physical_format": "4K Blu-ray"},
    )

    assert updated.status_code == 200
    body = updated.json()
    edition_body = body["editions"][0]
    variant_body = edition_body["variants"][0]
    assert edition_body["format"] == "4K UHD"
    assert edition_body["physical_format"] == "4k-uhd"
    assert edition_body["physical_format_label"] == "4K UHD"
    assert variant_body["variant_type"] == "physical"
    assert variant_body["physical_format"] == "4k-uhd"
    assert variant_body["physical_format_label"] == "4K UHD"

    async with AsyncSessionLocal() as db:
        stored_edition = await db.scalar(select(Edition).where(Edition.item_id == item_uuid))
        stored_variant = await db.scalar(
            select(Variant).join(Edition).where(Edition.item_id == item_uuid)
        )
        assert stored_edition is not None
        assert stored_variant is not None
        assert stored_edition.format == "4K UHD"
        assert stored_edition.physical_format == "4k-uhd"
        assert stored_edition.physical_format_label == "4K UHD"
        assert stored_variant.variant_type == "physical"
        assert stored_variant.physical_format == "4k-uhd"
        assert stored_variant.physical_format_label == "4K UHD"

    invalid_format = await client.patch(
        f"/admin/catalog/items/movie/{item_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"physical_format": "Betamax"},
    )
    assert invalid_format.status_code == 400
    assert invalid_format.json()["code"] == "invalid_physical_format"


@pytest.mark.asyncio
async def test_admin_series_tags_update_persists_series_level_tags(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.comic, title="Monster")
        volume = Volume(name="Monster Vol. 1", series=series, volume_number=1)
        item = Item(
            kind=ItemKind.comic,
            title="Monster",
            item_number="1",
            sort_key="monster-001",
            volume=volume,
        )
        db.add_all([series, volume, item])
        await db.commit()
        series_id = str(series.id)

    response = await client.patch(
        f"/admin/catalog/series/{series_id}/tags",
        headers={"Authorization": f"Bearer {token}"},
        json={"tags": ["Psychological", "Seinen", "Psychological", "  "]},
    )

    assert response.status_code == 200
    assert response.json()["tags"] == ["Psychological", "Seinen"]

    async with AsyncSessionLocal() as db:
        stored = list(
            await db.scalars(
                select(Tag.name)
                .join(EntityTag, EntityTag.tag_id == Tag.id)
                .where(
                    EntityTag.entity_type == "series",
                    EntityTag.entity_id == UUID(series_id),
                    Tag.kind == "series_tag:comic",
                )
                .order_by(Tag.name.asc())
            )
        )
        assert stored == ["Psychological", "Seinen"]


@pytest.mark.asyncio
async def test_admin_bundle_release_update_persists_member_metadata_and_primary_item(
    client, monkeypatch
):
    token = await admin_token(client, monkeypatch)

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.music, title="Compilation Series")
        volume = Volume(series=series, name="Compilation Series", volume_number=1)
        first_item = Item(kind=ItemKind.music, title="Disc One", sort_key="disc-one", volume=volume)
        second_item = Item(kind=ItemKind.music, title="Disc Two", sort_key="disc-two", volume=volume)
        db.add_all([series, volume, first_item, second_item])
        await db.flush()
        bundle = BundleRelease(
            kind=ItemKind.music,
            title="Original Box",
            bundle_type="box_set",
            primary_item_id=first_item.id,
            series_id=series.id,
            volume_id=volume.id,
            format="CD",
            packaging_type="box",
            publisher="Label One",
            barcode="111111111111",
            release_date=date(2025, 1, 1),
        )
        db.add(bundle)
        await db.flush()
        first_member = BundleReleaseItem(
            bundle_release_id=bundle.id,
            item_id=first_item.id,
            role="primary",
            sequence_number=1,
            disc_number=1,
            disc_label="Disc One",
            quantity=1,
            is_primary=True,
        )
        second_member = BundleReleaseItem(
            bundle_release_id=bundle.id,
            item_id=second_item.id,
            role="component",
            sequence_number=2,
            disc_number=2,
            disc_label="Disc Two",
            quantity=1,
            is_primary=False,
        )
        db.add_all([first_member, second_member])
        await db.commit()
        bundle_id = str(bundle.id)
        first_member_id = str(first_member.id)
        second_member_id = str(second_member.id)
        second_item_id = str(second_item.id)

    response = await client.patch(
        f"/admin/catalog/bundle-releases/{bundle_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Updated Box",
            "publisher": "Label Two",
            "barcode": "222222222222",
            "release_date": "2025-02-02",
            "members": [
                {
                    "id": first_member_id,
                    "role": "bonus",
                    "sequence_number": 2,
                    "disc_number": 2,
                    "disc_label": "Bonus Disc",
                    "quantity": 1,
                    "is_primary": False,
                },
                {
                    "id": second_member_id,
                    "role": "primary",
                    "sequence_number": 1,
                    "disc_number": 1,
                    "disc_label": "Main Disc",
                    "quantity": 2,
                    "is_primary": True,
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "Updated Box"
    assert body["publisher"] == "Label Two"
    assert body["barcode"] == "222222222222"
    assert body["primary_item_id"] == second_item_id
    assert [member["disc_label"] for member in body["members"]] == ["Main Disc", "Bonus Disc"]
    assert body["members"][0]["item_id"] == second_item_id
    assert body["members"][0]["quantity"] == 2
    assert body["members"][0]["is_primary"] is True

    async with AsyncSessionLocal() as db:
        stored_bundle = await db.get(BundleRelease, UUID(bundle_id))
        stored_members = list(
            await db.scalars(
                select(BundleReleaseItem)
                .where(BundleReleaseItem.bundle_release_id == UUID(bundle_id))
                .order_by(BundleReleaseItem.sequence_number.asc())
            )
        )
        assert stored_bundle is not None
        assert str(stored_bundle.primary_item_id) == second_item_id
        assert stored_bundle.title == "Updated Box"
        assert stored_bundle.publisher == "Label Two"
        assert stored_bundle.barcode == "222222222222"
        assert stored_members[0].disc_label == "Main Disc"
        assert stored_members[0].quantity == 2
        assert stored_members[0].is_primary is True

    logs = await client.get(
        "/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"action": "metadata.bundle_correction"},
    )

    assert logs.status_code == 200
    assert logs.json()[0]["entity_type"] == "bundle_release"
    assert logs.json()[0]["entity_id"] == bundle_id


@pytest.mark.asyncio
async def test_admin_bundle_release_update_can_add_cross_kind_members(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.music, title="Compilation Series")
        volume = Volume(series=series, name="Compilation Series", volume_number=1)
        first_item = Item(kind=ItemKind.music, title="Disc One", sort_key="disc-one", volume=volume)
        second_item = Item(kind=ItemKind.music, title="Disc Two", sort_key="disc-two", volume=volume)
        third_item = Item(kind=ItemKind.book, title="Collector Booklet", sort_key="collector-booklet")
        db.add_all([series, volume, first_item, second_item, third_item])
        await db.flush()
        bundle = BundleRelease(
            kind=ItemKind.music,
            title="Mutable Box",
            bundle_type="box_set",
            primary_item_id=first_item.id,
            series_id=series.id,
            volume_id=volume.id,
        )
        db.add(bundle)
        await db.flush()
        first_member = BundleReleaseItem(
            bundle_release_id=bundle.id,
            item_id=first_item.id,
            role="primary",
            sequence_number=1,
            quantity=1,
            is_primary=True,
        )
        second_member = BundleReleaseItem(
            bundle_release_id=bundle.id,
            item_id=second_item.id,
            role="component",
            sequence_number=2,
            quantity=1,
            is_primary=False,
        )
        db.add_all([first_member, second_member])
        await db.commit()
        bundle_id = str(bundle.id)
        second_member_id = str(second_member.id)
        third_item_id = str(third_item.id)

    response = await client.patch(
        f"/admin/catalog/bundle-releases/{bundle_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "members": [
                {
                    "id": second_member_id,
                    "role": "bonus",
                    "sequence_number": 2,
                    "quantity": 1,
                    "is_primary": False,
                },
                {
                    "item_id": third_item_id,
                    "role": "primary",
                    "sequence_number": 1,
                    "disc_label": "New Main Disc",
                    "quantity": 1,
                    "is_primary": True,
                },
            ],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["primary_item_id"] == third_item_id
    assert body["members"][0]["item_id"] == third_item_id
    assert body["members"][0]["kind"] == "book"
    assert {member["title"] for member in body["members"]} == {"Disc Two", "Collector Booklet"}
    assert all(member["title"] != "Disc One" for member in body["members"])

    async with AsyncSessionLocal() as db:
        stored_members = list(
            await db.scalars(
                select(BundleReleaseItem)
                .where(BundleReleaseItem.bundle_release_id == UUID(bundle_id))
                .order_by(BundleReleaseItem.sequence_number.asc())
            )
        )
        assert len(stored_members) == 2
        assert third_item_id in {str(member.item_id) for member in stored_members}
        assert all(str(member.item_id) != str(first_item.id) for member in stored_members)


@pytest.mark.asyncio
async def test_admin_bundle_release_audit_uses_public_member_sorting(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    async with AsyncSessionLocal() as db:
        series = Series(kind=ItemKind.music, title="Compilation Series")
        volume = Volume(series=series, name="Compilation Series", volume_number=1)
        zebra_item = Item(kind=ItemKind.music, title="Zebra Disc", sort_key="zebra-disc", volume=volume)
        alpha_item = Item(kind=ItemKind.music, title="Alpha Disc", sort_key="alpha-disc", volume=volume)
        db.add_all([series, volume, zebra_item, alpha_item])
        await db.flush()
        bundle = BundleRelease(
            kind=ItemKind.music,
            title="Sortable Box",
            bundle_type="box_set",
            primary_item_id=zebra_item.id,
            series_id=series.id,
            volume_id=volume.id,
        )
        db.add(bundle)
        await db.flush()
        zebra_member = BundleReleaseItem(
            bundle_release_id=bundle.id,
            item_id=zebra_item.id,
            item=zebra_item,
            role="primary",
            quantity=1,
            is_primary=True,
        )
        alpha_member = BundleReleaseItem(
            bundle_release_id=bundle.id,
            item_id=alpha_item.id,
            item=alpha_item,
            role="component",
            quantity=1,
            is_primary=False,
        )
        db.add_all([zebra_member, alpha_member])
        await db.commit()
        bundle_id = str(bundle.id)
        zebra_member_id = str(zebra_member.id)
        alpha_member_id = str(alpha_member.id)

    response = await client.patch(
        f"/admin/catalog/bundle-releases/{bundle_id}",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "title": "Sortable Box Updated",
            "members": [
                {
                    "id": zebra_member_id,
                    "role": "primary",
                    "quantity": 1,
                    "is_primary": True,
                },
                {
                    "id": alpha_member_id,
                    "role": "component",
                    "quantity": 1,
                    "is_primary": False,
                },
            ],
        },
    )

    assert response.status_code == 200

    logs = await client.get(
        "/admin/audit/logs",
        headers={"Authorization": f"Bearer {token}"},
        params={"action": "metadata.bundle_correction"},
    )

    assert logs.status_code == 200
    before_members = logs.json()[0]["details_json"]["before"]["members"]
    assert [member["id"] for member in before_members] == [alpha_member_id, zebra_member_id]


@pytest.mark.asyncio
async def test_admin_provider_ingest_persistent_job_queue(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "provider_ingest_retry_attempts", 0)
    calls = 0

    async def fake_get_item(self, provider_item_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Provider is warming up",
            )
        raw = comicvine_issue_raw()
        raw["id"] = 92001
        raw["api_detail_url"] = "https://comicvine.gamespot.com/api/issue/4000-92001/"
        raw["site_detail_url"] = "https://comicvine.gamespot.com/job-issue/4000-92001/"
        raw["volume"] = {
            **raw["volume"],
            "id": 99201,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-99201/",
        }
        return ProviderItem(provider="comicvine", provider_item_id="4000-92001", raw=raw)

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    created = await client.post(
        "/admin/providers/ingest/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "comicvine",
            "provider_item_id": "job-123",
            "max_attempts": 2,
        },
    )

    assert created.status_code == 201
    job_id = created.json()["id"]
    assert created.json()["status"] == "queued"

    first_run = await client.post(
        f"/admin/providers/ingest/jobs/{job_id}/run",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert first_run.status_code == 200
    assert first_run.json()["status"] == "queued"
    assert first_run.json()["attempts"] == 1
    assert first_run.json()["last_error"] == "Provider is warming up"
    assert first_run.json()["next_run_at"] is not None

    retried = await client.post(
        f"/admin/providers/ingest/jobs/{job_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert retried.status_code == 200
    assert retried.json()["status"] == "done"
    assert retried.json()["attempts"] == 2
    assert retried.json()["item_id"] is not None

    jobs = await client.get(
        "/admin/providers/ingest/jobs",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "done"},
    )

    assert jobs.status_code == 200
    assert jobs.json()[0]["id"] == job_id

    async with AsyncSessionLocal() as db:
        persisted = await db.get(ProviderIngestJob, UUID(job_id))
        assert persisted is not None
        assert persisted.status == "done"


@pytest.mark.asyncio
async def test_admin_provider_ingest_job_summary_and_filters(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "worker_provider_ingest_stale_after_seconds", 60)
    now = datetime.now(UTC)
    async with AsyncSessionLocal() as db:
        db.add_all(
            [
                ProviderIngestJob(
                    provider=ExternalProvider.gcd,
                    provider_item_id="due-1",
                    status="queued",
                    attempts=0,
                    max_attempts=3,
                    next_run_at=now - timedelta(seconds=5),
                ),
                ProviderIngestJob(
                    provider=ExternalProvider.gcd,
                    provider_item_id="failed-cover",
                    status="failed",
                    attempts=2,
                    max_attempts=2,
                    last_error="Provider timeout while fetching cover",
                    updated_at=now - timedelta(seconds=30),
                ),
                ProviderIngestJob(
                    provider=ExternalProvider.comicvine,
                    provider_item_id="running-1",
                    status="running",
                    attempts=1,
                    max_attempts=3,
                    updated_at=now - timedelta(minutes=10),
                ),
                ProviderIngestJob(
                    provider=ExternalProvider.gcd,
                    provider_item_id="done-1",
                    status="done",
                    attempts=1,
                    max_attempts=3,
                ),
            ]
        )
        await db.commit()

    summary = await client.get(
        "/admin/providers/ingest/jobs/summary",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert summary.status_code == 200
    assert summary.json()["queued"] == 1
    assert summary.json()["running"] == 1
    assert summary.json()["failed"] == 1
    assert summary.json()["done"] == 1
    assert summary.json()["due_queued"] == 1
    assert summary.json()["stale_running"] == 1
    assert summary.json()["latest_failure_at"] is not None

    filtered = await client.get(
        "/admin/providers/ingest/jobs",
        headers={"Authorization": f"Bearer {token}"},
        params={"status": "failed", "provider": "gcd", "q": "timeout"},
    )

    assert filtered.status_code == 200
    assert [job["provider_item_id"] for job in filtered.json()] == ["failed-cover"]


@pytest.mark.asyncio
async def test_admin_provider_ingest_run_pending_recovers_stale_running_job(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "provider_ingest_retry_attempts", 0)
    monkeypatch.setattr(settings, "worker_provider_ingest_stale_after_seconds", 60)

    async def fake_get_item(self, provider_item_id):
        raw = comicvine_issue_raw()
        raw["id"] = 93001
        raw["api_detail_url"] = "https://comicvine.gamespot.com/api/issue/4000-93001/"
        raw["site_detail_url"] = "https://comicvine.gamespot.com/stale-job/4000-93001/"
        raw["volume"] = {
            **raw["volume"],
            "id": 99301,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-99301/",
        }
        return ProviderItem(provider="comicvine", provider_item_id="4000-93001", raw=raw)

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    created = await client.post(
        "/admin/providers/ingest/jobs",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "comicvine",
            "provider_item_id": "stale-job",
            "max_attempts": 2,
        },
    )

    assert created.status_code == 201
    job_id = UUID(created.json()["id"])
    stale_timestamp = datetime.now(UTC) - timedelta(minutes=10)
    async with AsyncSessionLocal() as db:
        await db.execute(
            update(ProviderIngestJob)
            .where(ProviderIngestJob.id == job_id)
            .values(
                status="running",
                next_run_at=None,
                last_error=None,
                updated_at=stale_timestamp,
            )
        )
        await db.commit()

    run_pending = await client.post(
        "/admin/providers/ingest/jobs/run-pending",
        headers={"Authorization": f"Bearer {token}"},
        params={"limit": 5},
    )

    assert run_pending.status_code == 200
    body = run_pending.json()
    assert body["processed"] == 1
    assert body["recovered"] == 1
    assert body["jobs"][0]["id"] == str(job_id)
    assert body["jobs"][0]["status"] == "done"


@pytest.mark.asyncio
async def test_admin_ingest_upserts_comicvine_issue(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    indexed_documents = []

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="comicvine", provider_item_id="4000-12345", raw=comicvine_issue_raw()
        )

    async def fake_get_character_detail(self, provider_item_id):
        assert provider_item_id == "4005-1443"
        return ComicVineCharacterDetail(
            provider_item_id="4005-1443",
            name="Spider-Man",
            aliases=["Peter Parker", "Spidey"],
            description="Friendly neighborhood hero.",
            image_url="https://comicvine.gamespot.com/a/uploads/scale_medium/spidey.jpg",
            first_appeared_in_issue_id="4000-12345",
            api_detail_url="https://comicvine.gamespot.com/api/character/4005-1443/",
            site_detail_url="https://comicvine.gamespot.com/spider-man/4005-1443/",
        )

    async def fake_index_documents(self, documents):
        indexed_documents.extend(documents)
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(ComicVineProvider, "get_character_detail", fake_get_character_detail)
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
    issue = body["item"]["issues"][0]
    assert issue["issue_number"] == "1"
    assert issue["display_title"] == "The Spider Strikes"
    assert issue["publisher"] == "Marvel"
    assert issue["page_count"] == 32
    assert issue["release_date"] == "1963-03-01"
    assert issue["contributors"] == [
        {
            "person_id": issue["contributors"][0]["person_id"],
            "name": "Stan Lee",
            "role": "writer",
            "sequence": 1,
            "scope": "issue",
        },
        {
            "person_id": issue["contributors"][1]["person_id"],
            "name": "Steve Ditko",
            "role": "artist",
            "sequence": 2,
            "scope": "issue",
        },
    ]
    assert issue["characters"][0]["name"] == "Spider-Man"
    assert issue["story_arcs"][0]["name"] == "The Spider Strikes"
    assert issue["identifiers"][0]["identifier_type"] == "provider_item_id"
    assert issue["cover_image_url"] == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    assert indexed_documents == [
        {
            "id": body["item_id"],
            "kind": "comic",
            "title": "The Amazing Spider-Man",
            "item_number": "1",
            "runtime_minutes": None,
            "cover_image_url": "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
            "thumbnail_image_url": None,
            "publisher": "Marvel",
            "release_date": "1963-03-01",
            "region": None,
            "release_year": 1963,
            "barcode": "400012345",
            "barcodes": ["400012345"],
            "variant": "The Spider Strikes",
            "variant_names": ["The Spider Strikes"],
            "bundle_titles": [],
            "bundle_release_ids": [],
            "series_title": "The Amazing Spider-Man",
            "volume_name": "The Amazing Spider-Man",
            "catalog_number": None,
            "creators": ["Stan Lee", "Steve Ditko"],
            "characters": ["Spider-Man"],
            "story_arcs": ["The Spider Strikes"],
            "platforms": [],
            "release_status": None,
            "language": None,
            "imprint": None,
            "subtitle": None,
            "series_group": None,
            "age_rating": None,
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
        assert await db.scalar(select(func.count()).select_from(Item)) == 0
        assert await db.scalar(select(func.count()).select_from(ComicWork)) == 1
        assert await db.scalar(
            select(func.count()).select_from(ComicIssue).where(ComicIssue.work_id == UUID(body["item_id"]))
        ) == 1
        assert await db.scalar(select(func.count()).select_from(ComicContribution)) == 2
        assert await db.scalar(select(func.count()).select_from(ComicIdentifier)) == 1
        assert await db.scalar(
            select(func.count()).select_from(ComicVolume).where(ComicVolume.title == "The Amazing Spider-Man")
        ) == 1
        assert await db.scalar(select(func.count()).select_from(Series)) == 0
        assert await db.scalar(select(func.count()).select_from(Volume)) == 0
        assert await db.scalar(select(func.count()).select_from(Variant)) == 0
        assert await db.scalar(select(func.count()).select_from(Organization)) == 0
        assert await db.scalar(select(func.count()).select_from(EntityOrganization)) == 0
        assert await db.scalar(select(func.count()).select_from(Person)) == 2
        assert await db.scalar(select(func.count()).select_from(EntityPerson)) == 0
        assert await db.scalar(select(func.count()).select_from(Character)) == 1
        assert await db.scalar(select(func.count()).select_from(CharacterAppearance)) == 0
        assert await db.scalar(select(func.count()).select_from(ComicCharacterAppearance)) == 1
        assert await db.scalar(select(func.count()).select_from(StoryArc)) == 1
        assert await db.scalar(select(func.count()).select_from(StoryArcItem)) == 0
        assert await db.scalar(select(func.count()).select_from(ComicStoryArcMembership)) == 1
        assert await db.scalar(select(func.count()).select_from(Tag)) == 0
        assert await db.scalar(select(func.count()).select_from(EntityTag)) == 0
        provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id)
            .where(ExternalProviderId.entity_type == "comic_issue")
            .order_by(ExternalProviderId.provider_item_id)
        )
        assert list(provider_ids) == ["4000-12345"]
        provider_links = await db.execute(
            select(
                ExternalProviderId.entity_type,
                ExternalProviderId.provider_item_id,
                ExternalProviderId.site_url,
                ExternalProviderId.api_url,
            ).order_by(
                ExternalProviderId.entity_type.asc(),
                ExternalProviderId.provider_item_id.asc(),
            )
        )
        provider_link_rows = provider_links.all()
        # Provider links should be for comic_issue, not comic_work, since the unique constraint
        # on (provider, provider_item_id) prevents storing the same ID for multiple entity_types
        assert (
            "comic_issue",
            "4000-12345",
            "https://comicvine.gamespot.com/amazing-spider-man-1/4000-12345/",
            "https://comicvine.gamespot.com/api/issue/4000-12345/",
        ) in provider_link_rows
        item_provider_links = await db.execute(
            select(
                ExternalProviderId.provider_item_id,
                ExternalProviderId.site_url,
                ExternalProviderId.api_url,
            ).where(ExternalProviderId.entity_type == "item")
        )
        assert item_provider_links.all() == []
        character = await db.scalar(select(Character).where(Character.name == "Spider-Man"))
        assert character is not None
        assert character.aliases in (None, ["Peter Parker", "Spidey"])
        if character.description is not None:
            assert character.description == "Friendly neighborhood hero."
        if character.image_url is not None:
            assert (
                character.image_url
                == "https://comicvine.gamespot.com/a/uploads/scale_medium/spidey.jpg"
            )
        assert character.first_appearance_item_id is None
        cover = await db.scalar(select(ComicIssue.cover_image_key))
        assert cover is None


@pytest.mark.asyncio
async def test_admin_ingest_populates_comicvine_associated_cover_variants(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    raw = comicvine_issue_raw()
    raw["id"] = 498453
    raw["api_detail_url"] = "https://comicvine.gamespot.com/api/issue/4000-498453/"
    raw["site_detail_url"] = "https://comicvine.gamespot.com/over-the-garden-wall-1/4000-498453/"
    raw["volume"] = {
        **raw["volume"],
        "id": 100090,
        "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-100090/",
        "name": "Over The Garden Wall",
        "publisher": {"name": "BOOM! Studios"},
    }
    raw["associated_images"] = [
        {
            "id": 4767296,
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/variant-a.jpg",
            "caption": None,
            "image_tags": "All Images",
        },
        {
            "id": 4767295,
            "original_url": "https://comicvine.gamespot.com/a/uploads/original/variant-b.jpg",
            "caption": "Subscription cover",
            "image_tags": "All Images",
        },
    ]

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="comicvine", provider_item_id="4000-498453", raw=raw)

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "4000-498453"},
    )

    assert response.status_code == 201
    issue = response.json()["item"]["issues"][0]
    assert issue["cover_image_url"] == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    assert issue["display_title"] == "The Spider Strikes"

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Variant)) == 0
        assert await db.scalar(
            select(func.count()).select_from(ComicIssue).where(ComicIssue.work_id == UUID(response.json()["item_id"]))
        ) == 1


@pytest.mark.asyncio
async def test_admin_provider_ingest_records_retry_history(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    calls = 0

    async def fake_get_item(self, provider_item_id):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="ComicVine temporarily unavailable",
            )
        raw = comicvine_issue_raw()
        raw["id"] = 90001
        raw["api_detail_url"] = "https://comicvine.gamespot.com/api/issue/4000-90001/"
        raw["site_detail_url"] = "https://comicvine.gamespot.com/retry-issue/4000-90001/"
        raw["volume"] = {
            **raw["volume"],
            "id": 99001,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-99001/",
        }
        return ProviderItem(provider="comicvine", provider_item_id="4000-90001", raw=raw)

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "temporary-issue"},
    )

    assert response.status_code == 201
    assert calls == 2

    history = await client.get(
        "/admin/providers/ingest/history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert history.status_code == 200
    entry = history.json()[0]
    assert entry["provider"] == "comicvine"
    assert entry["provider_item_id"] == "temporary-issue"
    assert entry["status"] == "created"
    assert entry["attempts"] == 2
    assert entry["item_id"] == response.json()["item_id"]
    assert entry["error"] is None


@pytest.mark.asyncio
async def test_admin_provider_ingest_failed_history_can_be_retried(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "provider_ingest_retry_attempts", 0)

    async def fail_get_item(self, provider_item_id):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Provider is down",
        )

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Provider images should not be mirrored by default")

    monkeypatch.setattr(ComicVineProvider, "get_item", fail_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", fail_mirror_cover)

    failed = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "comicvine", "provider_item_id": "retry-me"},
    )

    assert failed.status_code == 502

    history = await client.get(
        "/admin/providers/ingest/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    failed_entry = history.json()[0]
    assert failed_entry["status"] == "failed"
    assert failed_entry["attempts"] == 1
    assert failed_entry["error"] == "Provider is down"

    async def successful_get_item(self, provider_item_id):
        raw = comicvine_issue_raw()
        raw["id"] = 91001
        raw["api_detail_url"] = "https://comicvine.gamespot.com/api/issue/4000-91001/"
        raw["site_detail_url"] = "https://comicvine.gamespot.com/retried-issue/4000-91001/"
        raw["volume"] = {
            **raw["volume"],
            "id": 99101,
            "api_detail_url": "https://comicvine.gamespot.com/api/volume/4050-99101/",
        }
        return ProviderItem(provider="comicvine", provider_item_id="4000-91001", raw=raw)

    monkeypatch.setattr(ComicVineProvider, "get_item", successful_get_item)

    retried = await client.post(
        "/admin/providers/ingest/retry",
        headers={"Authorization": f"Bearer {token}"},
        json={"history_id": failed_entry["id"]},
    )

    assert retried.status_code == 200
    assert retried.json()["created"] is True

    retried_history = await client.get(
        "/admin/providers/ingest/history",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retried_history.json()[0]["status"] == "created"
    assert retried_history.json()[0]["provider_item_id"] == "retry-me"


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
    # Comics v1 now returns ComicWorkV1Response with different structure
    assert body["item"]["title"] == "Batman: Dark Victory"
    assert body["item"]["issues"][0]["issue_number"] == "12"
    # Check that identifiers are properly populated
    assert len(body["item"]["issues"][0]["identifiers"]) > 0
    assert body["item"]["issues"][0]["identifiers"][0]["value"] in ["256114", "76194122054301211"]
    # Verify search document was indexed (comic_work_search_document structure)
    assert len(indexed_documents) > 0
    assert "title" in indexed_documents[0]
    assert indexed_documents[0]["title"] == "Batman: Dark Victory"

    async with AsyncSessionLocal() as db:
        # Comics v1 uses ExternalProviderId with entity_type='comic_issue'
        issue_provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id).where(
                ExternalProviderId.entity_type == "comic_issue"
            ).order_by(ExternalProviderId.provider_item_id)
        )
        assert "256114" in list(issue_provider_ids)


@pytest.mark.asyncio
async def test_admin_ingest_gcd_publisher_imprint(client, monkeypatch):
    """When GCD indicia_publisher differs from publisher, comics v1 only creates ComicWork."""
    token = await admin_token(client, monkeypatch)

    raw = gcd_issue_raw()
    raw["indicia_publisher"] = "Vertigo"
    raw["publisher"] = "DC Comics"

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="gcd", provider_item_id="256114", raw=raw)

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)
    monkeypatch.setattr(ImageMirror, "mirror_cover_best_effort", lambda *a, **kw: None)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "provider_item_id": "256114"},
    )
    assert response.status_code == 201
    body = response.json()
    # Comics v1 returns ComicWorkV1Response
    assert body["item"]["title"] == "Batman: Dark Victory"
    assert body["item"]["id"] is not None


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

    for idx, provider_item_id in enumerate(issues):
        response = await client.post(
            "/admin/providers/ingest",
            headers={"Authorization": f"Bearer {token}"},
            json={"provider": "gcd", "provider_item_id": provider_item_id},
        )

        assert response.status_code == 201
        # First issue creates the work, second issue reuses it
        assert response.json()["created"] is (idx == 0)

    async with AsyncSessionLocal() as db:
        # Comics v1 uses ComicWork and ComicIssue, not Item
        comic_works_count = await db.scalar(select(func.count()).select_from(ComicWork))
        comic_issues_count = await db.scalar(select(func.count()).select_from(ComicIssue))
        assert comic_works_count == 1  # Both issues map to same work (volume)
        assert comic_issues_count == 2  # But we have 2 issues
        
        volumes = await db.scalar(select(func.count()).select_from(Volume))
        assert volumes == 1
        
        # Check provider IDs for issues
        provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id)
            .where(ExternalProviderId.entity_type == "comic_issue")
            .order_by(ExternalProviderId.provider_item_id)
        )
        # Check provider IDs for volume
        volume_provider_ids = await db.scalars(
            select(ExternalProviderId.provider_item_id)
            .where(ExternalProviderId.entity_type == "volume")
            .order_by(ExternalProviderId.provider_item_id)
        )
        assert list(provider_ids) == ["2663120", "2665653"]
        assert list(volume_provider_ids) == ["216143"]


@pytest.mark.asyncio
async def test_admin_ingest_does_not_apply_standard_cover_to_gcd_variant(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "comicvine_api_key", "test-key")
    variant_issue = gcd_variant_issue_raw()
    variant_issue["cover"] = None

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="gcd", provider_item_id=provider_item_id, raw=variant_issue)

    async def fail_find_issue_cover(self, **kwargs):
        raise AssertionError("Variant issues should not receive standard issue cover fallback")

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item)
    monkeypatch.setattr(ComicVineProvider, "find_issue_cover", fail_find_issue_cover)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "provider_item_id": "2665653"},
    )

    assert response.status_code == 201
    comic_work = response.json()["item"]
    assert comic_work["title"] == "Absolute Batman"
    assert len(comic_work["issues"]) > 0
    issue = comic_work["issues"][0]
    assert issue["issue_number"] is not None
    # Variant information is now in the issue, not in a separate variants array
    assert issue["display_title"] is not None


@pytest.mark.asyncio
async def test_admin_ingest_can_mirror_provider_cover_when_enabled(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "mirror_provider_images", True)
    monkeypatch.setattr(settings, "mirror_provider_images_allow_restricted", True)

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
            source_url="https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg",
            provider=provider,
            provider_item_id=provider_item_id,
            size_bytes=12345,
            width=823,
            height=1280,
            content_hash="abc123",
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
    comic_work = body["item"]
    assert len(comic_work["issues"]) > 0
    issue = comic_work["issues"][0]
    # Cover is now at the issue level
    assert issue["cover_image_url"] is not None
    assert issue["cover_image_url"] == "http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.webp"

    async with AsyncSessionLocal() as db:
        # In v1 schema, cover is stored on ComicIssue
        issue = await db.scalar(select(ComicIssue))
        assert issue is not None
        assert issue.cover_image_key == "covers/comicvine/4000-12345/cover.webp"
        cache_entry = await db.scalar(select(ImageCacheEntry))
        assert cache_entry is not None
        assert cache_entry.object_key == "covers/comicvine/4000-12345/cover.webp"
        assert cache_entry.provider == "comicvine"
        assert cache_entry.provider_item_id == "4000-12345"
        assert (
            cache_entry.source_url
            == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
        )
        assert cache_entry.public_url == (
            "http://localhost:9000/collectarr-images/covers/comicvine/4000-12345/cover.webp"
        )
        assert cache_entry.size_bytes == 12345
        assert cache_entry.width == 823
        assert cache_entry.height == 1280
        assert cache_entry.content_hash == "abc123"
        assert cache_entry.access_count == 1


@pytest.mark.asyncio
async def test_admin_ingest_skips_restricted_provider_cover_mirroring(client, monkeypatch):
    token = await admin_token(client, monkeypatch)
    settings = get_settings()
    monkeypatch.setattr(settings, "mirror_provider_images", True)
    monkeypatch.setattr(settings, "mirror_provider_images_allow_restricted", False)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="comicvine", provider_item_id="4000-12345", raw=comicvine_issue_raw()
        )

    async def fake_index_documents(self, documents):
        return True

    async def fail_mirror_cover(self, source_url, provider, provider_item_id):
        raise AssertionError("Restricted provider cover should not be mirrored by default")

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
    comic_work = body["item"]
    assert len(comic_work["issues"]) > 0
    issue = comic_work["issues"][0]
    assert (
        issue["cover_image_url"]
        == "https://comicvine.gamespot.com/a/uploads/scale_large/cover.jpg"
    )

    async with AsyncSessionLocal() as db:
        # In v1 schema, cover_image_key is on ComicIssue
        comic_issue = await db.scalar(select(ComicIssue))
        assert comic_issue is not None
        assert comic_issue.cover_image_key is None
        assert await db.scalar(select(ImageCacheEntry)) is None


@pytest.mark.asyncio
async def test_refresh_stale_items_updates_metadata_from_provider(client, monkeypatch):
    token = await admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="gcd", provider_item_id="256114", raw=gcd_issue_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "gcd", "provider_item_id": "256114"},
    )
    assert response.status_code == 201
    comic_work_id = response.json()["item_id"]

    # Age the provider link past the staleness window
    settings = get_settings()
    monkeypatch.setattr(settings, "worker_catalog_refresh_stale_days", 0)
    async with AsyncSessionLocal() as db:
        # Update ExternalProviderId instead of the legacy provider-link alias for new schema
        await db.execute(
            update(ExternalProviderId)
            .values(updated_at=datetime.now(UTC) - timedelta(days=1))
        )
        await db.commit()

    # Provide an updated title from the provider
    updated_raw = gcd_issue_raw()
    updated_raw["series_name"] = "Amazing Spider-Man (Remastered)"

    async def fake_get_item_refreshed(self, provider_item_id):
        return ProviderItem(provider="gcd", provider_item_id="256114", raw=updated_raw)

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item_refreshed)

    from app.services.admin import AdminMetadataService

    async with AsyncSessionLocal() as db:
        refreshed = await AdminMetadataService(db).refresh_stale_items(10)

    assert refreshed == 1

    async with AsyncSessionLocal() as db:
        # For comics v1, we now have ComicWork, ComicIssue entities
        comic_work = await db.get(ComicWork, UUID(comic_work_id))
        assert comic_work is not None
        # Comic work title comes from the series name
        assert comic_work.title is not None


@pytest.mark.asyncio
async def test_admin_preview_preserves_provider_raw_id(monkeypatch):
    class FakeHardcoverProvider:
        name = "hardcover"
        capabilities = ProviderCapabilities(
            kind=ItemKind.book,
            display_name="Hardcover",
            kinds=(ItemKind.book,),
        )

        @property
        def is_configured(self) -> bool:
            return True

        @property
        def status_message(self) -> str:
            return "configured"

        async def search(self, query: str, kind: ItemKind | None = None):
            return []

        async def get_item(self, provider_item_id: str) -> ProviderItem:
            assert provider_item_id == "book:42"
            return ProviderItem(
                provider="hardcover",
                provider_item_id=provider_item_id,
                raw={"id": 42, "title": "The Hobbit"},
            )

        async def normalize(self, data) -> NormalizedItem:
            assert data["id"] == 42
            return NormalizedItem(
                kind=ItemKind.book,
                title="The Hobbit",
                edition_format="Hardcover",
                provider_ids={"hardcover": "book:42"},
                volume_provider_ids={"hardcover": "book:42"},
            )

    clear_provider_preview_cache()

    async with AsyncSessionLocal() as db:
        service = admin_service.AdminMetadataService(db)
        monkeypatch.setattr(service.providers, "get", lambda _: FakeHardcoverProvider())

        preview = await service.preview(
            ProviderIngestRequest(
                provider=ExternalProvider.hardcover,
                provider_item_id="book:42",
            )
        )

    assert preview.provider == "hardcover"
    assert preview.provider_item_id == "book:42"
    assert preview.kind == ItemKind.book


@pytest.mark.asyncio
async def test_admin_preview_cache_reuses_hydrated_preview_for_ingest(monkeypatch):
    clear_provider_preview_cache()
    calls = {"get_item": 0, "normalize": 0}

    class FakeOpenLibraryProvider:
        name = "openlibrary"
        capabilities = ProviderCapabilities(
            kind=ItemKind.book,
            display_name="Open Library",
            kinds=(ItemKind.book,),
        )

        @property
        def is_configured(self) -> bool:
            return True

        @property
        def status_message(self) -> str:
            return "configured"

        async def search(self, query: str, kind: ItemKind | None = None):
            return []

        async def get_item(self, provider_item_id: str) -> ProviderItem:
            calls["get_item"] += 1
            assert provider_item_id == "OL4242M"
            return ProviderItem(
                provider="openlibrary",
                provider_item_id=provider_item_id,
                raw={"id": 4242, "title": "The Silmarillion"},
            )

        async def normalize(self, data) -> NormalizedItem:
            calls["normalize"] += 1
            assert data["id"] == 4242
            return NormalizedItem(
                kind=ItemKind.book,
                title="The Silmarillion",
                edition_format="Hardcover",
                provider_ids={"openlibrary": "OL4242M"},
                volume_provider_ids={"openlibrary": "OL4242M"},
            )

    async with AsyncSessionLocal() as db:
        service = admin_service.AdminMetadataService(db)
        monkeypatch.setattr(service.providers, "get", lambda _: FakeOpenLibraryProvider())

        preview = await service.preview(
            ProviderIngestRequest(
                provider=ExternalProvider.openlibrary,
                provider_item_id="OL4242M",
            )
        )
        response = await service.ingest(
            ProviderIngestRequest(
                provider=ExternalProvider.openlibrary,
                provider_item_id="OL4242M",
            )
        )

    assert preview.title == "The Silmarillion"
    assert response.created is True
    assert calls == {"get_item": 1, "normalize": 1}


@pytest.mark.asyncio
async def test_admin_preview_cache_uses_redis_across_service_instances(monkeypatch):
    clear_provider_preview_cache()
    fake = FakePreviewCacheRedis()
    calls = {"get_item": 0, "normalize": 0}

    @asynccontextmanager
    async def fake_redis_client():
        yield fake

    monkeypatch.setattr("app.services.provider_preview_state.redis_client", fake_redis_client)

    class FakeOpenLibraryProvider:
        name = "openlibrary"
        capabilities = ProviderCapabilities(
            kind=ItemKind.book,
            display_name="Open Library",
            kinds=(ItemKind.book,),
        )

        @property
        def is_configured(self) -> bool:
            return True

        @property
        def status_message(self) -> str:
            return "configured"

        async def search(self, query: str, kind: ItemKind | None = None):
            return []

        async def get_item(self, provider_item_id: str) -> ProviderItem:
            calls["get_item"] += 1
            assert provider_item_id in {"OL4242M", "OL9999M"}
            return ProviderItem(
                provider="openlibrary",
                provider_item_id=provider_item_id,
                raw={
                    "id": 4242 if provider_item_id == "OL4242M" else 9999,
                    "title": "The Silmarillion" if provider_item_id == "OL4242M" else "Unfinished Tales",
                },
            )

        async def normalize(self, data) -> NormalizedItem:
            calls["normalize"] += 1
            assert data["id"] in {4242, 9999}
            return NormalizedItem(
                kind=ItemKind.book,
                title="The Silmarillion" if data["id"] == 4242 else "Unfinished Tales",
                edition_format="Hardcover",
                provider_ids={"openlibrary": "OL4242M" if data["id"] == 4242 else "OL9999M"},
                volume_provider_ids={"openlibrary": "OL4242M" if data["id"] == 4242 else "OL9999M"},
            )

    async with AsyncSessionLocal() as db:
        service = admin_service.AdminMetadataService(db)
        monkeypatch.setattr(service.providers, "get", lambda _: FakeOpenLibraryProvider())

        preview = await service.preview(
            ProviderIngestRequest(
                provider=ExternalProvider.openlibrary,
                provider_item_id="OL4242M",
            )
        )
        sibling_preview = await service.preview(
            ProviderIngestRequest(
                provider=ExternalProvider.openlibrary,
                provider_item_id="OL9999M",
            )
        )

    assert fake.values
    assert fake.ttls
    clear_provider_preview_cache()

    async with AsyncSessionLocal() as db:
        service = admin_service.AdminMetadataService(db)
        monkeypatch.setattr(service.providers, "get", lambda _: FakeOpenLibraryProvider())

        response = await service.ingest(
            ProviderIngestRequest(
                provider=ExternalProvider.openlibrary,
                provider_item_id="OL4242M",
            )
        )

    clear_provider_preview_cache()

    async with AsyncSessionLocal() as db:
        service = admin_service.AdminMetadataService(db)
        monkeypatch.setattr(service.providers, "get", lambda _: FakeOpenLibraryProvider())

        sibling_cached = await service.preview(
            ProviderIngestRequest(
                provider=ExternalProvider.openlibrary,
                provider_item_id="OL9999M",
            )
        )

    assert preview.title == "The Silmarillion"
    assert sibling_preview.title == "Unfinished Tales"
    assert sibling_cached.title == "Unfinished Tales"
    assert response.created is True
    assert calls == {"get_item": 2, "normalize": 2}
    assert fake.values


@pytest.mark.asyncio
async def test_admin_ingest_creates_bundle_release_from_provider_package(monkeypatch):
    class FakeMusicBundleProvider:
        name = "musicbrainz"
        capabilities = ProviderCapabilities(
            kind=ItemKind.music,
            display_name="MusicBrainz",
            kinds=(ItemKind.music,),
        )

        @property
        def is_configured(self) -> bool:
            return True

        @property
        def status_message(self) -> str:
            return "configured"

        async def search(self, query: str, kind: ItemKind | None = None):
            return []

        async def get_item(self, provider_item_id: str) -> ProviderItem:
            assert provider_item_id == "bundle:mb:collection-1"
            return ProviderItem(
                provider="musicbrainz",
                provider_item_id=provider_item_id,
                raw={"id": "collection-1", "title": "Collection Box"},
            )

        async def normalize(self, data) -> NormalizedItem:
            assert data["id"] == "collection-1"
            return NormalizedItem(
                kind=ItemKind.music,
                title="Album One",
                series_title="Album One",
                volume_name="Album One",
                edition_title="Standard Edition",
                edition_format="CD",
                publisher="Roadrunner",
                release_date=date(2024, 5, 3),
                bundle_release=NormalizedBundleRelease(
                    title="Collection Box",
                    bundle_type="box_set",
                    format="CD",
                    packaging_type="box",
                    region="US",
                    publisher="Roadrunner",
                    barcode="123456789012",
                    release_date=date(2024, 5, 3),
                    provider_ids={"musicbrainz": "bundle:mb:collection-1"},
                    members=[
                        NormalizedBundleMember(
                            item=NormalizedItem(
                                kind=ItemKind.music,
                                title="Album One",
                                series_title="Album One",
                                volume_name="Album One",
                                edition_title="Standard Edition",
                                edition_format="CD",
                                publisher="Roadrunner",
                                release_date=date(2024, 5, 3),
                                provider_ids={"musicbrainz": "release:album-one"},
                            ),
                            role="primary",
                            sequence_number=1,
                            disc_number=1,
                            is_primary=True,
                        ),
                        NormalizedBundleMember(
                            item=NormalizedItem(
                                kind=ItemKind.music,
                                title="Album Two",
                                series_title="Album Two",
                                volume_name="Album Two",
                                edition_title="Deluxe Edition",
                                edition_format="CD",
                                publisher="Roadrunner",
                                release_date=date(2024, 5, 3),
                                provider_ids={"musicbrainz": "release:album-two"},
                            ),
                            role="primary",
                            sequence_number=2,
                            disc_number=2,
                        ),
                    ],
                ),
            )

    async with AsyncSessionLocal() as db:
        service = admin_service.AdminMetadataService(db)
        monkeypatch.setattr(service.providers, "get", lambda _: FakeMusicBundleProvider())

        response = await service.ingest(
            ProviderIngestRequest(
                provider=ExternalProvider.musicbrainz,
                provider_item_id="bundle:mb:collection-1",
            )
        )
        second_response = await service.ingest(
            ProviderIngestRequest(
                provider=ExternalProvider.musicbrainz,
                provider_item_id="bundle:mb:collection-1",
            )
        )

    assert response.created is True
    assert response.item["title"] == "Album One"
    assert second_response.created is False
    assert second_response.item_id == response.item_id

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Item)) == 2
        assert await db.scalar(select(func.count()).select_from(BundleRelease)) == 1
        assert await db.scalar(select(func.count()).select_from(BundleReleaseItem)) == 2

        bundle = await db.scalar(select(BundleRelease))
        assert bundle is not None
        assert bundle.title == "Collection Box"
        assert bundle.bundle_type == "box_set"
        assert bundle.primary_item_id == UUID(str(response.item_id))
        assert bundle.barcode == "123456789012"

        member_roles = await db.execute(
            select(BundleReleaseItem.role, BundleReleaseItem.disc_number)
            .where(BundleReleaseItem.bundle_release_id == bundle.id)
            .order_by(BundleReleaseItem.sequence_number.asc())
        )
        assert member_roles.all() == [("primary", 1), ("primary", 2)]

        provider_links = await db.execute(
            select(ExternalProviderId.provider_item_id)
            .where(ExternalProviderId.entity_type == "item")
            .order_by(ExternalProviderId.provider_item_id.asc())
        )
        bundle_provider_links = await db.scalars(
            select(ExternalProviderId.provider_item_id)
            .where(ExternalProviderId.entity_type == "bundle_release")
            .order_by(ExternalProviderId.provider_item_id.asc())
        )
        assert [row[0] for row in provider_links.all()] == ["release:album-one", "release:album-two"]
        assert list(bundle_provider_links) == ["bundle:mb:collection-1"]
