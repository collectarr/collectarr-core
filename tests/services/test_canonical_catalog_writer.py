import sys
from pathlib import Path
from datetime import date

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

import pytest

from app.models.base import ItemKind
from app.providers.base import (
    NormalizedCredit,
    NormalizedEpisode,
    NormalizedItem,
    NormalizedRelation,
    NormalizedSeason,
    NormalizedTrack,
)
from app.providers.envelope import (
    NormalizedProviderEnvelopeV1,
    ProviderAttribution,
    ProviderImageRef,
    ProviderProvenance,
)
from app.services.canonical_catalog_writer import (
    CanonicalCatalogWriter,
    CanonicalCatalogWriteResult,
    normalized_item_from_envelope,
)


def test_normalized_item_from_envelope_all_fields() -> None:
    norm = NormalizedItem(
        kind=ItemKind.comic,
        title="Action Comics #1",
        item_number="1",
        synopsis="Superman's first appearance",
        series_title="Action Comics",
        publisher="DC Comics",
        release_date=date(1938, 6, 1),
        cover_image_url="https://example.com/action1.jpg",
        creators=[
            NormalizedCredit(name="Jerry Siegel", role="Writer"),
            NormalizedCredit(name="Joe Shuster", role="Artist"),
        ],
        characters=[
            NormalizedCredit(name="Superman", role="Protagonist"),
            NormalizedCredit(name="Lois Lane", role="Supporting"),
        ],
        story_arcs=[
            NormalizedCredit(name="Golden Age Superman"),
        ],
        relations=[
            NormalizedRelation(
                relation_type="adaptation",
                title="Superman (1978)",
                kind=ItemKind.movie,
                start_year=1978,
            ),
        ],
    )

    envelope = NormalizedProviderEnvelopeV1.create(
        provider="comicvine",
        provider_item_id="4000-12345",
        kind=ItemKind.comic,
        normalized=norm,
        source_url="https://comicvine.gamespot.com/issue/4000-12345/",
        raw_payload_hash="hash123",
        provider_version="1.0.0",
        fetched_at="2026-08-18T12:00:00Z",
    )

    reconstructed = normalized_item_from_envelope(envelope)

    assert reconstructed.kind == ItemKind.comic
    assert reconstructed.title == "Action Comics #1"
    assert reconstructed.item_number == "1"
    assert reconstructed.publisher == "DC Comics"
    assert reconstructed.release_date == date(1938, 6, 1)
    assert len(reconstructed.creators) == 2
    assert reconstructed.creators[0].name == "Jerry Siegel"
    assert reconstructed.creators[0].role == "Writer"
    assert len(reconstructed.characters) == 2
    assert reconstructed.characters[0].name == "Superman"
    assert len(reconstructed.story_arcs) == 1
    assert reconstructed.story_arcs[0].name == "Golden Age Superman"
    assert len(reconstructed.relations) == 1
    assert reconstructed.relations[0].title == "Superman (1978)"
    assert reconstructed.relations[0].kind == ItemKind.movie


def test_normalized_item_from_envelope_music_and_tv() -> None:
    norm = NormalizedItem(
        kind=ItemKind.music,
        title="OK Computer",
        publisher="Parlophone",
        release_date=date(1997, 5, 21),
        tracks=[
            NormalizedTrack(position=1, title="Airbag", duration_seconds=284),
            NormalizedTrack(position=2, title="Paranoid Android", duration_seconds=383),
        ],
    )

    envelope = NormalizedProviderEnvelopeV1.create(
        provider="musicbrainz",
        provider_item_id="mb-album-1",
        kind=ItemKind.music,
        normalized=norm,
    )

    reconstructed = normalized_item_from_envelope(envelope)
    assert reconstructed.kind == ItemKind.music
    assert reconstructed.title == "OK Computer"
    assert len(reconstructed.tracks) == 2
    assert reconstructed.tracks[0].title == "Airbag"
    assert reconstructed.tracks[0].duration_seconds == 284
    assert reconstructed.tracks[1].title == "Paranoid Android"
