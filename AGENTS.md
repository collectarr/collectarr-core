# Working rules

- Follow the user's instructions over this file.
- Use conventional commit titles. For real changes, add a body: what changed,
  why, and how it was checked. Do not use one-line commits for whole stages.
- No legacy support, compatibility layers, deprecated aliases or dead code.
- After the initial Music baseline, change schemas with explicit ordered
  migrations. Never reset a database to make an upgrade work.
- Never modify live databases or backups. Use isolated test storage.
- Do not rewrite history or replace published tags without an explicit request.
- CLZ is a reference only. Do not copy its code, paid fonts or proprietary assets.
- Canonical APIs validate strict payloads. Importers may normalize inputs.
- Mark DB tests `db` and use explicit DB fixtures. Pure tests must not touch DBs.
