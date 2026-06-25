# Library Parity Contract

This contract defines the canonical cross-repo metadata surface shared by `collectarr-core`, `collectarr-app`, and `collectarr-sync`.

## Active library kinds (P0 baseline)

The active top-level library kinds are exactly:

- `comic`
- `manga`
- `anime`
- `book`
- `game`
- `boardgame`
- `movie`
- `tv`
- `music`

`ItemKind.collection` remains a non-top-level internal kind and is intentionally excluded from the active parity set.

## Metadata field schema (single source of truth)

The canonical editable metadata fields are declared **once** in
`app/catalog/metadata_fields.py` as a registry of `MetadataFieldSpec` entries
(key, value type, label, common/typed flags, applicable kinds). All derived
lookups (`_COMMON_ALLOWED_KEYS`, `_KIND_ALLOWED_KEYS`, `_NORMALIZED_VALUE_TYPES`,
`TYPED_KIND_METADATA_KEYS` in `app/metadata_normalized.py`) are computed from this
registry so they can no longer drift apart.

This registry is the schema that the **admin edit panel** and the **Flutter app
edit dialog** render from. It is exposed over HTTP at `GET /metadata/field-schema`
and documented in `docs/field-schema.md`.

- Registry: `app/catalog/metadata_fields.py`
- HTTP schema: `GET /metadata/field-schema`
- Generated docs: `docs/field-schema.md` (re-run `python -m scripts.export_field_schema`)
- Golden test: `tests/metadata/test_field_registry_contract.py`

## Contract guarantees

1. Every active kind is top-level routable in the media catalog.
2. Every active kind has a non-null default provider.
3. Every active kind has at least one provider registered in `ProviderRegistry`.
4. The default provider for an active kind must be included in that kind's provider list.

## Source of truth

- Media-kind routing/defaults: `app/catalog/media_types.py`
- Provider capabilities: `app/providers/*` via `ProviderRegistry`
- Provider support snapshot: `docs/provider-support.md`

## Enforcement

Automated parity checks live in:

- `tests/metadata/test_library_parity_contract.py`

When changing kinds/providers, update the source of truth first and then update generated docs/tests if needed.
