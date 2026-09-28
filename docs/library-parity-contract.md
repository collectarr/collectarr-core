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

## Field Ownership

Catalog Item v1 request and response fields are defined by the typed schemas in
`app/schemas/catalog_item_v1.py` and exported in `catalog-item-v1.json`. The
legacy `app/catalog/metadata_fields.py` registry remains for normalization and
correction workflows that have not yet moved to Catalog Item v1. It is exported
as an internal migration artifact and is not a public editing endpoint or the
source of Catalog Item field definitions.

## Guarantees

1. Every active kind is top-level routable in the media catalog.
2. Every active kind has an explicit field schema and typed read contract.
3. Every exported field has an explicit canonical owner and write target.
4. Music is the `music` branch of `CatalogItemV1`, with contained disc titles
   and ordered tracks; Catalog Item responses expose no release-group or
   medium identity.
5. Neither repository retains provider IDs, source envelopes, provider search,
   provider integrations, or provider-import APIs.

## Sources of Truth

- Kind labels and routing: `app/catalog/media_types.py`
- Field applicability and ownership: `app/catalog/metadata_fields.py`
- API request and response schemas: `app/schemas/`
- Generated client artifacts: `contracts/`

Core publishes `openapi.json`, `catalog-item-v1.json`,
`metadata-field-schema.json`, and `active-kinds.json`; their hashes are recorded
in `contract-manifest.json`. Music is a typed kind in the Catalog Item
contract, not a separate API graph. Update the source schema and regenerate the
bundle when a contract changes.
