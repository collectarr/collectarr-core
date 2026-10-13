# 🎼 Collectarr Core

A self-hosted Music catalog for Collectarr: discover albums, keep edition details
consistent and review improvements to shared catalog information.

**Version 1 supports Music only.** The current Music schema and API are preserved
as the v1 baseline. Other kinds and their tables arrive in later releases.

## ✨ A catalog built around real releases

- Search Music releases using titles, artists and supported identifiers.
- Keep edition details, artist credits, discs, tracks and artwork together.
- Describe recording details and credits at the correct album/disc scope.
- Submit new catalog entries and propose corrections for review.
- Let administrators review submissions and manage catalog quality.
- Give the App a consistent contract for searching, adding and editing albums.

Core contains catalog facts. Your collection status, notes, loans, purchases,
listening history and custom values belong to the App and optional Sync service.

## 📸 A look inside

> **Screenshot placeholder — Add from Core:** searching for a Music album.
>
> **Screenshot placeholder — Catalog review:** proposed details and corrections.

## 🧭 An independent CLZ-inspired project

Core is part of Collectarr's independent **clean-room implementation inspired by
CLZ Music workflows**. Collectarr is not affiliated with or endorsed by CLZ.
No CLZ catalog dataset, implementation code or proprietary assets are bundled.

## 🔒 Stable data, explicit upgrades

The initial release creates only the Music catalog and the shared infrastructure
it needs. This is the current model labelled v1, not a historical schema rollback.
After v1, all persistent schema changes require explicit versioned migrations.
Adding another kind introduces its tables through a migration rather than
pre-creating unused schemas or replacing existing databases.

Do not reset a live database, user backup or catalog as part of development.

## 🚀 Use it with Collectarr

Pair Core with [Collectarr App](https://github.com/collectarr/collectarr-app).
Personal-device synchronization is provided separately by
[Collectarr Sync](https://github.com/collectarr/collectarr-sync).

<details>
<summary>Self-hosting and development</summary>

See [deployment](docs/deployment.md) and [architecture](docs/architecture.md).
Use Python 3.14 and the declared dependencies. Start with an isolated test
PostgreSQL database when developing, and read [AGENTS.md](AGENTS.md) before
changing schema, contracts or persistence.

</details>
