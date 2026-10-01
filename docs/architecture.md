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
version, issue variant, or release. Kind-specific children such as Music discs
and tracks, TV/Anime episodes, Book printings, credits, and identifiers remain
children of that item. A series may remain a reference or grouping; it is not a
required editable parent.

Typed Catalog Item APIs and proposals exist for all nine kinds. The App cutover
is still in progress, so this repository does not yet claim that every older
per-kind route and table has been removed. Music's field contract is grounded in
the saved CLZ Music Edit form. Exact CLZ parity for the other eight kinds remains
unverified until their Edit-form captures are available.

Admin catalog search, item detail, root-level correction, per-kind item counts,
and search reindex include flat Catalog Item roots for all nine kinds. Comic,
Game, Board Game, and Manga each use one root per concrete collectible item;
their old Work/Release-style roots and related read paths have been removed.
Admin corrections update normalized identifier rows for applicable kinds and
Book credit rows. Structured contents such as printings, media, discs, seasons,
and episodes remain kind-owned child data. Anime and TV each use one flat
Catalog Item root with contained media, episodes, and identifiers; TV's former
series/release routes, models, services, and database tables are removed from
the active schema.

The shared field contract is exported from Core schemas and pinned by App.
Regenerate it with `python -m scripts.export_contract_bundle`; review any
intentional contract change together with the App pin.

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

PostgreSQL is the source of truth. The Add search route queries the flattened
Catalog Item roots directly and accepts `limit` and `offset`. Exact identifier
matches use each kind's indexed identity table where one exists, plus indexed
root barcode and catalog-number columns. Free-text matching is limited to
indexed title/sort fields (and indexed Music artist, label, and subtitle
fields); explicit filters inspect their named kind fields instead of casting
the entire JSON document to text.
