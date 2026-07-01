from datetime import date

from app.db.session import AsyncSessionLocal
from app.models import Edition, Franchise, Item, Series, Variant, Volume
from app.models.base import ItemKind


async def seed_comic() -> tuple[str, str, str]:
    async with AsyncSessionLocal() as db:
        franchise = Franchise(name="Marvel")
        series = Series(kind=ItemKind.comic, title="The Amazing Spider-Man", franchise=franchise)
        volume = Volume(name="The Amazing Spider-Man (1963)", series=series, volume_number=1)
        item = Item(
            kind=ItemKind.comic,
            title="The Amazing Spider-Man",
            item_number="1",
            sort_key="amazing-spider-man-001",
            volume=volume,
        )
        edition = Edition(
            item=item,
            title="Standard Edition",
            format="Single Issue",
            publisher="Marvel",
            upc="75960604716100111",
            language="en",
            release_date=date(1963, 3, 1),
        )
        variant = Variant(edition=edition, name="Cover A", is_primary=True)
        db.add_all([franchise, series, volume, item, edition, variant])
        await db.commit()
        return str(item.id), str(edition.id), str(variant.id)


async def register_and_login(client) -> str:
    response = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "password123", "display_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]
