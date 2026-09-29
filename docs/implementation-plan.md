# Catalog Item v1 Status

## Implemented in Core

- Source-neutral typed Catalog Item roots and read/search routes exist for all
  nine kinds.
- User proposals use kind-owned Catalog Item fields and publish approved values
  through the corresponding kind writer.
- Search is paginated, exact identifier lookup uses indexed identity tables,
  and supported substring search uses trigram indexes.
- Duplicate merge remains disabled until App-owned references can be remapped
  atomically.
- The Core contract is exported from its schema source and pinned by App.
  Music is grounded in the saved CLZ Music Edit form; exact CLZ parity for the
  other eight kinds is unverified pending their Edit-form captures.

## Remaining coordinated work

1. Move App forms, local catalog persistence, workspace, and owned-copy
   creation to the typed roots while preserving the existing UI.
2. Move retained personal references to Catalog Item or Owned Copy references
   and keep their synchronization in `collectarr-sync`.
3. Remove Core catalog routes and tables that App no longer consumes. Retain
   kind-owned children with independent domain behavior.
4. Regenerate the contract and update the documented fresh-database setup in
   all three repositories.

## Local checks

```powershell
python -m scripts.export_contract_bundle --check
python -m ruff check .
python -m pytest
```

Contract generation without `--check` is an intentional source change and must
be reviewed together with App's pinned artifact. These checks do not modify or
reset a database.
