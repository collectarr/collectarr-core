# Catalog Item Contract

This document describes the shared catalog contract consumed by
`collectarr-app`. It does not claim exact parity with every CLZ Edit form.
Saved captures are needed to confirm the remaining provisional App field
ledgers for kinds without a dedicated CLZ product.

## Active Kinds

The active kinds are `anime`, `boardgame`, `book`, `comic`, `game`, `manga`,
`movie`, `music`, and `tv`. Each is a top-level Catalog Item kind.

## Field Definitions

`app/schemas/catalog_item_v1.py` defines the typed request and response fields
for every kind. The `details` object is discriminated by `kind`; common fields
and each kind's contained data are validated before persistence. Catalog Item
details are stored together in `catalog_items.details`, while normalized
identifiers are indexed in `catalog_item_identities`.

App-owned fields do not appear in the Core contract. Owned Copies, purchase
details, conditions, local locations, personal images, notes, wishlists,
tracking, and listening history remain App or Sync data.

## Contract Artifacts

Core exports `openapi.json`, `catalog-item-v1.json`, and `active-kinds.json`.
Their hashes are recorded in `contract-manifest.json`. The old metadata field
registry and its `metadata-field-schema.json` artifact are retired; the typed
Catalog Item API schema is the source of truth for canonical fields.

Music is the `music` branch of `CatalogItemV1`, with ordered tracks, disc
titles, credits, and links as contained data. No release-group or medium
identity is exposed.

## Source-Neutral Writes

The App resolves provider data and prepares a complete Catalog Item before
submitting it. Core validates and deduplicates the canonical object without
knowing its source. Core does not accept provider IDs, envelopes, snapshots,
provenance, or import jobs.

When a field changes, update the typed schema, regenerate the contract bundle,
and update the pinned App contract deliberately.
