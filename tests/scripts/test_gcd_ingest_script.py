import pytest
from sqlalchemy import func, select

from app.db.session import AsyncSessionLocal
from app.models.base import ItemKind
from app.models.canonical import Item, ItemProviderLink, VolumeProviderLink
from app.providers.base import ProviderItem, ProviderSearchResult
from app.providers.gcd import GCDProvider
from app.scripts import ingest_gcd
from app.search.client import SearchClient


def gcd_issue_raw() -> dict:
    return {
        "api_url": "https://www.comics.org/api/issue/256114/",
        "series_name": "Batman: Dark Victory (1999 series)",
        "descriptor": "12",
        "number": "12",
        "title": "",
        "publication_date": "November 2000",
        "key_date": "2000-11-00",
        "price": "2.95 USD; 4.50 CAD",
        "page_count": "36.000",
        "editing": "Mark Chiarello (editor)",
        "indicia_publisher": "DC Comics",
        "isbn": "",
        "barcode": "76194122054301211",
        "on_sale_date": "2000-09-20",
        "notes": "",
        "variant_of": None,
        "series": "https://www.comics.org/api/series/6139/",
        "story_set": [
            {
                "type": "comic story",
                "title": "Revenge",
                "script": "Jeph Loeb",
                "pencils": "Tim Sale",
                "inks": "Tim Sale",
                "colors": "Gregory Wright (colors); Heroic Age (separations)",
                "letters": "Richard Starkings",
                "editing": "None",
                "characters": "Batman [Bruce Wayne]; Dick Grayson",
                "synopsis": "Two-Face seeks revenge.",
            },
        ],
        "cover": "https://files1.comics.org//img/gcd/covers_by_id/237/w400/237538.jpg",
    }


def test_issue_queries_build_single_and_range():
    assert ingest_gcd.issue_queries("Batman", "12", None, None) == ["Batman #12"]
    assert ingest_gcd.issue_queries("Batman", None, 1, 3) == [
        "Batman #1",
        "Batman #2",
        "Batman #3",
    ]


@pytest.mark.asyncio
async def test_ingest_gcd_dry_run_searches_without_writing(monkeypatch, capsys):
    async def fake_search(self, query, kind=None):
        assert query == "Batman #12"
        return [
            ProviderSearchResult(
                provider="gcd",
                provider_item_id="256114",
                title="Batman: Dark Victory (1999 series) #12",
                kind=ItemKind.comic,
                summary="November 2000 - 2.95 USD - 36 pages",
            )
        ]

    async def fail_get_item(self, provider_item_id):
        raise AssertionError("Dry run should not fetch or ingest provider items")

    def fail_session():
        raise AssertionError("Dry run should not open the database")

    monkeypatch.setattr(GCDProvider, "search", fake_search)
    monkeypatch.setattr(GCDProvider, "get_item", fail_get_item)
    monkeypatch.setattr(ingest_gcd, "AsyncSessionLocal", fail_session)

    args = ingest_gcd.parse_args(["--series", "Batman", "--issue", "12", "--dry-run"])
    exit_code = await ingest_gcd.run_ingest(args)

    assert exit_code == 0
    output = capsys.readouterr().out
    assert "DRY-RUN gcd:256114 Batman: Dark Victory (1999 series) #12" in output


@pytest.mark.asyncio
async def test_ingest_gcd_imports_issue_and_skips_existing(monkeypatch):
    get_item_calls = []
    output = []

    async def fake_get_item(self, provider_item_id):
        get_item_calls.append(provider_item_id)
        return ProviderItem(provider="gcd", provider_item_id="256114", raw=gcd_issue_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(GCDProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    args = ingest_gcd.parse_args(["--provider-item-id", "256114"])
    exit_code = await ingest_gcd.run_ingest(args, output.append)

    assert exit_code == 0
    assert get_item_calls == ["256114"]
    assert output[0].startswith("INGESTED gcd:256114 item_id=")

    skip_args = ingest_gcd.parse_args(["--provider-item-id", "256114", "--skip-existing"])
    skip_exit_code = await ingest_gcd.run_ingest(skip_args, output.append)

    assert skip_exit_code == 0
    assert get_item_calls == ["256114"]
    assert output[-1] == "SKIPPED gcd:256114 already linked"

    async with AsyncSessionLocal() as db:
        assert await db.scalar(select(func.count()).select_from(Item)) == 1
        provider_ids = await db.scalars(
            select(ItemProviderLink.provider_item_id).order_by(
                ItemProviderLink.provider_item_id
            )
        )
        volume_provider_ids = await db.scalars(
            select(VolumeProviderLink.provider_item_id).order_by(
                VolumeProviderLink.provider_item_id
            )
        )
        assert list(provider_ids) == ["256114"]
        assert list(volume_provider_ids) == ["6139"]
