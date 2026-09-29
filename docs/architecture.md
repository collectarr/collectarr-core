# Architecture

## Product boundary

Core owns source-neutral canonical catalog data and its read/write API. User
proposals are catalog submissions that moderators review before publication.
Core does not own owned copies or other personal state; optional personal-state
sync belongs to `collectarr-sync`.

Provider search, credentials, rate limiting, ingest jobs, and provider runtime
are not part of the target architecture. Old provider identifiers and snapshots
may still occur in legacy source tables retained for the staged catalog
migration; they are not an input to the flattened Catalog Item API.

## Catalog model

The target has one root aggregate per kind for a concrete collectible edition,
version, issue variant, or release. Kind-specific fields that were previously
split across a Work and a Release/Edition/Variant are stored on that root.
Genuine contained children keep kind-owned identities where they have domain
behavior, such as Music discs and tracks, TV/Anime episodes, Book printings,
credits, and identifiers. A series may remain a descriptive reference or
grouping, but it is not a required editable parent.

The flattened roots use separate typed tables:

```text
music_items   tv_items       anime_items
movie_items   book_items     boardgame_items
game_items    manga_items    comic_items
```

The flattened catalog implementation and its field-contract status are recorded
in [the baseline and current status](architecture/flattened-catalog-baseline.md).
Music's contract is grounded in the saved CLZ Music Edit form. Exact CLZ parity
for the other eight kinds remains unverified until their Edit-form captures are
available.

## API and proposals

Typed, source-neutral Catalog Item routes expose each flattened root and its
real children. Proposal review submits kind-owned Catalog Item fields, validates
them against the schema for that kind, and publishes approved values through the
same flattened writer. Unknown fields are not persisted; a malformed recognized
field is rejected with its field path. Proposals do not create owned copies.

The staged cutover is not yet complete across repositories. The App still has
active Work/Release forms, storage, and the legacy cross-kind `/search` path.
Legacy Core routes and tables remain mounted until the paired App migration is
complete. They are migration sources only and must not be treated as the target
Catalog Item contract. No live database migration or reset has been run.

The shared Core/App field artifact is exported from Core's schema source and
pinned by App. Regenerate it with `python -m scripts.export_contract_bundle`
and update App's pin only as part of an intentional contract change.

## Repository boundaries

- `collectarr-core` owns canonical catalog data, proposals, image delivery,
  search infrastructure, and catalog administration.
- `collectarr-app` owns the local library, owned copies, wishlist, tracking,
  personal images, locations, and user-facing workflows.
- `collectarr-sync` optionally mirrors personal state between App clients. It
  does not store canonical Catalog Items.

## Search and storage

PostgreSQL is the source of truth; Meilisearch is a derived index. Flattened
kind-specific search routes support bounded pagination and indexed exact
identifier lookup. Title and other supported substring fields use trigram
indexes.

Existing databases require the reviewed additive migrations documented in the
flattened-catalog status before they can use the new roots. This implementation
does not run migrations, reset a database, or delete existing data. Fresh
development setup instructions are documented separately in the deployment
guide.
