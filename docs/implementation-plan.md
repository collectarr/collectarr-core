# Catalog Item Document Unification Status

## Implemented in Core source

- One SQLAlchemy root table per concrete item for all nine kinds. Item-contained
  media, seasons, episodes, printings, credits, identifiers, discs, and tracks
  are stored in each root's `details` JSONB document.
- Kind-owned document-shape modules define root keys, contained object fields,
  nullability, required values, and collection validation. The common schema
  module composes those kind contracts and projects accepted proposals.
- Book series remain independent reusable groupings. People, organizations,
  editorial links, and workflow records keep their independent identities.
- Admin corrections, seed data, search, barcode/identifier lookup, reindex
  fingerprints, and overview counts use the flattened root documents.
- Movie media, Anime seasons, Music disc/track IDs and order, Book printing
  data, and identifier lists are retained in the contained documents.
- Music is grounded in the saved CLZ Music Edit form. Exact CLZ parity for the
  other eight kinds is unverified pending their Edit-form captures.

## Remaining coordinated work

1. Move scalar editable field definitions from `app/catalog/metadata_fields.py`
   into kind-owned field modules. Keep the shared registry as composition and
   contract export only.
2. Regenerate OpenAPI, the canonical contract bundle, and schema visualizations
   from the updated models. Review and pin the resulting bundle in App.
3. Finish App's per-kind typed metadata and personal-data models, remove
   duplicate shared kind DTOs and generic semantic readers, and preserve its
   current workspace presentation and personal features.
4. Finish the coordinated App/Sync reference and payload cutover. Sync continues
   to mirror personal state only; it must never receive Core catalog documents.
5. Update all repositories' current-status documents when the code and pinned
   contracts have been synchronized.

## Database boundary

The supported Core schema is created from the current SQLAlchemy models on a
new, empty PostgreSQL database. `create_all()` does not reshape an existing
database. Keep existing databases and backups untouched; use a separate empty
database for the v1 baseline.

## Checks

Contract generation and schema export are implementation steps. Run automated
tests only after the coordinated source and documentation changes are complete.
