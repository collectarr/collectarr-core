import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import ExternalProviderId, Item, Organization, Person
from app.providers.base import ProviderItem
from app.providers.musicbrainz import MusicBrainzProvider
from app.search.client import SearchClient


RELEASE_ID = "f9a4ef2d-b3ac-4d19-8d4e-5db0f35ec028"
GROUP_ID = "6b9a3f23-2b8b-4f7a-9f36-5fb41a315f5c"


async def _admin_token(client, monkeypatch) -> str:
    settings = get_settings()
    monkeypatch.setattr(settings, "bootstrap_admin_emails", {"admin@example.com"})
    response = await client.post(
        "/auth/register",
        json={"email": "admin@example.com", "password": "password123", "display_name": "Admin"},
    )
    assert response.status_code == 201
    return response.json()["access_token"]


def _release_raw() -> dict:
    return {
        "id": RELEASE_ID,
        "title": "Kind of Blue",
        "date": "1959-08-17",
        "country": "US",
        "barcode": "074646493525",
        "status": "Official",
        "disambiguation": "Legacy edition",
        "artist-credit": [
            {
                "name": "Miles Davis",
                "artist": {"id": "561d854a-6a28-4aa7-8c99-323e6ce46c2a", "name": "Miles Davis"},
            }
        ],
        "label-info": [
            {
                "catalog-number": "CK 64935",
                "label": {"id": "7b5b5f7b", "name": "Columbia"},
            }
        ],
        "media": [
            {"format": "CD", "track-count": 5},
            {"format": "CD", "track-count": 6},
        ],
        "release-group": {"id": GROUP_ID, "primary-type": "Album", "title": "Kind of Blue"},
        "cover-art-archive": {"artwork": True, "front": True},
    }


@pytest.mark.asyncio
async def test_musicbrainz_provider_search_normalizes_releases(monkeypatch):
    async def fake_request(self, path, params):
        assert path == "release"
        assert params["query"] == "Kind of Blue"
        assert params["fmt"] == "json"
        return {"releases": [_release_raw()]}

    monkeypatch.setattr(MusicBrainzProvider, "_request", fake_request)

    results = await MusicBrainzProvider().search(" Kind of Blue ")

    assert len(results) == 1
    assert results[0].provider_item_id == RELEASE_ID
    assert results[0].kind == ItemKind.music
    assert results[0].title == "Kind of Blue"
    assert results[0].summary == "Miles Davis · 1959-08-17 · US"
    assert results[0].image_url.endswith(f"/release/{RELEASE_ID}/front-500")


@pytest.mark.asyncio
async def test_musicbrainz_provider_fetches_release_and_normalizes(monkeypatch):
    async def fake_request(self, path, params):
        assert path == f"release/{RELEASE_ID}"
        assert params["inc"] == "artist-credits+labels+release-groups+media"
        return _release_raw()

    monkeypatch.setattr(MusicBrainzProvider, "_request", fake_request)

    item = await MusicBrainzProvider().get_item(RELEASE_ID)
    normalized = await MusicBrainzProvider().normalize(item.raw)

    assert item.provider_item_id == RELEASE_ID
    assert normalized.kind == ItemKind.music
    assert normalized.title == "Kind of Blue"
    assert normalized.publisher == "Columbia"
    assert normalized.release_date.isoformat() == "1959-08-17"
    assert normalized.barcode == "074646493525"
    assert normalized.edition_format == "Album / CD"
    assert normalized.creators[0].name == "Miles Davis"
    assert normalized.provider_ids == {"musicbrainz": RELEASE_ID}
    assert normalized.volume_provider_ids == {"musicbrainz": GROUP_ID}
    assert normalized.track_count == 11
    assert normalized.catalog_number == "CK 64935"
    assert normalized.country == "US"
    assert normalized.release_status == "Official"
    assert normalized.physical_format == "CD"


@pytest.mark.asyncio
async def test_admin_ingest_upserts_musicbrainz_release(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(provider="musicbrainz", provider_item_id=RELEASE_ID, raw=_release_raw())

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(MusicBrainzProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={"provider": "musicbrainz", "provider_item_id": RELEASE_ID},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "music"
    assert body["item"]["title"] == "Kind of Blue"
    assert body["item"]["publisher"] == "Columbia"
    assert body["item"]["barcode"] == "074646493525"

    async with AsyncSessionLocal() as db:
        item = await db.scalar(select(Item).where(Item.kind == ItemKind.music))
        provider_ids = list(
            await db.scalars(
                select(ExternalProviderId.provider_item_id).where(
                    ExternalProviderId.provider == ExternalProvider.musicbrainz
                )
            )
        )
        publisher = await db.scalar(select(Organization.name))
        artist = await db.scalar(select(Person.name))

    assert item is not None
    assert sorted(provider_ids) == sorted([RELEASE_ID, GROUP_ID])
    assert publisher == "Columbia"
    assert artist == "Miles Davis"
