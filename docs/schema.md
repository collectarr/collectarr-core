# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Central catalog server: PostgreSQL. Stores shared metadata only.
- Flutter client: Drift/SQLite. Stores the user's personal library and local catalog cache.
- Optional `collectarr-sync`: user-hosted event log for syncing a user's own devices.

The central server must not store owned items, wishlist, reading progress, ratings, prices,
condition, grading, notes, tags, or personal shelves.

## Central Catalog

The backend currently keeps the comics-first class names for compatibility, but the schema is
generalized around this shape:

| Concept | Current table | General meaning |
| --- | --- | --- |
| Work/franchise | `franchises` | Abstract work/franchise such as Naruto, Batman, Dune, Elden Ring |
| Series/run | `series` | Comic run, manga series, TV show, music artist catalog, game series |
| Volume/group | `volumes` | Comic volume, TV season, manga run, album grouping |
| Release/item | `items` | Issue, volume, episode, movie, album, book, game, expansion |
| Edition | `editions` | Format/region/language/publisher-level edition |
| Variant | `variants` | Cover, platform, pressing, steelbook, collector edition, regional variant |

Supported media kinds are:

`anime`, `boardgame`, `book`, `bluray`, `comic`, `game`, `manga`, `movie`, `music`, `tv`.

Most shared catalog tables include `metadata_json` so provider-specific fields can be stored
without changing the relational shape for every media type. Keep commonly filtered fields as
columns: title, number, release date, barcode, ISBN, region, platform, format, publisher, language.

## Generic Catalog Tables

The central catalog also has generic relationship tables:

- `organizations`: publishers, studios, developers, distributors, labels.
- `persons`: creators, writers, artists, directors, actors, authors, musicians.
- `entity_organizations`: organization roles attached to work/series/release/variant entities.
- `entity_persons`: person roles attached to work/series/release/variant entities.
- `tags`: genres, characters, arcs, franchises, themes.
- `entity_tags`: tag assignments.
- `image_assets`: cover/poster/banner/background image refs in object storage.
- `external_provider_ids`: provider mappings such as GCD, ComicVine, IGDB, TMDb, AniList, BGG,
  OpenLibrary, MusicBrainz.

## Client Local Data

Flutter owns personal data locally. The current MVP keeps owned items and wishlist in separate
Drift tables, but semantically they map to:

- `ownership_status`: owned, wishlist.
- `tracking_status`: planned, in_progress, completed, paused, dropped, repeating.
- personal fields: purchase date, purchase price, grade, condition, rating, notes, tags,
  storage box, quantity, signed-by, key item, grading company.

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
