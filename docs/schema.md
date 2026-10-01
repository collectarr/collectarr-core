# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Central catalog server: PostgreSQL. Stores shared, canonical metadata only.
- Flutter client: Drift/SQLite. Stores the user's personal library and local catalog cache.
- Optional `collectarr-sync`: user-hosted event log for syncing a user's own devices.

The central server must not store owned items, wishlist state, reading progress, ratings,
prices, condition, grading, notes, personal tags, or personal shelves. Shared editorial tags
attached to catalog entities are allowed in Core.

## Central Catalog

The schema is kind-first. Each flattened kind root has a typed identity and revision,
kind-owned canonical details, and dedicated child tables for repeated records. Several
flattened roots store their validated kind details in JSONB; child records with independent
behavior remain relational.

| Kind | Canonical tables |
| --- | --- |
| Music | `music_items`, `music_item_discs`, `music_item_tracks` |
| Books | `book_items`, `book_item_printings`, `book_item_credits`, `book_item_identifiers`, `book_series`, `book_item_series_memberships` |
| Games | `game_items`, `game_item_identifiers` |
| Board games | `boardgame_items`, `boardgame_item_identifiers` |
| Comics | `comic_items`, `comic_item_identifiers` |
| Manga | `manga_items`, `manga_item_identifiers` |
| Anime | `anime_items`, `anime_item_media`, `anime_item_episodes`, `anime_item_identifiers` |
| Movies | `movie_items`, `movie_item_media` |
| TV | `tv_series`, `tv_seasons`, `tv_episodes`, `tv_releases`, `tv_release_media` |

Lists, identifiers, genres, platforms, credits, aliases, links, and other repeated values
use typed relation tables. Scalar metadata uses concrete SQL columns (`String`, `Text`,
`Integer`, `Boolean`, `Date`, `DateTime`, `Numeric`, `UUID`, or typed arrays where the field
is intrinsically ordered). Canonical payloads are validated and persisted through typed
kind-specific catalog fields.

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
