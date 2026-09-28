# Music Catalog Item Contract

Music is one typed kind in the source-neutral `CatalogItemV1` contract. A
Music item represents one concrete album edition and contains its catalog
fields, identifiers, images, links, credits, disc titles, and ordered tracks.
Tracks and disc titles are child data and have no independent catalog identity.

Core exports the shared contract at `contracts/catalog-item-v1.json`. App pins
that artifact and generates the typed Dart transport from it. There is no
separate Music catalog contract or DTO generator. The `MusicCatalogDetailsV1`
schema is the Music branch of the shared Catalog Item contract.

Provider search, credentials, source IDs, import history, snapshots, and
provenance belong to App and are not accepted by Core's catalog API. Owned
copies, tracking, listening history, local images, and personal fields also
remain in App; they are not part of the Core Catalog Item contract.

## Fresh database baseline

The coordinated v1 cutover targets fresh Core and App databases. Existing
databases and backups from the old Work/Release graph are incompatible with
the final schema. Core's `create_all()` creates missing tables but does not
reshape or remove existing tables. See [deployment.md](../deployment.md) before
deploying the completed cutover.

## Contract export

Run `python -m scripts.export_contract_bundle` from the Core repository after
changing source schemas. CI checks the checked-in OpenAPI, Catalog Item, and
active-kind artifacts against their source schemas and manifest hashes. The
exported Catalog Item contract is version 1.
