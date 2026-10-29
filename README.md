# 🎼 Collectarr Core

A self-hosted Music and Games catalog for Collectarr: discover albums and games,
keep edition details consistent and review improvements to shared catalog information.

**License:** [GNU AGPLv3 only](LICENSE) (`AGPL-3.0-only`). See the
[contribution guide](CONTRIBUTING.md) for development and licensing terms,
including the historical MIT notice.

**Current release supports Music and Games.** Baseline 1 established the Music
baseline and shared catalog infrastructure. Ordered migration 2 introduced independent
Games inventory catalogs (Games, Hardware and Toys). Other kinds arrive in future
versioned migrations.

## ✨ A catalog built around real releases

- Search Music and Games releases using titles, creators, platforms and supported identifiers.
- Keep edition details, credits, discs, tracks, media and artwork together.
- Derive automatic sort titles for releases (e.g. "The Wall" -> "Wall, The").
- Manage independent inventories for Games, Hardware and Toys without mixing personal copy state.
- Describe recording details and credits at the correct album/disc scope.
- Submit new catalog entries and propose corrections for review.
- Let administrators review submissions and manage catalog quality.
- Give the App a consistent contract for searching, adding and editing items.

Core contains catalog facts. Your collection status, notes, loans, purchases,
listening/playing history and custom values belong to the App and optional Sync service.

## 📸 A look inside

> **Screenshot placeholder — Add from Core:** searching for a catalog release.
>
> **Screenshot placeholder — Catalog review:** proposed details and corrections.

## 🧭 An independent CLZ-inspired project

Core is part of Collectarr's independent **clean-room implementation inspired by
CLZ workflows**. Collectarr is not affiliated with or endorsed by CLZ.
No CLZ catalog dataset, implementation code or proprietary assets are bundled.

## 🔒 Stable data, explicit upgrades

The initial release created only the Music catalog and the shared infrastructure
it needs as the v1 baseline. Ordered migration 2 added independent tables for Games,
Hardware and Toys while preserving the Music baseline.
All persistent schema changes require explicit versioned migrations.
Adding another kind introduces its tables through an ordered migration rather than
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
