from datetime import date

from app.db.session import AsyncSessionLocal
from app.models import Edition, Item, Variant
from app.models.base import ItemKind


async def seed_comic() -> tuple[str, str, str]:
    async with AsyncSessionLocal() as db:
        item = Item(
            kind=ItemKind.comic,
            title="The Amazing Spider-Man",
            item_number="1",
            sort_key="amazing-spider-man-001",
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
        db.add_all([item, edition, variant])
        await db.commit()
        return str(item.id), str(edition.id), str(variant.id)


async def register_and_login(client) -> str:
    response = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "password123", "display_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]
