# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Central catalog server: PostgreSQL. Stores shared, canonical metadata only.
- Flutter client: Drift/SQLite. Stores the user's personal library and local catalog cache.
- Optional `collectarr-sync`: user-hosted event log for syncing a user's own devices.

The central server must not store owned items, wishlist state, reading progress, ratings,
prices, condition, grading, notes, personal tags, or personal shelves. Shared editorial tags
attached to catalog entities are allowed in Core.

## Central Catalog

The schema is kind-first. Canonical metadata is stored in typed tables for each media kind;
there is no generic metadata document column in the catalog schema.

| Kind | Canonical tables |
| --- | --- |
| Music | `music_release_groups`, `music_releases`, `music_mediums`, `music_tracks` |
| Books | `book_works`, `book_editions`, `book_printings` |
| Games | `game_works`, `game_releases` |
| Board games | `boardgame_works`, `boardgame_editions` |
| Comics | `comic_volumes`, `comic_works`, `comic_issues`, `comic_variants` |
| Manga | `manga_works`, `manga_editions`, `manga_chapters` |
| Anime | `anime_series` (Work), `anime_episodes`, `anime_releases`, `anime_release_media`, `anime_release_episode_map` |
| Movies | `movie_works`, `movie_releases`, `movie_release_media` |
| TV | `tv_series`, `tv_seasons`, `tv_episodes`, `tv_releases`, `tv_release_media` |

Lists, identifiers, genres, platforms, credits, aliases, links, and other repeated values
use typed relation tables. Scalar metadata uses concrete SQL columns (`String`, `Text`,
`Integer`, `Boolean`, `Date`, `DateTime`, `Numeric`, `UUID`, or typed arrays where the field
is intrinsically ordered). Provider payloads are used at ingest time and are not persisted as
JSON documents.

`provider_payload_snapshots` stores provenance and retention fields: provider identity, source URL,
payload hash, provider version, fetch/expiry timestamps, and purge timestamp. When a payload must
be retained for auditing, its source and normalized values are stored in
`provider_payload_snapshot_values` as typed path/value rows; purge removes those child rows.

The full generated schema, including every column, enum, foreign key, index, and constraint,
is available in [schema-full.md](schema-full.md) and the interactive [schema viewer](schema.html).

## Shared Catalog Relations

Shared typed relation tables include:

- `organizations`: publishers, studios, developers, distributors, and labels.
- `persons`: creators, writers, artists, directors, actors, authors, and musicians.
- `entity_organizations` and `entity_persons`: role-bearing links to catalog entities.
- `entity_aliases`: searchable alternate names.
- `entity_links`: trailers and external links.
- `entity_tags` and `tags`: shared editorial taxonomy assignments.
- `image_assets`: cover/poster/banner/background image references in object storage.
- `image_cache_entries`: provider image cache index.
- `external_provider_ids`: provider-to-canonical entity mappings.
- `provider_payload_snapshots` and `provider_payload_snapshot_values`: provider provenance plus
  optionally retained source/normalized payload values in typed path/value rows.

## Workflow Relations

Admin audit details, duplicate-review entity lists/details, and metadata proposal values are
stored in child tables. Their values use a typed scalar representation with a path column and
concrete value columns, so workflow history does not require a document column either.

## Client Local Data

Flutter owns personal data locally. The local catalog cache stores denormalized typed metadata
needed for offline rendering; it is not the source of truth for shared catalog metadata.

Personal fields include purchase date, purchase price, grade, condition, rating, notes,
personal tags, location, quantity, signed-by, key item, and grading company.

## Sync Service

`collectarr-sync` is separate from the central catalog. It stores only user-owned event data:

- current entity state for personal entities;
- append-only change log;
- device id and client timestamps.

The sync schema is intentionally event-log-shaped so it can later move to PostgreSQL without
changing the client sync contract.
