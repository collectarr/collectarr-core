import pytest
from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.base import ExternalProvider, ItemKind
from app.models.canonical import BundleRelease, BundleReleaseItem, ExternalProviderId, Item, Organization, Person
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
            {
                "format": "CD",
                "track-count": 5,
                "tracks": [
                    {
                        "position": 1,
                        "title": "So What",
                        "length": 563000,
                        "artist-credit": [
                            {
                                "name": "Miles Davis",
                                "artist": {
                                    "id": "561d854a-6a28-4aa7-8c99-323e6ce46c2a",
                                    "name": "Miles Davis",
                                },
                            }
                        ],
                    },
                    {
                        "position": 2,
                        "title": "Freddie Freeloader",
                        "length": 585000,
                    },
                ],
            },
            {
                "format": "CD",
                "track-count": 6,
                "tracks": [
                    {
                        "position": 1,
                        "title": "Flamenco Sketches",
                        "length": 566000,
                    }
                ],
            },
        ],
        "release-group": {"id": GROUP_ID, "primary-type": "Album", "title": "Kind of Blue"},
        "cover-art-archive": {"artwork": True, "front": True},
    }


def _bundle_release_raw() -> dict:
    return {
        "id": "59211ea4-ffd2-4ad9-9a4e-941d3148024a",
        "title": "ae3o & h3ae",
        "date": "2003-12-04",
        "country": "GB",
        "status": "Official",
        "artist-credit": [
            {
                "name": "Autechre",
                "artist": {"id": "410c9baf-5469-44f6-9852-826524b80c61", "name": "Autechre"},
            },
            {
                "name": "The Hafler Trio",
                "artist": {
                    "id": "146c01d0-d3a2-44c3-acb5-9208bce75e14",
                    "name": "The Hafler Trio",
                },
            },
        ],
        "label-info": [
            {
                "catalog-number": "pgram002",
                "label": {"id": "a0759efa-f583-49ea-9a8d-d5bbce55541c", "name": "Phonometrography"},
            }
        ],
        "media": [
            {
                "position": 1,
                "title": "ae3o",
                "format": "CD",
                "track-count": 1,
                "tracks": [
                    {
                        "position": 1,
                        "title": "ae3o",
                        "length": 974546,
                    }
                ],
            },
            {
                "position": 2,
                "title": "h3ae",
                "format": "CD",
                "track-count": 1,
                "tracks": [
                    {
                        "position": 1,
                        "title": "h3ae",
                        "length": 922546,
                    }
                ],
            },
        ],
        "release-group": {
            "id": "9d127db0-056a-4d7e-a40e-1ef5cd02d695",
            "primary-type": "Album",
            "title": "ae3o & h3ae",
        },
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
        assert params["inc"] == "artist-credits+labels+release-groups+media+recordings"
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
    assert len(normalized.tracks) == 3
    assert normalized.tracks[0].title == "So What"
    assert normalized.tracks[0].duration_seconds == 563
    assert normalized.tracks[0].artist == "Miles Davis"
    assert normalized.tracks[2].disc_number == 2
    assert normalized.catalog_number == "CK 64935"
    assert normalized.country == "US"
    assert normalized.release_status == "Official"
    assert normalized.physical_format == "CD"
    assert normalized.cover_image_url is not None
    assert normalized.cover_image_url.endswith(f"/release/{RELEASE_ID}/front-500")


@pytest.mark.asyncio
async def test_musicbrainz_provider_normalizes_multi_title_release_as_bundle():
    normalized = await MusicBrainzProvider().normalize(_bundle_release_raw())

    assert normalized.bundle_release is not None
    assert normalized.bundle_release.title == "ae3o & h3ae"
    assert normalized.bundle_release.bundle_type == "box_set"
    assert normalized.bundle_release.format == "CD"
    assert normalized.bundle_release.provider_ids == {"musicbrainz": "59211ea4-ffd2-4ad9-9a4e-941d3148024a"}
    assert len(normalized.bundle_release.members) == 2
    assert normalized.bundle_release.members[0].item.title == "ae3o"
    assert normalized.bundle_release.members[0].item.provider_ids == {
        "musicbrainz": "59211ea4-ffd2-4ad9-9a4e-941d3148024a#disc-1"
    }
    assert normalized.bundle_release.members[0].disc_number == 1
    assert normalized.bundle_release.members[0].is_primary is True
    assert normalized.bundle_release.members[1].item.title == "h3ae"
    assert normalized.bundle_release.members[1].disc_number == 2


@pytest.mark.asyncio
async def test_musicbrainz_cover_falls_back_to_release_group(monkeypatch):
    """When the release has no front cover, fall back to release-group cover."""
    raw = _release_raw()
    raw["cover-art-archive"] = {"artwork": False, "front": False}

    async def fake_request(self, path, params):
        return raw

    monkeypatch.setattr(MusicBrainzProvider, "_request", fake_request)

    item = await MusicBrainzProvider().get_item(RELEASE_ID)
    normalized = await MusicBrainzProvider().normalize(item.raw)
    assert normalized.cover_image_url is not None
    assert normalized.cover_image_url.endswith(f"/release-group/{GROUP_ID}/front-500")


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


@pytest.mark.asyncio
async def test_admin_ingest_musicbrainz_bundle_release(client, monkeypatch):
    token = await _admin_token(client, monkeypatch)

    async def fake_get_item(self, provider_item_id):
        return ProviderItem(
            provider="musicbrainz",
            provider_item_id="59211ea4-ffd2-4ad9-9a4e-941d3148024a",
            raw=_bundle_release_raw(),
        )

    async def fake_index_documents(self, documents):
        return True

    monkeypatch.setattr(MusicBrainzProvider, "get_item", fake_get_item)
    monkeypatch.setattr(SearchClient, "index_documents_best_effort", fake_index_documents)

    response = await client.post(
        "/admin/providers/ingest",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "provider": "musicbrainz",
            "provider_item_id": "59211ea4-ffd2-4ad9-9a4e-941d3148024a",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["created"] is True
    assert body["item"]["kind"] == "music"
    assert body["item"]["title"] == "ae3o"

    async with AsyncSessionLocal() as db:
        bundle = await db.scalar(select(BundleRelease))
        bundle_items = list(
            await db.scalars(
                select(BundleReleaseItem).order_by(BundleReleaseItem.sequence_number.asc())
            )
        )
        provider_ids = list(
            await db.scalars(
                select(ExternalProviderId.provider_item_id).where(
                    ExternalProviderId.provider == ExternalProvider.musicbrainz
                )
            )
        )
        item_titles = list(await db.scalars(select(Item.title).order_by(Item.title.asc())))

    assert bundle is not None
    assert bundle.title == "ae3o & h3ae"
    assert bundle.bundle_type == "box_set"
    assert bundle.format == "CD"
    assert len(bundle_items) == 2
    assert [entry.disc_label for entry in bundle_items] == ["ae3o", "h3ae"]
    assert sorted(provider_ids) == [
        "59211ea4-ffd2-4ad9-9a4e-941d3148024a",
        "59211ea4-ffd2-4ad9-9a4e-941d3148024a#disc-1",
        "59211ea4-ffd2-4ad9-9a4e-941d3148024a#disc-2",
    ]
    assert item_titles == ["ae3o", "h3ae"]
