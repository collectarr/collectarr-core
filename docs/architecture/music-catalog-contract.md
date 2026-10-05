# Music Catalog Contract

The public Music catalog uses one `CatalogMusicItemResponse` for each concrete album edition. Search and detail reads use `/metadata/music/items`; no response contains a Release Group → Release parent chain. Disc and track data are contained by the item and are described by `CatalogMusicDiscResponse` and `CatalogMusicTrackResponse`. The cross-kind `/search` and barcode lookup endpoints return `{id, kind, kind_data}` and keep Music fields, including the title, inside the Music-owned data map.

The Core contract exporter derives `contracts/music-catalog-v1.json` from the same Pydantic response schemas used by the API. App pins this artifact and owns the kind-specific Dart DTO. `metadata-field-schema.json` remains the contract for editable metadata fields; it does not describe the contained disc and track structure.

Music metadata-field ownership now points to `catalog_music_item` / `music_items`. Music no longer inherits Work/Release correction fields such as Edition title, Publisher, or Release status. The Admin catalog list, detail response, correction path, and reindexing read the flat `MusicItem` model; track corrections replace the contained JSONB document while retaining existing disc IDs, titles, matrix numbers, and matching track IDs.

## Field ownership

- Core owns canonical album-edition fields, discs, tracks, credits, identifiers, and catalog links.
- The v1 canonical track document contains ID, display position/order, title,
  artist, duration, and structural rows (`is_header`, `parent_header_id`,
  `indent_level`). Headers have a title and order but no position, artist, or
  duration. Parent headers must precede their children in the same disc;
  indentation is limited to 0?8 and must match the active parent depth.
  A disc contains its ID/number, title, matrix numbers, and ordered rows.
  Provider recording IDs, playback/file details, disc TOC data, storage
  placement, and other local-only fields are
  not accepted or returned by Core.
- User copies, media condition, storage device and slot, owned images, listening history, and other personal data remain in App and Sync.
- Music has no synopsis field. Synopsis remains available for kinds that define it.
- A Music item has one catalog identity. Two editions with the same title remain separate items.

## PostgreSQL baseline

Core supports a fresh v1 schema created from the current SQLAlchemy models. There is no schema-upgrade path. Existing databases and backups are not rewritten by `bootstrap_schema`; retain them separately and use a new, empty database for this baseline.

## Export

From the Core repository, run `python -m scripts.export_contract_bundle`. The exporter builds the Music item, disc, and track schemas from the API response classes and includes the artifact hash in `contract-manifest.json`.

CI runs `python -m scripts.export_contract_bundle --check` to compare the committed bundle with the current API schemas and verify the hashes in the manifest. The check ignores only the export timestamp and Core commit metadata, which change on each export.

## Music document storage

`music_items` is the only Music catalog table. Its non-null `discs` JSONB column
contains ordered discs and their tracks. Component UUIDs remain in the document;
there are no standalone disc/track entities or foreign keys. Typed validation
checks positive unique disc numbers, component IDs, non-negative track order and
duration, required row titles, playable track positions, and header hierarchy. Reads return the same nested API
shape. Writers replace the whole validated document; in-place nested JSON edits
are not a supported persistence path. Album revision/timestamps track document
changes. Search indexes album metadata; track search remains local to the App.

This is a fresh schema-v1 baseline, without migration or compatibility code.
Existing databases are not reset or transformed by this change.
