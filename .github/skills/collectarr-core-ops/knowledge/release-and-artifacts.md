# Release And Artifact Knowledge

## Current alpha-line caveat

The current `main` release automation is not aligned with blindly continuing the alpha line.

Known recent behavior:
- remote alpha tags existed as `v0.1.0-alpha.1` and `v0.1.0-alpha.2`
- a later `v0.1.0-alpha.3` GitHub prerelease was created manually
- the `release.yml` flow on `main` followed the stable semantic-release path and had to be treated carefully

## Release-note workflow

For backend alpha release notes:
1. inspect the previous release notes
2. inspect the commit or PR range between tags
3. group the shipped changes into user-facing sections
4. update the GitHub release body in the existing style

Good current style:
- `## What's Changed`
- 2-3 summary bullets
- emoji section headers like `### ✨ Features`, `### 🐛 Fixes`, `### 🧪 Validation`, `### 🔒 Security`
- `Full Changelog:` link at the end

## Artifact verification

A backend release is only truly consumable when all intended artifacts exist.

Check separately:
- GitHub release/tag exists
- GHCR container version exists
- package visibility matches intended distribution
- anonymous or intended pull path actually works when public distribution is expected

## Known recent gap

A manual backend prerelease can exist without a matching GHCR image.

If GHCR push is attempted locally and Docker is unavailable, expect failures like missing `dockerDesktopLinuxEngine` / daemon connectivity. In that state:
- do not claim the container artifact was published
- report the exact remaining blocker
