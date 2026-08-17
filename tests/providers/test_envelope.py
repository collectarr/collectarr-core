import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from app.models.base import ItemKind
from app.providers.base import NormalizedItem
from app.providers.envelope import (
    NormalizedProviderEnvelopeV1,
    ProviderAttribution,
    ProviderImageRef,
    ProviderProvenance,
)
from scripts.export_provider_golden_fixtures import generate_golden_envelopes


def test_envelope_creation_and_serialization() -> None:
    norm = NormalizedItem(
        kind=ItemKind.book,
        title="Test Book",
        page_count=100,
        cover_image_url="https://example.com/cover.jpg",
    )
    envelope = NormalizedProviderEnvelopeV1.create(
        provider="test_provider",
        provider_item_id="item-123",
        kind=ItemKind.book,
        normalized=norm,
        source_url="https://example.com/item-123",
        raw_payload_hash="abcd",
        provider_version="1.0.0",
        fetched_at="2026-08-17T12:00:00Z",
    )

    data = envelope.to_dict()
    assert data["schema_version"] == "v1"
    assert data["provider"] == "test_provider"
    assert data["provider_item_id"] == "item-123"
    assert data["kind"] == "book"
    assert data["normalized"]["title"] == "Test Book"
    assert data["provenance"]["source_url"] == "https://example.com/item-123"
    assert len(data["images"]) == 1
    assert data["images"][0]["url"] == "https://example.com/cover.jpg"

    restored = NormalizedProviderEnvelopeV1.from_dict(data)
    assert restored.provider == envelope.provider
    assert restored.provider_item_id == envelope.provider_item_id
    assert restored.kind == envelope.kind
    assert restored.normalized == envelope.normalized
    assert restored.provenance == envelope.provenance
    assert restored.images == envelope.images
    assert restored.attribution == envelope.attribution


def test_golden_envelopes_contain_all_10_providers() -> None:
    fixtures = generate_golden_envelopes()
    assert len(fixtures) == 10

    providers = {f["provider"] for f in fixtures}
    expected_providers = {
        "openlibrary",
        "anilist",
        "musicbrainz",
        "mangadex",
        "gcd",
        "tmdb",
        "hardcover",
        "comicvine",
        "bgg",
        "igdb",
    }
    assert providers == expected_providers

    for item in fixtures:
        assert item["schema_version"] == "v1"
        assert item["provider"] in expected_providers
        assert item["provider_item_id"]
        assert item["kind"]
        assert isinstance(item["normalized"], dict)
        assert item["normalized"]["title"]
        assert "provenance" in item
        assert "fetched_at" in item["provenance"]
        assert isinstance(item["images"], list)
        assert len(item["images"]) >= 1
        assert "attribution" in item


if __name__ == "__main__":
    test_envelope_creation_and_serialization()
    test_golden_envelopes_contain_all_10_providers()
    print("All core envelope unit tests passed!")
