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
