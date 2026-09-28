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
