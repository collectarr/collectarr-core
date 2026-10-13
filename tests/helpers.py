from uuid import uuid4

from app.db.session import AsyncSessionLocal
from app.models.catalog_comic_item import ComicItem


async def seed_comic() -> str:
    async with AsyncSessionLocal() as db:
        item = ComicItem(
            title="The Amazing Spider-Man #1",
            sort_key="amazing spider-man 1",
            barcode="75960604716100111",
            details={
                "series_title": "The Amazing Spider-Man",
                "issue_number": "1",
                "publisher": "Marvel",
                "imprint": "Marvel Knights",
                "language": "en",
                "country": "US",
                "release_status": "released",
                "release_date": "1963-03-01",
                "cover_image_url": "https://cdn.example/standard.jpg",
                "description": "Peter Parker swings into action.",
                "identifiers": [
                    {
                        "id": str(uuid4()),
                        "identifier_type": "barcode",
                        "value": "75960604716100111",
                        "normalized_value": "75960604716100111",
                        "is_primary": True,
                    }
                ],
            },
        )
        db.add(item)
        await db.commit()
        return str(item.id)


async def register_and_login(client) -> str:
    response = await client.post(
        "/api/v1/auth/register",
        json={"email": "test@example.com", "password": "password123", "display_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]
