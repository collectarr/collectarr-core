# Catalog Cutover Status

This document records the current Core/App cutover state. It is not a database
reset or deployment instruction. Do not run a reset against an existing user
database.

## In place in Core

- Source-neutral flattened Catalog Item roots and kind-specific read/search
  routes exist for all nine kinds.
- User proposals are validated against the flattened kind schema and approved
  proposals publish through kind-owned Catalog Item writers.
- Root searches use bounded pagination; exact identifiers use indexed
  identifier tables. Supported substring searches use PostgreSQL trigram
  indexes.
- Duplicate merge is disabled until App-owned references can be remapped in a
  coordinated operation. Duplicate inspection and ignore records remain.
- Core's pinned field contract is exported from its schema source. Music is
  grounded in the saved CLZ Music Edit form; exact parity for the other kinds is
  unverified pending their Edit-form captures.

## Remaining coordinated work

1. Connect App Add/Edit, local catalog persistence, workspace, offline rows,
   and owned-copy creation to the flattened Core roots while preserving the
   existing UI.
2. Move App's useful personal references and records to Catalog Item or owned
   copy identities, and keep their sync in `collectarr-sync`.
3. Replace App's active legacy cross-kind search with flat per-kind search and
   retain the kind's own query filters and result presentation.
4. After App no longer calls them, remove Core's old Work/Release routes,
   serializers, search projections, and schema imports. Retain only genuine
   kind-owned child entities.
5. Review old database values and complete deterministic one-way migrations
   from the recorded baseline. The SQL is not run by this implementation; do
   not reset or migrate a live database.
6. Refresh generated contracts and all three repositories' current-status and
   fresh-database instructions after each coordinated schema milestone.

The detailed legacy identity cases, migration invariants, field ledgers, and
contract notes are in
[`architecture/flattened-catalog-baseline.md`](architecture/flattened-catalog-baseline.md).

## Verification

After a Core model, route, or contract change, run:

```powershell
python -m scripts.export_contract_bundle --check
python -m ruff check .
python -m pytest
```

Contract generation without `--check` is an intentional source change and must
be reviewed together with App's pinned artifact. Existing databases and old
backup formats are not rewritten or deleted by these commands.
