# Collectarr Core

[![Catalog items](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-total.svg)](docs/deployment.md#catalog-badges)
[![Music](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-music.svg)](docs/deployment.md#catalog-badges)
[![Comics](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-comics.svg)](docs/deployment.md#catalog-badges)
[![Games](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-games.svg)](docs/deployment.md#catalog-badges)
[![Hardware](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-hardware.svg)](docs/deployment.md#catalog-badges)
[![Toys](https://raw.githubusercontent.com/collectarr/collectarr-core/catalog-badges/catalog-toys.svg)](docs/deployment.md#catalog-badges)

A self-hosted catalog for Collectarr: discover albums, comics, games, gaming
hardware and toys, keep edition details consistent and review improvements to
shared catalog information.

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
