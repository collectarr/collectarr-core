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

`ItemKind.bluray` and `ItemKind.collection` still exist as non-top-level legacy/internal kinds and are intentionally excluded from the active parity set.

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
