# Working rules

- Follow the user's instructions over this file.
- Use conventional commit titles. For real changes, add a body: what changed,
  why, and how it was checked. Do not use one-line commits for whole stages.
- Keep each commit to one fix, feature, refactor or docs change; split mixed
  work into separate commits instead of one commit per session.
- Update `CHANGELOG.md` under "Unreleased" in the same commit: one short,
  user-facing line in the matching section (Features, Fixes, Refactors, Docs,
  CI & Build), describing the effect rather than files or internals. The
  Release workflow turns these entries into the release notes.
- Fixes and Refactors entries only cover behavior or code that shipped in a
  published release. Changes to work that is still unreleased (for example a
  kind added since the last tag) get no Fixes/Refactors line; update that
  work's Features entry instead if its user-facing effect changed. Check with
  `git show <last tag>:<path>` when unsure. The commit type still follows the
  change itself.
- Run tests and linters before pushing (`ruff check .`, `pytest -m "not db"`
  for fast correctness, and verify the contract bundle with
  `python -m scripts.export_contract_bundle --check`).
- Merge pull requests with several commits using "Rebase and merge", so each
  conventional commit reaches `main` and sets the next version; squash only
  single-change pull requests.
- Release by running the Release workflow on `main`; do not bump versions or tag by hand.
- No legacy support, compatibility layers, deprecated aliases or dead code.
- After the initial Music baseline, change schemas with explicit ordered
  migrations. Never reset a database to make an upgrade work.
- Migrate from the last released schema. Unreleased intermediate schemas are
  not migration baselines: fold unreleased changes into the next migration
  instead of adding steps for them.
- Never modify live databases or backups. Use isolated test storage.
- Do not rewrite history or replace published tags without an explicit request.
- CLZ is a reference only. Do not copy its code, paid fonts or proprietary assets.
  Inspect it read-only: open editors and dialogs, then Cancel; never save there.
- The goal is an improved, fully FOSS CLZ. Match its workflows, but keep the
  stronger typed catalog model.
- Canonical APIs validate strict payloads. Importers may normalize inputs.
- Mark DB tests `db` and use explicit DB fixtures. Pure tests must not touch DBs.
- Keep kind-specific logic in kind modules (`app/catalog/kind_documents/`).
  Share common catalog mechanics, not kind rules.
- Scripts and tools must never delete, reset or seed the user's real database.
- Keep scratch files, logs and captures out of the repository; use a temporary directory.

## Token Efficiency

- Keep tool output short. Only retrieve what is needed.
- Search with `rg` before reading files.
- Read only relevant lines. Use offset/limit instead of reading entire files.
- Avoid reading the same content multiple times.
- Limit output using head, tail, or grep.
- Never dump large files, logs, or directories.
- Use `git diff` to inspect changes instead of re-reading files.
- Run targeted tests first. Show only relevant errors.
- Expand searches or output limits when needed for correctness.
- Preserve important findings across context compaction.

**Rule:** Minimize token usage without sacrificing correctness.

- Follow docs/release-notes.md for release descriptions. Write the editorial summary in docs/release-summaries.json; generate What's Changed with tool/release_notes.py. Keep contributor credit and comparison links.
