# Core Current Status

Last reviewed: 2026-10-09.

## Implemented

- Core stores one concrete Catalog Item root for each of the nine active kinds.
- `CatalogKindDefinition` is the composition source for kind models, document
  schemas, field declarations, response schemas, proposal writers, and metadata
  routes. Media type and document registries are derived from it.
- Proposal validation accepts only fields declared by the submitted kind.
  Correction targets resolve the root model and entity type through the kind
  definition.
- Shared and kind-specific search routes return stable offset pages with
  `items`, `next_offset`, and `has_more`. Cross-kind search orders results
  before applying pagination. Music's detailed page retains discs and tracks.
- Identifier matching uses indexed barcode and catalog-number columns or
  JSONB containment supported by each non-Music root's GIN details index.
  Manga ISBN lookups use JSONB containment rather than unindexed scalar JSON
  extraction.
- Catalog-root entity resolution and canonical correction model lookup derive
  their nine root models from the kind composition registry.
- The edit-field contract contains field semantics and UI hints. Table and
  canonical write ownership are resolved through kind definitions.
- Shared credit shapes contain only common person and role fields. Artist ID
  and instrument are Music-specific. Music and Comic credit shapes support
  join phrases; unrelated kinds do not.
- Core's OpenAPI, field, active-kind, Music, and Catalog Item contracts were
  regenerated from the active sources and copied into App's pinned bundle.

## Remaining limits

- Music field decisions use the saved CLZ Music form. Exact CLZ parity for
  Comics, Books, Movies, and Games remains unverified until their Edit captures
  are available. Manga, Anime, TV, and Board Game ledgers are provisional
  because CLZ has no dedicated product form for them.
- The full Core suite passes 152 tests against the isolated local
  `collectarr_test` database. This includes canonical schema/API contracts and
  PostgreSQL `EXPLAIN` checks for declared identifier and scalar indexes;
  `ruff check .` also passes.
- Duplicate merge remains disabled until App-owned references can be remapped
  safely. No live database was reset, migrated, or deleted.
- The final App Windows build and repository-wide architecture guard remain to
  be run after the implementation and documentation pass is complete.
