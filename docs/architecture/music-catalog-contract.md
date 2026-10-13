# Music Catalog Contract

The public Music catalog uses one `CatalogMusicItemResponse` for each concrete album edition. Detail reads use `/metadata/music/items/{id}`; search at `/metadata/music/items` returns a page with `items`, `next_offset`, and `has_more`. The cross-kind `/search` and barcode lookup endpoints return `{id, kind, kind_data}` and keep Music fields inside the Music-owned data map.

Core exports the strict v2 Music contract as `contracts/music-catalog-v2.json` and the kind payload schemas as `contracts/catalog-item-v2.json`. App pins these generated artifacts and owns the kind-specific Dart domain model. The v2 payload rejects the former album-level recording fields and role-specific credit arrays; there is no v1 adapter or fallback path.

## Ownership

- Album edition fields stay at the root: title, artist credits, release and original release dates, label, country, barcode, catalog number, packaging, genres, box-set metadata, covers, and external links.
- Generic `credits[]` belongs to the album. Each disc has its own `credits[]`, recording date, recording locations, live/studio state, and SPARS code. A credit has a stable ID, optional real `contributor_id`, credited name, role vocabulary value, optional role ID, instruments list, and sequence.
- `CatalogMusicArtistCreditResponse` remains separate because it carries artist join-phrase and sequence semantics. Composition belongs to a track.
- Each disc owns physical format and technical metadata. `format_family` has only `vinyl`, `opticalDisc`, `tape`, `digital`, and `other`; CD, SACD, and cassette are format names, not families.
- Search `release_date` and `release_year` come from the album's release or original release date. Disc recording dates stay separate and never fill a missing edition date.
- Personal collection data, user copies, media condition, storage placement, owned images, and listening history remain in App and Sync.
- A Music item has one catalog identity. Two editions with the same title remain separate items.

## Strict nested documents

Music v2 accepts `discs[]`, and each disc accepts ordered `tracks[]` and `credits[]`. Track rows retain IDs, display positions, order, title, artist, optional composition and duration, and hierarchy fields. Header rows have no position, artist, or duration. Parent headers must precede their children in the same disc; indentation must match the active parent depth.

Core rejects unknown root and nested fields, duplicate disc/track/credit IDs, duplicate positions, and non-canonical component ordering. Every non-null disc `format` requires an explicit, non-null coarse `format_family`, including custom vocabulary values. App format presets fill known families; custom formats require a user selection. Core does not infer family from a format label or repair approximate payloads. Provider/import normalization belongs before the canonical write boundary.

## PostgreSQL baseline

Core supports a fresh v2 schema created from the current SQLAlchemy models. There is no schema-upgrade path. Existing databases are not transformed by this change; bootstrap a new empty database for this baseline.

`music_items` is the only Music catalog table. Its non-null `discs` JSONB column contains ordered discs, credits, recording data, and tracks; album `credits` are stored as a separate JSONB collection. Component UUIDs remain in the document, with no standalone disc/track entities or foreign keys. Writers replace the full validated document. Album revision/timestamps track changes.

## Contract generation

From the Core repository, run `python -m scripts.export_contract_bundle`. The exporter derives the Music item, disc, credit, and track schemas from the API response classes and writes their hashes to `contract-manifest.json`. CI runs `python -m scripts.export_contract_bundle --check` to verify the generated artifacts and manifest hashes.
