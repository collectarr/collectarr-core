import pytest

from app.db.session import AsyncSessionLocal
from app.services.catalog_comic_items import CatalogComicItemService


@pytest.mark.db
@pytest.mark.asyncio
async def test_comic_create_read_and_search_preserve_publication_fields(client):
    fields = {
        "title": "Isolated comic fixture", "series_title": "Fixture series",
        "issue_number": "1/2", "variant": "B", "variant_description": "Foil",
        "subtitle": "Issue subtitle", "publication_age": "Modern", "age_rating": "Teen",
        "barcode": "0000000000998", "cover_date": {"year": 2024},
        "release_date_parts": {"month": 5, "day": 3},
    }
    async with AsyncSessionLocal() as db:
        item = await CatalogComicItemService(db).create_from_proposal(fields)
        await db.commit()
    read = await client.get(f"/api/v1/metadata/comics/items/{item.id}")
    assert read.status_code == 200, read.text
    for key, value in fields.items():
        assert read.json()[key] == value
    for query in ({"q": "Isolated comic"}, {"barcode": "0000000000998"}):
        search = await client.get('/api/v1/search', params={"kind": "comic", **query})
        assert search.status_code == 200, search.text
        hit = search.json()['items'][0]
        assert hit['id'] == str(item.id)
        for key in ('publication_age', 'variant_description', 'subtitle'):
            assert hit['kind_data'][key] == fields[key]
        assert hit['kind_data']['release_date_parts'] == {
            'year': None, 'month': 5, 'day': 3,
        }


@pytest.mark.db
@pytest.mark.asyncio
async def test_comic_series_list_groups_issues_and_lists_them_in_issue_order(client):
    def issue(series, number, *, publisher="Marvel", volume=2018, variant=None, year=2018, cover=None):
        fields = {"title": f"{series} #{number}{variant or ''}", "series_title": series,
                  "issue_number": number, "release_date_parts": {"year": year}}
        if publisher is not None:
            fields["publisher"] = publisher
        if volume is not None:
            fields["volume_start_year"] = volume
        if variant is not None:
            fields["variant"] = variant
        if cover is not None:
            fields["cover_image_url"] = cover
        return fields

    async with AsyncSessionLocal() as db:
        service = CatalogComicItemService(db)
        for fields in (
            issue("Series Fixture", "10", year=2019),
            issue("Series Fixture", "2", cover="https://covers.test/2.jpg"),
            issue("Series Fixture", "1", cover="https://covers.test/1.jpg"),
            issue("Series Fixture", "2", variant="B"),
            issue("Series Fixture", "1", publisher="Other"),
            issue("Series Fixture", "1", publisher=None, volume=None),
            issue("Series Fixture Annual", "1"),
        ):
            await service.create_from_proposal(fields)
        await db.commit()

    found = await client.get("/api/v1/metadata/comics/series", params={"q": "series fixture"})
    assert found.status_code == 200, found.text
    assert [(row["series_title"], row["publisher"], row["issue_count"]) for row in found.json()] == [
        ("Series Fixture", None, 1),
        ("Series Fixture", "Marvel", 4),
        ("Series Fixture", "Other", 1),
        ("Series Fixture Annual", "Marvel", 1),
    ]
    marvel = found.json()[1]
    assert marvel == {
        "series_title": "Series Fixture", "publisher": "Marvel", "volume_start_year": 2018,
        "first_year": 2018, "last_year": 2019, "issue_count": 4,
        "cover_image_url": "https://covers.test/1.jpg",
    }

    issues = await client.get("/api/v1/metadata/comics/series/issues", params={
        "series_title": "Series Fixture", "publisher": "Marvel", "volume_start_year": 2018,
    })
    assert issues.status_code == 200, issues.text
    assert [row["kind_data"]["title"] for row in issues.json()] == [
        "Series Fixture #1", "Series Fixture #2", "Series Fixture #2B", "Series Fixture #10",
    ]
    unpublished = await client.get("/api/v1/metadata/comics/series/issues", params={"series_title": "Series Fixture"})
    assert [row["kind_data"]["title"] for row in unpublished.json()] == ["Series Fixture #1"]
