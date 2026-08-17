"""Export golden fixtures for NormalizedProviderEnvelopeV1 across all 10 providers."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.models.base import ItemKind
from app.providers.anilist import AniListProvider
from app.providers.base import (
    NormalizedCredit,
    NormalizedItem,
    NormalizedRelation,
    NormalizedTrack,
    NormalizedVariantCover,
)
from app.providers.bgg import BGGProvider
from app.providers.comicvine import ComicVineProvider
from app.providers.envelope import NormalizedProviderEnvelopeV1
from app.providers.gcd import GCDProvider
from app.providers.hardcover import HardcoverProvider
from app.providers.igdb import IGDBProvider
from app.providers.mangadex import MangaDexProvider
from app.providers.musicbrainz import MusicBrainzProvider
from app.providers.openlibrary import OpenLibraryProvider
from app.providers.tmdb import TMDbProvider


def generate_golden_envelopes() -> list[dict[str, Any]]:
    envelopes: list[NormalizedProviderEnvelopeV1] = []

    # 1. Open Library (book)
    ol = OpenLibraryProvider()
    ol_norm = NormalizedItem(
        kind=ItemKind.book,
        title="The Fellowship of the Ring",
        subtitle="Being the First Part of The Lord of the Rings",
        synopsis="The first volume of the epic high-fantasy novel.",
        page_count=423,
        publisher="George Allen & Unwin",
        release_date=None,
        isbn="9780261102354",
        cover_image_url="https://covers.openlibrary.org/b/id/12345-L.jpg",
        creators=[NormalizedCredit(name="J.R.R. Tolkien", role="author")],
        genres=["Fantasy", "Adventure"],
        provider_ids={"openlibrary": "OL27479W", "openlibrary_edition": "OL82563M"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="openlibrary",
            provider_item_id="OL27479W",
            kind=ItemKind.book,
            normalized=ol_norm,
            capabilities=ol.capabilities,
            source_url="https://openlibrary.org/works/OL27479W",
            raw_payload_hash=hashlib.sha256(b"ol_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 2. AniList (manga & anime)
    ani = AniListProvider()
    ani_norm = NormalizedItem(
        kind=ItemKind.manga,
        title="Berserk",
        synopsis="Guts, a former mercenary known as the Black Swordsman, seeks revenge.",
        publisher="Hakusensha",
        cover_image_url="https://s4.anilist.co/file/anilistcdn/media/manga/cover/large/bx30002-777.jpg",
        creators=[NormalizedCredit(name="Kentarou Miura", role="Story & Art")],
        genres=["Action", "Adventure", "Dark Fantasy"],
        provider_ids={"anilist": "30002", "mal": "2"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="anilist",
            provider_item_id="30002",
            kind=ItemKind.manga,
            normalized=ani_norm,
            capabilities=ani.capabilities,
            source_url="https://anilist.co/manga/30002",
            raw_payload_hash=hashlib.sha256(b"anilist_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 3. MusicBrainz (music)
    mb = MusicBrainzProvider()
    mb_norm = NormalizedItem(
        kind=ItemKind.music,
        title="The Dark Side of the Moon",
        publisher="Harvest",
        cover_image_url="https://coverartarchive.org/release/a1b2c3d4/front.jpg",
        creators=[NormalizedCredit(name="Pink Floyd", role="Artist")],
        genres=["Progressive Rock", "Psychedelic Rock"],
        tracks=[
            NormalizedTrack(position=1, title="Speak to Me", duration_seconds=67),
            NormalizedTrack(position=2, title="Breathe (In the Air)", duration_seconds=169),
            NormalizedTrack(position=3, title="Time", duration_seconds=425),
        ],
        track_count=3,
        provider_ids={"musicbrainz": "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="musicbrainz",
            provider_item_id="a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
            kind=ItemKind.music,
            normalized=mb_norm,
            capabilities=mb.capabilities,
            source_url="https://musicbrainz.org/release/a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
            raw_payload_hash=hashlib.sha256(b"mb_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 4. MangaDex (manga)
    md = MangaDexProvider()
    md_norm = NormalizedItem(
        kind=ItemKind.manga,
        title="Chainsaw Man",
        synopsis="Denji is a teenage boy living with a Chainsaw Devil named Pochita.",
        publisher="Shueisha",
        cover_image_url="https://uploads.mangadex.org/covers/d7037b2a-874a-4360-8a7b-07f2001542a9/cover.jpg",
        creators=[NormalizedCredit(name="Tatsuki Fujimoto", role="Author/Artist")],
        genres=["Action", "Supernatural", "Comedy"],
        provider_ids={"mangadex": "d7037b2a-874a-4360-8a7b-07f2001542a9"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="mangadex",
            provider_item_id="d7037b2a-874a-4360-8a7b-07f2001542a9",
            kind=ItemKind.manga,
            normalized=md_norm,
            capabilities=md.capabilities,
            source_url="https://mangadex.org/title/d7037b2a-874a-4360-8a7b-07f2001542a9",
            raw_payload_hash=hashlib.sha256(b"md_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 5. GCD (comic)
    gcd = GCDProvider()
    gcd_norm = NormalizedItem(
        kind=ItemKind.comic,
        title="Amazing Spider-Man #300",
        series_title="The Amazing Spider-Man",
        item_number="300",
        synopsis="Venom makes his first full appearance.",
        publisher="Marvel Comics",
        cover_image_url="https://www.comics.org/media/img/covers/12345.jpg",
        creators=[
            NormalizedCredit(name="David Michelinie", role="writer"),
            NormalizedCredit(name="Todd McFarlane", role="penciller"),
        ],
        characters=[NormalizedCredit(name="Spider-Man"), NormalizedCredit(name="Venom")],
        provider_ids={"gcd": "12345"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="gcd",
            provider_item_id="12345",
            kind=ItemKind.comic,
            normalized=gcd_norm,
            capabilities=gcd.capabilities,
            source_url="https://www.comics.org/issue/12345/",
            raw_payload_hash=hashlib.sha256(b"gcd_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 6. TMDb (movie)
    tmdb = TMDbProvider()
    tmdb_norm = NormalizedItem(
        kind=ItemKind.movie,
        title="Fight Club",
        synopsis="A ticking-time-bomb insomniac and a slippery soap salesman channel raw male aggression into a shocking new form of therapy.",
        runtime_minutes=139,
        publisher="20th Century Fox",
        cover_image_url="https://image.tmdb.org/t/p/w500/bptfVGEQuv6vDTIMVCHjJ9Dz8PX.jpg",
        creators=[
            NormalizedCredit(name="David Fincher", role="Director"),
            NormalizedCredit(name="Brad Pitt", role="Actor"),
            NormalizedCredit(name="Edward Norton", role="Actor"),
        ],
        genres=["Drama", "Thriller"],
        audience_rating="8.4",
        provider_ids={"tmdb": "550", "imdb": "tt0137523"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="tmdb",
            provider_item_id="550",
            kind=ItemKind.movie,
            normalized=tmdb_norm,
            capabilities=tmdb.capabilities,
            source_url="https://www.themoviedb.org/movie/550",
            raw_payload_hash=hashlib.sha256(b"tmdb_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 7. Hardcover (book)
    hc = HardcoverProvider()
    hc_norm = NormalizedItem(
        kind=ItemKind.book,
        title="Dune",
        synopsis="Set on the desert planet Arrakis, Dune is the story of the boy Paul Atreides.",
        page_count=688,
        publisher="Chilton Books",
        cover_image_url="https://assets.hardcover.app/covers/dune.jpg",
        creators=[NormalizedCredit(name="Frank Herbert", role="Author")],
        genres=["Science Fiction", "Space Opera"],
        provider_ids={"hardcover": "1234"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="hardcover",
            provider_item_id="1234",
            kind=ItemKind.book,
            normalized=hc_norm,
            capabilities=hc.capabilities,
            source_url="https://hardcover.app/books/dune",
            raw_payload_hash=hashlib.sha256(b"hardcover_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 8. Comic Vine (comic)
    cv = ComicVineProvider()
    cv_norm = NormalizedItem(
        kind=ItemKind.comic,
        title="Absolute Batman #1",
        series_title="Absolute Batman",
        item_number="1",
        volume_start_year=2024,
        synopsis="In this new DC Absolute universe, Bruce Wayne has no money, no mansion, and no butler.",
        publisher="DC Comics",
        cover_image_url="https://comicvine.gamespot.com/a/uploads/scale_large/1/1/batman1.jpg",
        creators=[
            NormalizedCredit(name="Scott Snyder", role="Writer"),
            NormalizedCredit(name="Nick Dragotta", role="Artist"),
        ],
        variant_covers=[
            NormalizedVariantCover(
                name="Variant Cover B",
                cover_image_url="https://comicvine.gamespot.com/a/uploads/scale_large/1/1/batman1b.jpg",
                thumbnail_image_url="https://comicvine.gamespot.com/a/uploads/square_mini/1/1/batman1b.jpg",
            )
        ],
        provider_ids={"comicvine": "4000-160294"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="comicvine",
            provider_item_id="4000-160294",
            kind=ItemKind.comic,
            normalized=cv_norm,
            capabilities=cv.capabilities,
            source_url="https://comicvine.gamespot.com/absolute-batman-1/4000-160294/",
            raw_payload_hash=hashlib.sha256(b"cv_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 9. BGG (boardgame)
    bgg = BGGProvider()
    bgg_norm = NormalizedItem(
        kind=ItemKind.boardgame,
        title="Gloomhaven",
        synopsis="Gloomhaven is a game of Euro-inspired tactical combat in a persistent world of shifting motives.",
        min_players=1,
        max_players=4,
        playing_time_minutes=120,
        min_age=14,
        publisher="Cephalofair Games",
        cover_image_url="https://cf.geekdo-images.com/gloomhaven.jpg",
        creators=[NormalizedCredit(name="Isaac Childres", role="Designer")],
        genres=["Adventure", "Fantasy", "Miniatures"],
        provider_ids={"bgg": "174430"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="bgg",
            provider_item_id="174430",
            kind=ItemKind.boardgame,
            normalized=bgg_norm,
            capabilities=bgg.capabilities,
            source_url="https://boardgamegeek.com/boardgame/174430/gloomhaven",
            raw_payload_hash=hashlib.sha256(b"bgg_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    # 10. IGDB (game)
    igdb = IGDBProvider()
    igdb_norm = NormalizedItem(
        kind=ItemKind.game,
        title="The Witcher 3: Wild Hunt",
        synopsis="The Witcher: Wild Hunt is a story-driven open world RPG set in a visually stunning fantasy universe.",
        publisher="CD PROJEKT RED",
        cover_image_url="https://images.igdb.com/igdb/image/upload/t_cover_big/co1wyy.jpg",
        platforms=["PC", "PlayStation 4", "Xbox One", "Nintendo Switch"],
        genres=["Role-playing (RPG)", "Adventure"],
        audience_rating="92.0",
        provider_ids={"igdb": "1942"},
    )
    envelopes.append(
        NormalizedProviderEnvelopeV1.create(
            provider="igdb",
            provider_item_id="1942",
            kind=ItemKind.game,
            normalized=igdb_norm,
            capabilities=igdb.capabilities,
            source_url="https://www.igdb.com/games/the-witcher-3-wild-hunt",
            raw_payload_hash=hashlib.sha256(b"igdb_raw_payload").hexdigest(),
            provider_version="1.0.0",
            fetched_at="2026-08-17T12:00:00Z",
        )
    )

    return [env.to_dict() for env in envelopes]


def generate_envelope_schema() -> dict[str, Any]:
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "NormalizedProviderEnvelopeV1",
        "type": "object",
        "required": [
            "schema_version",
            "provider",
            "provider_item_id",
            "kind",
            "normalized",
            "provenance",
            "images",
            "attribution",
        ],
        "properties": {
            "schema_version": {"type": "string", "enum": ["v1"]},
            "provider": {"type": "string"},
            "provider_item_id": {"type": "string"},
            "kind": {"type": "string"},
            "normalized": {"type": "object"},
            "provenance": {
                "type": "object",
                "required": ["fetched_at"],
                "properties": {
                    "fetched_at": {"type": "string"},
                    "source_url": {"type": ["string", "null"]},
                    "raw_payload_hash": {"type": ["string", "null"]},
                    "provider_version": {"type": ["string", "null"]},
                },
            },
            "images": {
                "type": "array",
                "items": {
                    "type": "object",
                    "required": ["provider", "url"],
                    "properties": {
                        "provider": {"type": "string"},
                        "url": {"type": "string"},
                        "kind": {"type": "string"},
                        "thumbnail_url": {"type": ["string", "null"]},
                        "image_id": {"type": ["string", "null"]},
                        "headers": {"type": "object"},
                        "cache_policy": {"type": ["string", "null"]},
                        "mirror_policy": {"type": ["string", "null"]},
                        "attribution": {"type": ["string", "null"]},
                        "expires_at": {"type": ["string", "null"]},
                    },
                },
            },
            "attribution": {
                "type": "object",
                "required": ["required"],
                "properties": {
                    "required": {"type": "boolean"},
                    "text": {"type": ["string", "null"]},
                    "url": {"type": ["string", "null"]},
                    "license_name": {"type": ["string", "null"]},
                },
            },
        },
    }


def main() -> None:
    out_dir = ROOT / "contracts"
    fixtures = generate_golden_envelopes()
    schema = generate_envelope_schema()

    (out_dir / "golden-provider-envelopes.json").write_text(
        json.dumps(fixtures, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (out_dir / "provider-envelope-schema-v1.json").write_text(
        json.dumps(schema, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Exported {len(fixtures)} golden provider envelopes and schema to {out_dir}")


if __name__ == "__main__":
    main()
