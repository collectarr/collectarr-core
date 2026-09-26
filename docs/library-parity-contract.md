# Library Parity Contract

> **Superseded target:** this document's previous entity levels do not define
> the new ownership model. The target is one Catalog Item plus zero or more
> App-owned copies, as described in
> [catalog-item-v1-cutover.md](catalog-item-v1-cutover.md). Public CLZ feature
> pages are not complete Edit-form field specifications; use the App's
> provisional per-kind ledgers until saved captures confirm exact parity.

This contract defines the shared kind and metadata surface consumed by
`collectarr-app` and `collectarr-sync`.

## Active Library Kinds

The active top-level kinds are `comic`, `manga`, `anime`, `book`, `game`,
`boardgame`, `movie`, `tv`, and `music`. `collection` remains an internal,
non-top-level kind.

## Metadata Field Schema

Editable canonical fields are declared in `app/catalog/metadata_fields.py` and
exported at `GET /api/v1/metadata/field-schema`. The schema identifies each
field's kind, type, UI role, canonical scope, source table, and write target.
The field schema describes the shared editing contract; it does not replace
kind-specific object schemas.

## Guarantees

1. Every active kind is top-level routable in the media catalog.
2. Every active kind has an explicit field schema and typed read contract.
3. Every exported field has an explicit canonical owner and write target.
4. Music uses one `MusicAlbumV1` catalog record with contained disc titles and
   ordered tracks; Music responses expose no release-group or medium identity.
5. Core contracts contain no provider IDs, source envelopes, provider search,
   or provider-import APIs. Provider integrations and provenance belong to App.

## Sources of Truth

- Kind labels and routing: `app/catalog/media_types.py`
- Field applicability and ownership: `app/catalog/metadata_fields.py`
- API request and response schemas: `app/schemas/`
- Generated client artifacts: `contracts/`

Core publishes `openapi.json`, `music-catalog-v1.json`,
`metadata-field-schema.json`, and `active-kinds.json`; their hashes are recorded
in `contract-manifest.json`. Update the source schema and regenerate the bundle
when a contract changes.
