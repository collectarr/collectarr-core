# Contract V2 Vocabulary

This document freezes the shared vocabulary that `collectarr-core`, `collectarr-app`, and
`collectarr-sync` are expected to use while the catalog and personal-data contracts migrate
away from repo-local, stringly-typed shapes.

## Canonical terms

| Term | Meaning | Identity | Notes |
| --- | --- | --- | --- |
| `item` | The canonical catalog work unit shown in search and detail views. | `item_id` | Examples: issue, manga volume, movie, album, book, game. |
| `edition` | A publisher/format/language/regional edition of an item. | `edition_id` | Used for paperback vs hardcover, regional editions, language variants, platform-wide releases. |
| `variant` | A more specific physical or presentation variant underneath an edition. | `variant_id` | Used for covers, pressings, steelbooks, collector SKUs, platform-specific packages. |
| `release` | Legacy alias for an edition-level publication choice. | `release_id` | Kept only as a compatibility term; the active core graph is `item -> edition -> variant`. |
| `bundle_release` | A package that groups multiple catalog items into a sellable release. | `bundle_release_id` | Used for box sets, slipcases, disc bundles, collector sets. |

## Personal anchor contract

Personal entities in app and sync currently support these canonical anchor types:

| Anchor type | Required identity | Meaning |
| --- | --- | --- |
| `item` | none beyond `item_id` | The personal row targets the base catalog item. |
| `edition` | `edition_id` | The personal row targets an edition-level publication choice. |
| `variant` | `variant_id` preferred, `edition_id` fallback | The personal row targets a specific physical release/variant. |
| `bundle_release` | `bundle_release_id` | The personal row targets a bundle/package release. |

Normalization rules:

- Legacy aliases `media` and `work` normalize to `item`.
- Legacy aliases `release` and `edition` normalize to `edition`.
- Legacy aliases `physical_release` and `physical-release` normalize to `variant`.
- If `bundle_release_id` is present, the canonical anchor is `bundle_release`.
- If `variant_id` is present, the canonical anchor is `variant`.
- If only `edition_id` is present, the canonical anchor is `edition`.

## Catalog anchor support matrix

| Surface | `item` | `edition` | `variant` | `release` | `bundle_release` |
| --- | --- | --- | --- | --- | --- |
| `collectarr-core` catalog schema | yes | yes | yes | compatibility alias only | yes |
| `collectarr-app` admin/catalog DTOs | yes | yes | yes | normalized to `edition` | yes |
| `collectarr-app` personal ownership/wishlist | yes | yes | yes | normalized to `edition` | yes |
| `collectarr-sync` personal payloads | yes | yes | yes | normalized to `edition` | yes |

## Migration guardrails

- Core remains the source of truth for the canonical catalog graph.
- App and sync may keep v1 wire fields while they normalize onto the canonical vocabulary above.
- `release_id` remains a reserved compatibility field and should not be reintroduced as a first-class
  personal anchor without a coordinated cross-repo contract change.