# Bundle Release Design

This document defines the canonical Core schema for multi-item packages,
the App add-flow changes needed to expose them, and the exact rule for how
personal ownership and consumption tracking stay split between App and Sync.

## Goals

- Model a purchasable package that contains multiple canonical items.
- Keep the existing `item -> edition -> variant -> release` path for
  single-item releases.
- Keep personal ownership, wishlist, progress, rating, and history out of
  Core.
- Let the App distinguish between adding a work, adding a specific physical
  release, and adding a bundle/package.

## Non-goals

- Core does not store personal watch/read/play/listen state.
- V1 does not support nested bundles that contain other bundles.
- V1 does not introduce bundle-scoped completion or rating as a canonical
  concept.

## When To Use Which Canonical Entity

Use the existing single-item path when the user is dealing with one canonical
item and its edition-specific packaging.

Examples:

- movie -> Blu-ray steelbook
- comic issue -> direct edition -> cover variant
- game -> platform edition -> collector variant

Use `BundleRelease` when one purchasable package contains multiple canonical
items.

Examples:

- TV season box set containing episodes and specials
- film collection containing multiple movies
- manga starter box containing several volumes
- music compilation or anthology containing multiple albums or releases

## Canonical Core Schema

### New table: `bundle_releases`

`bundle_releases` represents a single purchasable package or SKU-level package
identity. If there are two materially different box sets with different barcode,
packaging, release date, or contents, they are two rows.

Suggested columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Standard `UuidMixin` |
| `kind` | `item_kind` enum | Must match the media family of the contained items |
| `title` | `String(255)` not null | Package display title |
| `bundle_type` | `String(64)` nullable, indexed | `box_set`, `collection`, `compilation`, `anthology`, `season_pack`, `starter_set`, `omnibus`, `deluxe_set` |
| `franchise_id` | UUID nullable FK -> `franchises.id` | Optional browse anchor |
| `series_id` | UUID nullable FK -> `series.id` | Optional browse anchor |
| `volume_id` | UUID nullable FK -> `volumes.id` | Optional browse anchor |
| `primary_item_id` | UUID nullable FK -> `items.id` | Main item for result ranking and fallback display |
| `format` | `String(64)` nullable, indexed | Display label such as `Blu-ray`, `4K UHD`, `CD`, `Vinyl`, `Digital` |
| `variant_type` | `String(64)` nullable, indexed | `physical` or `digital` |
| `packaging_type` | `String(64)` nullable, indexed | `box`, `slipcase`, `steelbook`, `digipak`, `collector_case` |
| `region` | `String(32)` nullable, indexed | Region code when applicable |
| `language` | `String(32)` nullable, indexed | Primary packaging/content language |
| `publisher` | `String(255)` nullable | Display publisher or label |
| `sku` | `String(100)` nullable, indexed | Store or distributor SKU |
| `barcode` | `String(32)` nullable, indexed | UPC/EAN search surface |
| `release_date` | `Date` nullable, indexed | Package release date |
| `cover_image_key` | `String(512)` nullable | Mirrored/generated package art |
| `cover_image_url` | `String(1024)` nullable | External package art |
| `thumbnail_image_key` | `String(512)` nullable | Thumbnail asset key |
| `thumbnail_image_url` | `String(1024)` nullable | Thumbnail URL |
| `external_ids` | `JSONB` nullable | Provider-specific package IDs |
| `metadata_json` | `JSONB` nullable | Disc structure, provider raw fields, normalized format IDs |
| `created_at` | timestamp | Standard `TimestampMixin` |
| `updated_at` | timestamp | Standard `TimestampMixin` |

Recommended indexes:

- `ix_bundle_releases_kind_bundle_type` on `(kind, bundle_type)`
- `ix_bundle_releases_series_release_date` on `(series_id, release_date)`
- `ix_bundle_releases_primary_item` on `(primary_item_id)`
- `ix_bundle_releases_barcode` on `(barcode)`
- `ix_bundle_releases_format_region` on `(format, region)`

Notes:

- `bundle_releases` is intentionally SKU-like. V1 does not add a separate
  logical bundle parent plus bundle variants layer.
- `external_provider_ids.entity_type` should accept `bundle_release` so Core
  can map provider bundle/package IDs without a second provider mapping table.
- `image_assets`, `entity_tags`, `entity_organizations`, and `entity_persons`
  should also accept `bundle_release` as an entity type.

### New join table: `bundle_release_items`

`bundle_release_items` maps the package to the canonical items it contains.

Suggested columns:

| Column | Type | Notes |
| --- | --- | --- |
| `id` | UUID PK | Standard `UuidMixin` |
| `bundle_release_id` | UUID FK -> `bundle_releases.id` | Cascade delete with bundle |
| `item_id` | UUID FK -> `items.id` | Canonical item included in the package |
| `role` | `String(32)` not null, indexed | `main`, `bonus`, `special`, `episode`, `movie`, `volume`, `soundtrack`, `booklet`, `expansion` |
| `sequence_number` | `Integer` nullable | Order within the package |
| `disc_number` | `Integer` nullable, indexed | Optional disc or tray grouping |
| `disc_label` | `String(255)` nullable | Display label for a disc or tray |
| `quantity` | `Integer` not null default `1` | Usually `1`, but explicit when needed |
| `is_primary` | `Boolean` not null default `False` | Primary content item for summaries |
| `metadata_json` | `JSONB` nullable | Provider-specific placement data |
| `created_at` | timestamp | Standard `TimestampMixin` |
| `updated_at` | timestamp | Standard `TimestampMixin` |

Recommended constraints and indexes:

- `UniqueConstraint(bundle_release_id, item_id, role, disc_number, sequence_number)`
- `ix_bundle_release_items_item` on `(item_id)`
- `ix_bundle_release_items_bundle_sequence` on `(bundle_release_id, disc_number, sequence_number)`

Notes:

- V1 supports mixed contents by item membership, but still assumes one media
  family per bundle row through `bundle_releases.kind`.
- If providers later expose package parts richer than disc/sequence, that extra
  shape belongs in `metadata_json` first.

### SQLAlchemy shape

Suggested model surface in `app/models/canonical.py`:

```python
class BundleRelease(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_releases"

    kind: Mapped[ItemKind] = mapped_column(
        Enum(ItemKind, name="item_kind"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    bundle_type: Mapped[str | None] = mapped_column(String(64), index=True)
    franchise_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("franchises.id", ondelete="SET NULL"), index=True
    )
    series_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("series.id", ondelete="SET NULL"), index=True
    )
    volume_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("volumes.id", ondelete="SET NULL"), index=True
    )
    primary_item_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), index=True
    )
    format: Mapped[str | None] = mapped_column(String(64), index=True)
    variant_type: Mapped[str | None] = mapped_column(String(64), index=True)
    packaging_type: Mapped[str | None] = mapped_column(String(64), index=True)
    region: Mapped[str | None] = mapped_column(String(32), index=True)
    language: Mapped[str | None] = mapped_column(String(32), index=True)
    publisher: Mapped[str | None] = mapped_column(String(255))
    sku: Mapped[str | None] = mapped_column(String(100), index=True)
    barcode: Mapped[str | None] = mapped_column(String(32), index=True)
    release_date: Mapped[date | None] = mapped_column(Date, index=True)
    cover_image_key: Mapped[str | None] = mapped_column(String(512))
    cover_image_url: Mapped[str | None] = mapped_column(String(1024))
    thumbnail_image_key: Mapped[str | None] = mapped_column(String(512))
    thumbnail_image_url: Mapped[str | None] = mapped_column(String(1024))
    external_ids: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    items: Mapped[list[BundleReleaseItem]] = relationship(
        back_populates="bundle_release", cascade="all, delete-orphan"
    )


class BundleReleaseItem(UuidMixin, TimestampMixin, Base):
    __tablename__ = "bundle_release_items"

    bundle_release_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bundle_releases.id", ondelete="CASCADE"), index=True
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    sequence_number: Mapped[int | None] = mapped_column(Integer)
    disc_number: Mapped[int | None] = mapped_column(Integer, index=True)
    disc_label: Mapped[str | None] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_primary: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)

    bundle_release: Mapped[BundleRelease] = relationship(back_populates="items")
    item: Mapped[Item] = relationship()
```

## Core API Contract Changes

The App needs bundle awareness without turning bundle rows into top-level search
noise for every query.

Suggested API shape:

- Keep `/metadata/search` item-first.
- Include `bundle_count` on item detail or preview payloads when bundle matches
  exist.
- Add `GET /metadata/items/{item_id}/bundle-releases` returning package rows
  that include that item.
- Add `GET /metadata/bundle-releases/{bundle_release_id}` for full bundle detail.
- Allow provider ingest to create both `item` rows and `bundle_release` rows when
  the upstream source exposes package composition.

Suggested item bundle summary payload:

```json
{
  "id": "bundle-id",
  "title": "Batman: The Animated Series - Complete Collection",
  "bundleType": "box_set",
  "format": "Blu-ray",
  "variantType": "physical",
  "packagingType": "box",
  "region": "US",
  "releaseDate": "2023-10-31",
  "barcode": "883929800000",
  "primaryItemId": "item-id",
  "contentSummary": {
    "totalItems": 12,
    "primaryCount": 10,
    "bonusCount": 2
  }
}
```

## App Add Dialog Changes

The current add flow has only `owned` and `wishlist`, and `owned` uses
`editionId` and `variantId` as the release anchor. That is not enough once the
user wants to add a multi-item package.

### New add target model

The add target should become:

- `owned`
- `wishlist`
- `track`

The reference being added should become a separate selection:

- `media`
- `release`
- `bundle`

These are different decisions and should not be overloaded into one menu.

### Allowed combinations

| Target | `media` | `release` | `bundle` |
| --- | --- | --- | --- |
| `owned` | yes | yes | yes |
| `wishlist` | yes | yes | yes |
| `track` | yes | no | no |

Rules:

- `track` is item-centric by definition.
- `release` means a single-item edition/variant selection.
- `bundle` means a `bundle_release_id` selection.

### Proposed add dialog flow

1. The user searches and selects a canonical item result.
2. The preview pane shows a second segmented control: `Media`, `Physical release`, `Bundle release`.
3. `Media` mode uses only the canonical `item_id`.
4. `Physical release` mode reuses the existing edition/variant selectors.
5. `Bundle release` mode shows packages returned by `/metadata/items/{item_id}/bundle-releases`.
6. Each bundle card shows title, format, region, year, barcode, and a short contents summary.
7. The primary action label adapts to both target and reference type.

Examples:

- `Add to collection: Media`
- `Add to collection: Physical release`
- `Add to collection: Bundle release`
- `Add to wishlist: Bundle release`
- `Track media`

### Required local model changes in App and Sync

Owned and wishlist entities must be able to point at either a plain item/release
or a bundle.

Suggested owned/wishlist anchor fields:

- `anchorType`: `item`, `variant`, `bundle_release`
- `itemId`: nullable only for pure bundle copies if the UI derives a primary item
- `editionId`: nullable
- `variantId`: nullable
- `bundleReleaseId`: nullable

Exactly one anchor mode should be valid:

- `item` => `itemId` set, others null
- `variant` => `itemId` + `editionId` and optionally `variantId` set
- `bundle_release` => `bundleReleaseId` set, `itemId` optional as cached primary item

### App UI behavior rules

- If the user picks `owned + media`, create a generic owned copy attached only
  to the canonical item.
- If the user picks `owned + release`, create the current owned copy with
  `editionId` and `variantId`.
- If the user picks `owned + bundle`, create one owned copy attached to
  `bundleReleaseId`.
- If the user picks `wishlist + bundle`, create a wishlist entry for that
  package, not for every contained item.
- If the user picks `track`, force `media` mode and show item-level tracking
  controls only.

## Exact Personal Tracking Rule

The split is:

- ownership tracks what the user possesses
- wishlist tracks what the user wants to acquire
- tracking tracks what the user consumed

That produces one exact rule:

> Ownership and wishlist attach to the acquisition unit.
> Consumption tracking attaches to the consumed canonical item.

### Ownership

Ownership is bound to the real thing the user owns:

- single item, unknown release -> item-level owned row
- specific edition or pressing -> variant/release anchored owned row
- box set or compilation -> bundle-level owned row

Bundle ownership carries collector data such as:

- purchase date
- price paid
- condition
- grading fields
- location
- quantity
- notes

### Consumption tracking

Consumption tracking is always item-level.

Required fields:

- `itemId` required
- `status` item-level (`planned`, `in_progress`, `completed`, `paused`, `dropped`, `repeating`)
- `rating` item-level
- `startedAt` and `finishedAt` item-level
- optional source fields: `sourceVariantId`, `sourceBundleReleaseId`

This means:

- owning a season box set does not mark every episode complete
- tracking one episode does not require separate ownership rows for each episode
- selling a bundle does not erase the fact that some included items were consumed

### Derived bundle progress

Bundle progress should be computed, not stored as a first-class tracking row.

Examples:

- `7 / 10 episodes watched`
- `3 / 5 volumes read`
- `2 / 4 films completed`

Computation rule:

- gather the canonical items in `bundle_release_items`
- join them with the user's item tracking entries in App or Sync
- derive summary chips and completion ratios in the UI

Core does not store that derived progress.

### Optional source linkage

When a user consumes an item from a bundle they own, App and Sync may keep a
source reference on the tracking entry:

- `sourceBundleReleaseId` when the item was consumed from a box set or compilation
- `sourceVariantId` when the item was consumed from a specific single-item release

That source is explanatory metadata, not the primary identity of the tracking
entry. The primary identity remains the canonical `itemId`.

## Examples

### Example 1: TV season box set

- Core has canonical episode items for season 1.
- Core has one `bundle_releases` row for `Season 1 Blu-ray Box`.
- Core has `bundle_release_items` rows linking the package to episodes and extras.
- App creates one owned row with `bundleReleaseId`.
- App creates tracking rows per episode as the user watches them.
- UI derives `8 / 12 watched` on the owned bundle card.

### Example 2: Film collection

- Core has separate movie items for each film.
- Core has one `bundle_releases` row for `Collection 4K Set`.
- The user can wishlist the bundle without wishlisting each film.
- The user tracks each watched film individually.

### Example 3: Single Blu-ray movie

- Core uses the existing `item -> edition -> variant -> release` model.
- No `BundleRelease` row is needed.
- App creates an owned row pointing to `editionId` and `variantId`.
- App tracks the movie itself at `itemId`.

## Implementation Sequence

1. Add `bundle_releases` and `bundle_release_items` to Core models and Alembic.
2. Extend generic entity tables and provider mappings to accept `bundle_release`.
3. Add item-scoped bundle lookup endpoints.
4. Teach provider normalization and ingest to emit bundle rows when upstream
   data exposes package contents.
5. Add `track` as a first-class add target in App.
6. Add `bundleReleaseId` and `anchorType` to local personal entities in App and Sync.
7. Update add dialog preview and save workflow to choose `media`, `release`, or `bundle`.
8. Add derived bundle-progress chips in App UI using local/synced item tracking.

## Decision Summary

- Core gains a canonical package entity: `bundle_releases`.
- Core keeps single-item physical releases in `edition`, `variant`, and `release`.
- App and Sync own all personal ownership, wishlist, and tracking state.
- Ownership attaches to the acquisition unit.
- Tracking attaches to the consumed item.
- Bundle completion is derived in the App, not stored in Core.