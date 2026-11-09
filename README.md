<div align="center">

<h1>
  <img src="docs/assets/collectarr-icon.svg" alt="Collectarr Logo" width="128" height="128"><br>
  Collectarr Core
</h1>

A self-hosted catalog for Collectarr: discover albums, comics, games, gaming
hardware and toys, keep edition details consistent and review improvements to
shared catalog information.

[![Latest release](https://img.shields.io/github/v/release/collectarr/collectarr-core?label=latest&style=flat-square)](https://github.com/collectarr/collectarr-core/releases)
[![License](https://img.shields.io/badge/License-AGPL--3.0--only-blue?style=flat-square)](LICENSE)
[![CI](https://img.shields.io/github/actions/workflow/status/collectarr/collectarr-core/tests.yml?branch=main&style=flat-square&label=CI)](https://github.com/collectarr/collectarr-core/actions/workflows/tests.yml)
[![Release](https://img.shields.io/github/actions/workflow/status/collectarr/collectarr-core/release.yml?style=flat-square&label=release)](https://github.com/collectarr/collectarr-core/actions/workflows/release.yml)

[![Python](https://img.shields.io/badge/Python-3.14-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Container](https://img.shields.io/badge/Container-ghcr.io-2496ed?style=flat-square&logo=docker&logoColor=white)](https://github.com/collectarr/collectarr-core/pkgs/container/collectarr-core)
[![Contributing](https://img.shields.io/badge/Contributing-guide-orange?style=flat-square&logo=handshake&logoColor=white)](CONTRIBUTING.md)

[![Catalog items](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-total.svg)](docs/deployment.md#catalog-badges)
[![Music](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-music.svg)](docs/deployment.md#catalog-badges)
[![Comics](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-comics.svg)](docs/deployment.md#catalog-badges)
[![Games](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-games.svg)](docs/deployment.md#catalog-badges)
[![Hardware](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-hardware.svg)](docs/deployment.md#catalog-badges)
[![Toys](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-toys.svg)](docs/deployment.md#catalog-badges)

</div>

---

**License:** [GNU AGPLv3 only](LICENSE) (`AGPL-3.0-only`). See the
[contribution guide](CONTRIBUTING.md) for development and licensing terms,
including the historical MIT notice.

Core covers **Music**, **Comics** and **Games**, with separate **Hardware** and
**Toys** inventories inside Games. Other kinds arrive in future versioned
migrations.

## A catalog built around real releases

- Search each catalog using titles, creators and supported identifiers.
- Keep edition details, credits, discs, tracks, media and artwork together.
- Derive automatic sort titles for releases (e.g. "The Wall" -> "Wall, The").
- Manage independent inventories for Games, Hardware and Toys without mixing
  personal copy state.
- Describe recording details and credits at the correct album/disc scope.
- Submit new catalog entries and propose corrections for review.
- Let administrators review submissions and manage catalog quality.
- Give the App a consistent contract for searching, adding and editing items.

Core contains catalog facts. Your collection status, notes, loans, purchases,
listening/playing history and custom values belong to the App and optional Sync
service.

## Self-hosting

Run the published container image, `ghcr.io/collectarr/collectarr-core`, or
build the stack with Docker Compose. See [deployment](docs/deployment.md) for
setup, backups and the catalog badges, and [HTTPS and secrets](docs/https-and-secrets.md)
before exposing a server.

Pair Core with [Collectarr App](https://github.com/collectarr/collectarr-app).
Personal-device synchronization is provided separately by
[Collectarr Sync](https://github.com/collectarr/collectarr-sync).

## Stable data, explicit upgrades

All persistent schema changes use explicit, ordered migrations. Adding a kind
introduces its tables through a migration, without pre-creating unused schemas
or replacing existing databases. Do not reset a live database, user backup or
catalog as part of development.

## An independent CLZ-inspired project

Core is part of Collectarr's independent **clean-room implementation inspired by
CLZ workflows**. Collectarr is not affiliated with or endorsed by CLZ. No CLZ
catalog dataset, implementation code or proprietary assets are bundled.

## Development

Read the [architecture](docs/architecture.md) overview and [AGENTS.md](AGENTS.md)
before changing schema, contracts or persistence. Use Python 3.14 and the declared
dependencies, and start with an isolated test PostgreSQL database.
