# Music Catalog Contract

The public Music catalog uses one `CatalogMusicItemResponse` for each concrete album edition. Search and detail reads use `/metadata/music/items`; no response contains a Release Group → Release parent chain. Disc and track data are contained by the item and are described by `CatalogMusicDiscResponse` and `CatalogMusicTrackResponse`.

The Core contract exporter derives `contracts/music-catalog-v1.json` from the same Pydantic response schemas used by the API. App pins this artifact and owns the kind-specific Dart DTO. `metadata-field-schema.json` remains the contract for editable metadata fields; it does not describe the contained disc and track structure.

## Field ownership

- Core owns canonical album-edition fields, discs, tracks, credits, identifiers, and catalog links.
- User copies, media condition, storage device and slot, owned images, listening history, and other personal data remain in App and Sync.
- Music has no synopsis field. Synopsis remains available for kinds that define it.
- A Music item has one catalog identity. Two editions with the same title remain separate items.

## PostgreSQL baseline

Core supports a fresh v1 schema created from the current SQLAlchemy models. There is no schema-upgrade path. Existing databases and backups are not rewritten by `bootstrap_schema`; retain them separately and use a new, empty database for this baseline.

## Export

From the Core repository, run `python -m scripts.export_contract_bundle`. The exporter builds the Music item, disc, and track schemas from the API response classes and includes the artifact hash in `contract-manifest.json`.

CI runs `python -m scripts.export_contract_bundle --check` to compare the committed bundle with the current API schemas and verify the hashes in the manifest. The check ignores only the export timestamp and Core commit metadata, which change on each export.
