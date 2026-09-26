# Catalog Item v1 Cutover

## Core responsibility

Core owns shared, canonical Catalog Items and their typed contained data. A Catalog Item is one concrete collectible edition/version/issue variant/release. It is the only canonical workspace root for all nine kinds. Tracks, episodes, credits, components, included editions, and similar repeated information remain typed child data and do not create another editable Work or Release.

App owns providers, mapping, provider IDs, import provenance, owned copies, personal fields, tracking, reading/listening activity, and local images. Core receives source-neutral canonical Catalog Item writes and must not accept provider envelopes.

## Contract and reset

The target contract is `CatalogItemV1`, with a discriminated kind and typed details for Comic, Manga, Anime, Book, Game, Board Game, Movie, TV, and Music. Responses wrap `id`, `details`, and timestamps. Music write details accept ordered tracks without an album ID; Core supplies the containing Catalog Item ID on every returned track. The generated bundle contains `catalog-item-v1.json`; App pins that artifact and generates its transport types. OwnedCopy is intentionally excluded from Core.

The coordinated release starts Core and App on empty v1 databases and rebuilds search indexes. SQLAlchemy `create_all()` only adds missing tables; it is not a migration or reset mechanism. Existing database/backup formats are not compatible with the v1 baseline. Do not remove old tables or deploy the new baseline until App and Core are ready together.

## Status

Core now exports the typed all-kind Catalog Item v1 contract and has initial source-neutral `catalog_items` storage plus read, search, create, and update endpoints. The table is not yet populated by the existing App Add/Edit flows. Core still has per-kind work/release/edition models and routes for most kinds, and App still uses old scope refs and Drift schema v5. This document describes the target, not a claim that the cutover has completed.
