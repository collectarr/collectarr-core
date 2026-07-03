# Collectarr Core — Codex Instructions

## Product boundary
collectarr-core owns canonical catalog metadata, provider integrations, ingest, typed metadata contracts, admin metadata workflows, image/cache services, and contract exports for clients.

collectarr-core must not model app-owned personal user data such as owned copies, wishlist state, tracking progress, reading queue, loans, personal notes, local location/storage, purchase/sale data, or custom user field values.

## Canonical schema direction
The schema is kind-first.

Canonical metadata writes for migrated kinds must go to kind-specific tables:
- Books: book_works, book_editions, book_printings, book_contributions, book_identifiers, book_series_memberships
- Games: game_works, game_releases
- Board games: boardgame_works, boardgame_editions
- Music: music_releases, music_media, music_tracks
- Movies/TV/Comics/Manga/Anime: use their typed canonical slices

items, editions, and variants are legacy compatibility/search/projection tables only. Do not add new canonical metadata semantics to them.

## API and contracts
Core exports the client contract bundle from contracts/:
- openapi.json
- metadata-field-schema.json
- active-kinds.json
- provider-support.json
- contract-manifest.json

When API schemas, metadata fields, active kinds, or provider support change:
1. update the source registry/schema
2. regenerate contracts
3. update tests
4. keep app compatibility in mind

Do not use docs/*.md as the machine contract source. The contracts/ JSON files are the machine-readable source for clients.

## Metadata field schema
Every exported metadata field should include:
- key
- kind or applicableKinds
- valueType
- scope
- writeTarget
- sourceEntityType
- sourceTable
- editable/searchable/filterable flags where applicable

Fields must distinguish canonical metadata from legacy projection fields.

## Typed routes
Prefer typed routes over generic metadata fallback routes.

Do not add new features to:
- /metadata/{kind}/{id}
- /metadata/items/...
unless the code is explicitly legacy compatibility.

Prefer routes like:
- /metadata/books/works/{id}
- /metadata/books/editions/{id}
- /metadata/games/works/{id}
- /metadata/games/releases/{id}
- /metadata/boardgames/works/{id}
- /metadata/boardgames/editions/{id}
- /metadata/music/releases/{id}

## Refactor priorities
Prefer extracting from the large MetadataService into focused modules:
- typed reads
- search
- provider integration
- proposal/admin workflow
- facets
- images
- legacy projection
- per-kind handlers

Keep behavior-compatible tests when extracting.

## Local checks
Use the relevant local checks after changes:
- python -m scripts.export_contract_bundle
- python -m pytest
- python -m ruff check .

If a check cannot be run, state why.
