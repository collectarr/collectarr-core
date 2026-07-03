# Bundle Release Implementation Tasks

This checklist turns the bundle release design into concrete implementation
work across Core, App, and Sync.

Related design: `docs/bundle-release-design.md`

## Core

### Done in this slice

- Add canonical `BundleRelease` model.
- Add canonical `BundleReleaseComponent` membership model.
- Add Alembic migration `0007_add_bundle_releases.py`.
- Add head-schema coverage in migration tests.

### Next Core tasks

- Add Pydantic schemas for bundle summary and bundle detail payloads.
- Add typed bundle summary/detail routes on the dedicated bundle resource.
- Extend admin/provider ingest schemas so package composition can be persisted.
- Extend provider normalization contracts with optional bundle output.
- Add repository/service helpers to load bundle members and compute summaries.
- Allow `external_provider_ids.entity_type = bundle_release` in service-layer validation.
- Allow `image_assets`, `entity_tags`, `entity_persons`, and `entity_organizations`
  to attach to `bundle_release` in admin/editor flows.
- Add focused API tests for bundle list and bundle detail routes.
- Add ingest tests for one provider fixture that emits a bundle/package.

### Core sequencing

1. Schemas
2. Service/repository layer
3. Read endpoints
4. Provider ingest support
5. Tests

## App

### Done in this slice

- Add local `PersonalItemAnchorType` model.
- Add `anchorType` and `bundleReleaseId` to `OwnedItem`.
- Add `anchorType` and `bundleReleaseId` to `WishlistItem`.
- Add Drift columns for owned and wishlist cache tables.
- Regenerate `local_database.g.dart`.
- Propagate new fields through owned/wishlist repositories.
- Let collection mutations infer anchor type from variant versus bundle fields.

### Next App tasks

- Add bundle release DTOs to the metadata/admin model layer.
- Add API client methods for item bundle lookup and bundle detail.
- Extend local add-flow request models with `referenceType`:
  `media`, `release`, `bundle`.
- Add `track` as a first-class add target alongside `owned` and `wishlist`.
- Update `library_add_dialog.dart` preview pane to show reference selection.
- Reuse existing edition/variant selectors for `release` mode.
- Add bundle selector UI for `bundle` mode.
- Update `library_add_collection_workflow.dart` to pass `anchorType` and
  `bundleReleaseId` into `addItem` and `addToWishlist`.
- Add detail/inspector badges so owned and wishlist entries show whether they
  are item, release, or bundle anchored.
- Add derived bundle progress chips using item tracking joined against bundle
  membership.
- Add widget tests for:
  - owned media add
  - owned release add
  - owned bundle add
  - wishlist bundle add
  - track media only

### App sequencing

1. DTOs and API client
2. Add dialog state model
3. Add dialog UI
4. Workflow wiring
5. Detail/inspector presentation
6. Derived bundle progress
7. Widget tests

## Sync

### Next Sync tasks

- Add `anchor_type` and `bundle_release_id` to owned entity storage.
- Add `anchor_type` and `bundle_release_id` to wishlist entity storage.
- Keep tracking entity item-centric.
- Add optional `source_bundle_release_id` to tracking entries for attribution.
- Update push/pull serialization and validation.
- Add migration for existing sync databases.
- Add conflict-resolution coverage for anchor changes.
- Add tests for mixed-device sync where one device creates a bundle-owned row
  and another updates item-level tracking for a contained item.

### Sync sequencing

1. Storage schema
2. Wire payload validation
3. Migrations
4. Conflict handling
5. Tests

## Recommended implementation order

1. Core read endpoints for bundle lookup
2. App DTOs and API client
3. App add dialog reference-type flow
4. Sync schema extension
5. Derived bundle progress in App UI
6. Provider ingest bundle support in Core

## Immediate next task

The next highest-value step is App-side add-flow wiring, because the local model
support is now in place and the UI can start consuming real bundle metadata as
soon as Core exposes item-scoped bundle lookup endpoints.