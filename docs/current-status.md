# Core current status

The release exposes Music and Games in navigation. Games, Hardware and Toys
have independent catalog roots, tables, response models and proposal writers.
Hardware/Toy are registered catalog kinds without separate top-level navigation.
Canonical Hardware excludes serial numbers; personal copy state belongs to
App/Sync. Toys never accepts Hardware platform/type or Games progress fields.

Baseline 1 installs Music and shared support tables. Ordered migration 2 adds
`game_items`, `game_hardware_items` and `game_toy_items`, and the two new enum
values. Existing Music rows are preserved. Migration history and physical
schema must match; unversioned or unsupported databases are refused without
reset. No Games rows are reinterpreted as Hardware or Toys.

Verification uses isolated PostgreSQL storage: fresh install, baseline upgrade,
preservation, idempotence, strict wire validation, typed inventory create/read,
search, correction targets and the full test suite. Live databases and backups
were not opened or changed. The living UI comparison is maintained in the App
repository at `docs/clz-parity.md`.
