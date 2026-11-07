# Release notes

Every GitHub release uses this order: `Changes since last release:`; separator; `What's Changed`, contributor credits and comparison link.

Write the most important changes as a short English list in `docs/release-summaries.json`, keyed by release tag (for example `v1.2.0`): an object whose `summary` is a list of one-line entries, shown one under another. Explain user-visible outcomes, group related work, and do not claim tests or compatibility that were not checked. This summary is distinct from the complete change list. Keep `CHANGELOG.md` Unreleased entries grouped by Features, Fixes, Refactors, Docs and CI & Build for release preparation.

`tool/release_notes.py` builds `What's Changed` from the complete commit range of each release: every commit once, oldest first, with its author and commit link and the issues it or its pull request closes; merge commits and pull request titles are left out. GitHub's generated notes add New Contributors and the Full Changelog link. Lists that would exceed GitHub's description limit end with a link to the complete history. Without an editorial entry, the first changelog group of the release supplies up to ten rows.

Preview the newest release with `python tool/release_notes.py --repo collectarr/REPOSITORY`, or another one with `--tag vX.Y.Z`. Publish with the same command plus `--write`; `--all` backfills every published release. Drafts are excluded, and releases whose description is already current are not rewritten. Only release descriptions change: tags, versions, assets and databases are untouched.

The Release notes workflow runs after a successful Publish Release workflow and formats the newest release; run it manually with a tag, or with Backfill, to apply an edited summary to existing releases. It checks out main with its tags and commits summaries imported for new tags to `docs/release-summaries.json`, so every published summary stays versioned. Pushing to protected main needs the `RELEASE_TOKEN` secret.

Before semantic-release tags a release, the release workflow runs `tool/prepare_changelog.py`: it files the Unreleased `CHANGELOG.md` entries under `## X.Y.Z - date`, sets the version in `pyproject.toml` and pushes them as `chore(release): X.Y.Z`, which becomes the tagged commit. Pushing to protected main needs the `RELEASE_TOKEN` secret.
