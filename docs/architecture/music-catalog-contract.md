# Music Catalog Contract

The Music catalog API graph is exported from the Pydantic response models in `app/schemas/metadata_music.py` to `contracts/music-catalog-v1.json`. The export includes release groups, release summaries, releases, mediums, tracks, and their typed relations. It records field types, required fields, nullability, and the paired partial-date representation.

The App pins this artifact alongside the other Core contracts and generates its Music DTOs from that pinned copy. `metadata-field-schema.json` remains the contract for editable metadata fields; it does not describe the nested Music catalog graph.

## Field ownership

- Core owns canonical release-group, release, medium, track, and catalog relation metadata.
- `recording_id` is track-level canonical metadata and is now included in the Core model and response graph.
- Synopsis remains available for kinds that use it. Music has no synopsis field in its catalog model, response, correction path, provider preview, or search.
- Media condition describes one physical copy. Core does not own user copies, so it is excluded from the canonical Music medium and API. The App stores it in each owned copy's medium details.
- App-only physical-format summaries are derived from medium types. A local box-set membership and its display label remain in App-owned persistence.
- Device image paths, owned copies, tracking, and other user data stay outside the Core catalog contract.

## PostgreSQL rollout

`app.scripts.bootstrap_schema` calls `create_all` and does not remove columns. Before deploying the updated model, take the normal database backup and run `migrations/20260925_music_field_ownership.sql`. The migration copies existing Music synopsis and medium-condition values into archive tables, then drops the obsolete columns. The archive tables preserve those values for manual recovery; neither field is imported into a different semantic field.

The migration adds the nullable `music_tracks.recording_id` column. `create_all` alone does not add columns to an existing table.

## Export

From the Core repository, run `python -m scripts.export_contract_bundle`. The exporter builds the Music graph schema from the same Pydantic response classes used by the API and includes its hash in `contract-manifest.json`.

CI runs `python -m scripts.export_contract_bundle --check` to compare the committed bundle with the current API schemas and verify the hashes in the manifest. The check ignores only the export timestamp and Core commit metadata, which change on each export.
