# Collectarr Core Implementation Plan

> **Superseded target:** any per-kind Work/Release roadmap in this document is
> replaced by the all-kind Catalog Item v1 target in
> [catalog-item-v1-cutover.md](catalog-item-v1-cutover.md). Core's current
> graph-backed models are transitional; this plan is not evidence that the new
> contract or storage is complete.

## Ownership

Core owns the canonical catalog, source-neutral write API, typed metadata
contracts, search indexing, image storage, and catalog administration. The
target App owns copies and personal activity but has no provider adapters,
credentials, source identifiers, or provider imports. Core accepts an already
prepared canonical object and does not perform provider search or ingest.

## Catalog v1 Cutover

The coordinated v1 release replaces Music's release-group/release/medium graph
with the `music` branch of `CatalogItemV1`, containing ordered tracks, disc
titles, credits, links, and catalog fields. The metadata API exposes one shared
Catalog Item route for all kinds. The cutover removes provider ingest, provider
IDs, provider-source snapshots, and provider-specific proposals from Core for
every kind.

Core and App use fresh databases for this baseline. Existing Core PostgreSQL
data and App Drift databases or backups from the old formats are incompatible.
The new Core bootstrap uses `create_all()` and will not reshape existing
tables. See [deployment.md](deployment.md) before deploying.

## Contract Workflow

1. Define canonical request and response fields in typed Pydantic schemas.
2. Store each value in its canonical kind-specific table or relation.
3. Add catalog fields to search documents only when they affect search.
4. Run `python -m scripts.export_contract_bundle` to regenerate the checked-in
   OpenAPI, Catalog Item, metadata field, and active-kind artifacts.
5. Update App's pinned artifacts explicitly when Core changes.

## Ongoing Work

- Expand typed catalog coverage while keeping canonical ownership explicit.
- Improve duplicate review and catalog correction operations.
- Harden deployments and the generated schema explorer.
- Keep barcode entry local-first in App and use the identifier for Core catalog search.
