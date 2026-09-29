# Flattened Catalog Baseline

This implementation starts from the following clean, pre-cutover revisions:

| Repository | Branch | Baseline commit |
|---|---|---|
| App | `codex/pre-cutover-rollback-20260929` | `6949fb4f00e6fdd5828e21474b74fa448e793fe9` |
| Core | `codex/pre-cutover-rollback-20260929` | `f57205692d34d521ab8a2091dd527dd6c5da1ca4` |

The App commit contains the existing UI and the legacy Work/Release/Copy graph. Core has typed kind tables plus provider integrations. These are the source schemas for the one-way flattened-catalog migrations; the new model must not be used as the migration source.

## Migration invariants

- A concrete edition/release/variant becomes one root item. Preserve its UUID when possible.
- Copy shared fields from its old parent chain to each derived root and preserve fields owned by the concrete edition.
- Keep genuinely independent children and remap their parent IDs to the new root.
- A parent with no concrete child becomes one root using the parent UUID and null concrete-edition fields.
- Emit an explicit mapping from every old catalog identity to zero, one, or several new identities. Personal records must resolve through an explicit policy; they must not be duplicated silently.
- Assert source/destination row counts, orphan counts, and ID collisions before a migration is considered complete.
- Do not run this migration against a live database or delete/reset a deployed database.

## Legacy identity paths

The migration fixture in `tests/fixtures/flattened_catalog/legacy_graph_migration_cases.json` records the identity paths that must be covered before replacing these model families:

| Kind | Shared/parent table | Concrete item table | Retained child examples |
|---|---|---|---|
| Music | `music_release_groups` | `music_releases` | `music_mediums`, `music_tracks`, credits |
| TV | `tv_series` | `tv_releases` | seasons, episodes, release media, episode mappings |
| Anime | `anime_series` | `anime_releases` | episodes, release media, episode mappings |
| Movie | `movie_works` | `movie_releases` | release media, credits, links |
| Book | `book_works` | `book_editions` | `book_printings`, contributions, identifiers |
| Board Game | `boardgame_works` | `boardgame_editions` | mechanics, categories, families, votes, rankings |
| Game | `game_works` | `game_releases` | platforms, company roles, ratings, identifiers |
| Manga | `manga_works` | `manga_editions` | chapters, series links, contributors |
| Comic | `comic_works` → `comic_issues` | `comic_variants` (or the issue when it has no variant) | series, story arcs, characters, creators |

Provider tables and external-ID provenance are not part of the target catalog. Personal App state is migrated in App/Sync using the explicit identity map produced by Core.

## Fixture coverage

For every kind, the golden fixture covers a parent with two concrete children and a parent with no concrete child. It also lists the real child tables that must retain their independent IDs. Kind-specific required fields and personal-reference remaps are added with the corresponding migration implementation, not inferred from this generic fixture.

## User proposals

User proposals remain part of the product. They are source-neutral submissions of the same Catalog Item fields shown by Add/Edit: `kind` plus a `catalog_item` object. Core stores only fields recognized for that kind; provider IDs, provider envelopes, snapshots, personal copy data, and other unrecognized values are omitted by the schema projection. The App may attach the signed-in user's ID for review attribution; anonymous submissions remain supported as in the previous flow. Proposal review remains a catalog editorial workflow and does not invoke provider search or ingestion.

Proposal approval is a moderation decision, not provider ingestion. During the staged flattening work, the proposal record and its submitted fields are retained independently of catalog roots. Approval publishes reviewed fields through a kind-owned Catalog Item writer. Book, Music, and Movie now have writers; the other six kinds remain pending until their typed roots are implemented.

Proposal validation must use the same typed, kind-owned flattened Catalog Item schema as manual Add/Edit. Do not maintain a denylist of personal field names. Core projects the submitted object onto the fields recognized for its kind, including declared contained-child fields, and persists only that projection. Unknown App-local copy fields and transport values are omitted without enumerating their names. A malformed value for a recognized field still fails validation with its field path. Proposal submission does not create an owned copy. Core derives root metadata keys from the kind field registry and validates declared child shapes in `app/catalog/catalog_item_schema.py`; this is the schema boundary to extend as each flattened kind model lands and the source used by proposal create and update.

The exporter emits `contracts/catalog-item-v1.json` from that same schema source and the App pins it under `tool/core_contracts/`. Music's field shape is grounded in the saved CLZ Music Edit form. The other eight kind shapes are provisional Core field inventories; their exact CLZ parity remains unverified until their Edit-form captures are available.

## Flattened Music root staging

Core now defines a source-neutral `MusicItem` root in `music_items`, with independent `MusicItemDisc` and `MusicItemTrack` child rows. The root corresponds to one concrete album edition; it contains the CLZ Music catalog fields and has no release-group parent. `GET /metadata/music/items` provides bounded offset pagination and exact barcode lookup, and `GET /metadata/music/items/{id}` reads one root with its ordered discs and tracks.

App now has a Music-owned typed transport DTO and remote source for listing and reading these flat Music items. They are not yet connected to the active Music Add/Edit, local persistence, or workspace flows; those still use the old release-group/release graph and remain part of the cutover. Track `position` accepts an integer or a string so identifiers such as `A1` survive transport, while `position_order` controls display order in Core.

Approving a Music proposal writes this root and its contained disc/track rows in the same database transaction as the moderation decision.

`migrations/20260929_flatten_music_catalog_items.sql` is the one-way backfill from the pinned legacy baseline. It preserves release IDs as item IDs, preserves medium and non-header track IDs, creates group-only items for groups without releases, and records differing legacy release titles in `music_item_migration_conflicts`. `music_item_legacy_identity_map` records each old root and child mapping; a Release Group with multiple releases is explicitly marked ambiguous rather than mapped to an arbitrary item. Legacy Music roles or label/identifier values with no direct CLZ field mapping are retained in `music_item_migration_review` for explicit review. The SQL is not executed by this implementation and must not be run against a live database. Existing release-group and release routes remain temporarily mounted while App's Music editor, workspace, and local storage move to the new response shape; they are not the target API and must be removed when that paired App migration lands.

The additive `migrations/20260929_catalog_item_proposals.sql` migration creates the proposal table for an existing Core database. Fresh databases receive the same table through `Base.metadata.create_all`. Do not execute either setup path as part of this code change or against a live database.

## Flattened Movie root staging

Core defines a typed `MovieItem` root in `movie_items` and contained `MovieItemMedia` rows in `movie_item_media`. The root stores one concrete edition's validated flattened Movie fields and does not require a Movie Work parent. `GET /metadata/movies/items` offers bounded offset pagination and exact barcode lookup; `GET /metadata/movies/items/{id}` returns the item and its ordered media. Movie proposal approval writes this root and media in the same transaction as the moderation decision.

`migrations/20260929_flatten_movie_catalog_items.sql` is the one-way backfill from `movie_works` and `movie_releases`. Release IDs become item IDs, media IDs are retained, works with no releases become standalone roots, and work references with multiple releases are recorded as ambiguous in `movie_item_legacy_identity_map`. Legacy fields without a v1 Movie contract destination are copied to `movie_item_migration_review`; source tables are retained. The migration has row-count and collision checks and has not been run. Movie's field ledger is provisional; this implementation does not claim CLZ parity.

Until the other six kinds have typed flattened roots and publication paths, attempts to approve their proposals return a conflict and leave them pending; Core never reports approval without publishing a Catalog Item.

## Flattened Book root staging

Core defines a typed `BookItem` root in `book_items`, with contained printing, credit, and identifier rows. Each Edition keeps its UUID as the item ID; shared Work fields are copied onto each derived item. A Work without Editions becomes one standalone item with edition-only fields left null. `GET /metadata/books/items` offers bounded offset pagination, exact barcode/identifier lookup, and `GET /metadata/books/items/{id}` reads one item with its contained rows.

`migrations/20260929_flatten_book_catalog_items.sql` is the one-way backfill from `book_works`, `book_editions`, and `book_printings`. It records Work mappings as ambiguous when a Work has multiple Editions, preserves printing IDs, and stores legacy fields without a contract destination in `book_item_migration_review`. The source tables remain intact and the migration has not been run. The Book field ledger is provisional; exact CLZ parity is unverified without a saved Edit-form capture.
