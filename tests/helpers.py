from datetime import date

from app.db.session import AsyncSessionLocal
from app.models import ComicIdentifier, ComicIssue, ComicWork
from app.models.base import ExternalProvider


async def seed_comic() -> tuple[str, str, str]:
    async with AsyncSessionLocal() as db:
        work = ComicWork(
            title="The Amazing Spider-Man",
            sort_title="amazing spider-man",
            description="Peter Parker swings into action.",
            original_language="en",
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
            imprint="Marvel Knights",
            language="en",
            region="US",
            release_status="released",
            cover_image_url="https://cdn.example/standard.jpg",
            description="Peter Parker swings into action.",
        )
        db.add(issue)
        await db.flush()
        db.add(
            ComicIdentifier(
                issue_id=issue.id,
                identifier_type="barcode",
                value="75960604716100111",
                normalized_value="75960604716100111",
                is_primary=True,
                source_provider=ExternalProvider.comicvine,
            )
        )
        await db.commit()
        return str(work.id), str(issue.id), str(issue.id)


async def register_and_login(client) -> str:
    response = await client.post(
        "/auth/register",
        json={"email": "test@example.com", "password": "password123", "display_name": "Test"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]
