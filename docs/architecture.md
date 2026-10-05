# Architecture

## Product boundary

Core owns source-neutral catalog data, user-submitted catalog proposals, image
delivery, search, and catalog administration. App owns owned copies and all
personal state. Sync may mirror that personal state between App installations;
it never stores canonical catalog data.

The project has no provider search or ingest subsystem. Proposals carry only
kind-owned catalog fields from the same form used for manual Catalog Item
creation and editing. They do not contain source identities or owned-copy data.

## Catalog model

The target shape is one typed Catalog Item per concrete collectible edition,
version, issue variant, or release. Media, seasons, episodes, printings,
credits, identifiers, discs, tracks, and other repeated item values are typed
documents inside that kind's root JSONB document. Reusable groupings such as
Book series may keep independent identity; they are not required editable
parents.

Typed Catalog Item APIs and proposals exist for all nine kinds. Core's active
ORM and metadata routes use flat Catalog Item roots; the nine kind definitions
compose their model, document, field declarations, response schema, proposal
writer, and routes. Music's field contract is grounded in the saved CLZ Music
Edit form. Exact CLZ parity for the other eight kinds remains unverified until
their Edit-form captures are available.

Admin catalog search, item detail, root-level correction, per-kind item counts,
and search reindex include flat Catalog Item roots for all nine kinds. Comic,
Game, Board Game, and Manga each use one root per concrete collectible item;
their old Work/Release-style roots and related read paths have been removed.
Admin corrections update the relevant kind-owned root document while preserving
unrelated component identities. Structured contents such as printings, media,
discs, seasons, and episodes remain kind-owned values inside that document.
Anime and TV each use one flat Catalog Item root with contained media,
seasons, episodes, and identifiers; TV's former
series/release routes, models, services, and database tables are removed from
the active schema.

The shared field contract is exported from Core schemas and pinned by App.
Regenerate it with `python -m scripts.export_contract_bundle`; review any
intentional contract change together with the App pin. The metadata field
schema describes field identity, type, applicability, and editor hints. Root
table and write ownership come from the kind registry instead of repeated
per-field scope and table claims.

## Fresh database baseline

The current source defines a clean database baseline. Initialize a new, empty
PostgreSQL database with:

```powershell
python -m app.scripts.bootstrap_schema
```

Only a new, empty database is supported. `create_all()` creates missing
objects; it does not reshape existing tables. Keep existing
databases and backups intact and use a separate empty database for this
baseline. Never reset a deployed database as part of implementation work.

## Search and storage

PostgreSQL is the source of truth. Shared and kind-specific Catalog Item search
routes return `items`, `next_offset`, and `has_more`. Cross-kind search merges
all selected kinds before pagination and orders by normalized sort title,
normalized title, kind, and ID. Exact identifier matches use the kind root's
indexed JSONB details document, plus indexed root barcode and catalog-number
columns. Free-text matching uses indexed title/sort fields and indexed Music
artist, label, and subtitle fields; search does not cast the entire JSON
document to text.

The shared search route uses the Catalog Item envelope shape
`{id, kind, kind_data}`. Music's kind-specific page includes its typed disc and
track response because album contents are needed by Add. Other kind-specific
search pages retain their typed response model.
