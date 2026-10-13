# Testing Collectarr Core

Run fast schema, domain and contract tests without a database:

```sh
python -m pytest -m "not db"
```

Run persistence/API tests against an isolated local database whose name ends in
`_test` with `ENVIRONMENT=test`:

```sh
python -m pytest -m db
```

Database tests carry the `db` marker. The `client` and `db_session` fixtures
request `clean_database`; tests opening sessions directly request it explicitly
with `pytest.mark.usefixtures("clean_database")`. Cleanup is never autouse.
Pure tests never depend on PostgreSQL and do not pay schema creation/truncation
costs. Schema initialization runs once per DB suite; each DB test gets clean
tables and rate-limit state. Existing live databases are never test targets.

`db`, `integration` and `slow` are registered markers. Unknown markers fail
collection. Both CI jobs report the 20 slowest test phases.

Before this change the full 167-test suite took about 150 seconds locally.
The final explicit split passes 116 fast tests in 1.00 seconds with PostgreSQL
unavailable and 51 DB tests in 44.34 seconds on the isolated test instance.
These are local measurements, not timing thresholds.
