# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Central catalog server: PostgreSQL. Stores shared metadata only.
- Flutter client: Drift/SQLite. Stores the user's personal library and local catalog cache.
- Optional `collectarr-sync`: user-hosted event log for syncing a user's own devices.

The central server must not store owned items, wishlist, reading progress, ratings, prices,
condition, grading, notes, personal tags, or personal shelves. Shared editorial tags attached
to catalog series are allowed in Core.

## Central Catalog

The central schema is organized around item/release records plus per-kind grouping tables
where they still make sense:

| Concept | Current table | General meaning |
| --- | --- | --- |
| Item | `items` | Issue, episode, movie, album, book, game, expansion |
| Edition | `editions` | Format/region/language/publisher-level edition |
| Variant | `variants` | Cover, platform, pressing, steelbook, collector edition, regional variant |
| Bundle | `bundle_releases` | Multi-item package or box set |
| Bundle membership | `bundle_release_components` | Entities contained in a bundle |

Supported media kinds are:

`anime`, `boardgame`, `book`, `comic`, `game`, `manga`, `movie`, `music`, `tv`.

Until a release schema is finalized, normalized video format IDs are stored in
`editions.metadata_json.normalized.physical_format` and mirrored onto the
primary variant metadata. `editions.format` keeps the display label, while
`variants.variant_type` distinguishes `physical` from `digital` releases.

Most shared catalog tables include `metadata_json` so provider-specific fields can be stored
without changing the relational shape for every media type. Keep commonly filtered fields as
columns: title, number, release date, barcode, ISBN, region, platform, format, publisher, language.

## Generic Catalog Tables

The central catalog also has generic relationship tables:

- `organizations`: publishers, studios, developers, distributors, labels.
- `persons`: creators, writers, artists, directors, actors, authors, musicians.
- `entity_organizations`: organization roles attached to work/series/release/variant entities.
- `entity_persons`: person roles attached to work/series/release/variant entities.
- `tags`: genres, characters, arcs, themes, and shared editorial tags.
- `entity_tags`: tag assignments.
- `image_assets`: cover/poster/banner/background image refs in object storage.
- `image_cache_entries`: mirrored provider cover cache index, including source URL, object key,
  size, dimensions, content hash, and last access time for LRU cleanup.
- `external_provider_ids`: provider mappings such as GCD, ComicVine, IGDB, TMDb, AniList, BGG,
  OpenLibrary, MusicBrainz.

## Client Local Data

Flutter owns personal data locally. The current MVP keeps owned items and wishlist in separate
Drift tables, but semantically they map to:

- `ownership_status`: owned, wishlist.
- `tracking_status`: planned, in_progress, completed, paused, dropped, repeating.
- personal fields: purchase date, purchase price, grade, condition, rating, notes, personal tags,
    location, quantity, signed-by, key item, grading company.

The local catalog cache stores denormalized metadata snapshots so the app can show the user's
library offline even when the central catalog is unavailable.

## Sync Service

`collectarr-sync` is separate from the central catalog. It stores only user-owned event data:

- current entity state for personal entities
- append-only change log
- device id and client timestamps

The current implementation uses a small SQLite database for easy self-hosting. The schema is
intentionally event-log-shaped so it can later move to PostgreSQL without changing the client sync
contract.
