# Core current status

Reviewed: 2026-10-13.

The release branch exposes Music only. The current album/disc/credit/track structures are unchanged and labelled schema/contract v1 and package 1.0.0. Public kinds, navigation, proposals, corrections, search and generated contracts are restricted to Music. Unreleased kind models remain source modules and are not included in release table creation.

Baseline 1 installs the current Music and shared support tables through an explicit, transactional migration entry point. Existing unversioned or unsupported databases are refused without reset. Future schema changes and new kinds require ordered, data-preserving migrations.

Core owns canonical catalog metadata; App/Sync own personal library copies and state. Stable IDs, scoped credits, instrument lists and partial dates retain their current strict contract. Regenerated Music JSON definitions were compared with the pre-reset definitions and are identical.

Verification: Ruff and the contract generator check pass. All 167 tests pass against an isolated PostgreSQL test container, including fresh physical schema checks, preserved rows, unsupported-version refusal, admin summaries on the Music-only schema, strict wire validation, correction/audit and serializable inactive-kind errors. Production/development databases were not opened or changed.

The first release is being prepared, not published. Existing tags and Git history are preserved. Test-suite organization and database fixture runtime improvements are the next authorized stage.
