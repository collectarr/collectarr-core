# Collectarr Data Boundaries

Collectarr splits data across three stores:

- Central catalog server: PostgreSQL. Stores shared, canonical metadata only.
- Flutter client: Drift/SQLite. Stores the user's personal library and local catalog cache.
- Optional `collectarr-sync`: user-hosted event log for syncing a user's own devices.

The central server must not store owned items, wishlist state, reading progress, ratings,
prices, condition, grading, notes, personal tags, or personal shelves. Shared editorial tags
attached to catalog entities are allowed in Core.

## Central Catalog

The schema is kind-first. Each concrete catalog item has one typed root row with a stable
identity, revision, and kind-owned `details` JSONB document. Repeated item data is typed and
stored inside that root document instead of separate child tables. `book_series` remains an
independent reusable grouping.

| Kind | Canonical tables |
| --- | --- |
| Music | `music_items` (discs and tracks are contained in `details`) |
| Books | `book_items`, `book_series` (printings, credits, identifiers, and item membership are contained in `details`) |
| Games | `game_items` (identifiers are contained in `details`) |
| Board games | `boardgame_items` (identifiers are contained in `details`) |
| Comics | `comic_items` (identifiers and issue details are contained in `details`) |
| Manga | `manga_items` (identifiers and chapters are contained in `details`) |
| Anime | `anime_items` (media, seasons, episodes, and identifiers are contained in `details`) |
| Movies | `movie_items` (media is contained in `details`) |
| TV | `tv_items` (media, seasons, episodes, and identifiers are contained in `details`) |

Kind-owned document schemas validate each root's scalar fields and repeated values, including
component identity and order where applicable. Shared editorial records such as people,
organizations, aliases, links, and tags keep independent tables when they are reused across
catalog items. Core search uses root columns and indexes over the JSONB documents.

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
