---
name: collectarr-core-ops
description: "Use when working on collectarr-core recurring workflows: choose focused pytest or ruff validation for provider ingest, images, worker, metadata, or admin-domain changes; follow the protected-main PR flow for integrations; inspect or prepare alpha release notes and GHCR artifact checks; or avoid known repo-specific mistakes around release publishing and branch handling."
---

# collectarr-core ops

Use this skill for recurring backend workflows in `collectarr-core` so work starts from verified commands and release constraints instead of rediscovering them.

## Scope

This skill is for:
- focused validation of touched backend slices
- provider ingest, image pipeline, worker, metadata, and admin-domain follow-up work
- protected `main` branch / PR landing flow
- alpha release-note and artifact verification work

This skill is not for:
- Flutter app/browser preview tasks
- full Docker environment setup from scratch
- unrelated multi-repo release orchestration

## Assets

Read these first when relevant:
- `knowledge/validation-and-pr-flow.md`
- `knowledge/release-and-artifacts.md`

## Workflow

### 1. Focused validation first

For local backend edits:
- start with the cheapest focused test or lint command that can falsify the change
- only widen to broader validation after the touched slice is green
- use repo-known focused command sets from the knowledge files instead of defaulting immediately to full `pytest`

### 2. Protected main handling

`origin/main` is protected.

When the user asks to land larger integrated work:
- do not assume direct push is allowed
- prefer a linear branch from `origin/main`
- validate there, push the branch, and land through a PR with the required checks

### 3. Release work

For alpha release and release-note tasks:
- inspect the actual published tags and release state first
- verify whether GitHub Release, GHCR image, and visibility all line up
- do not assume a GitHub prerelease means the container artifact is consumable

### 4. Known mistakes to avoid

- Do not assume `main` can be pushed directly; branch protection rejects it.
- Do not assume the `release.yml` flow on `main` is safe for continuing the alpha line without checking the planned version/path first.
- Do not claim a backend release is complete if the GHCR image is missing or not pullable.
