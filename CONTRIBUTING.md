# Contributing to Collectarr Core

Thanks for improving the self-hostable catalog behind Collectarr.

## Before you start

- Check existing issues and pull requests; discuss schema and API changes first.
- Read [AGENTS.md](AGENTS.md) and the architecture and deployment docs.
- Never reset production data or introduce destructive migrations as a shortcut.
- Keep credentials, personal data, CLZ proprietary assets, and unlicensed
  catalog datasets out of the repository.

## Development and review

Use Python 3.14 and the project's declared dependencies. Develop against an
isolated test PostgreSQL database. Follow the repository's documented test
commands and migration checks; describe tests and compatibility implications
in your pull request. Keep changes focused and add tests for behavior changes.

## Licensing contributions

Collectarr Core is licensed under **GNU Affero GPLv3 only**
(`AGPL-3.0-only`). By submitting a contribution, you confirm that you
have the right to submit it under that license and that it may be
redistributed under those terms. You retain copyright to your original
contribution; no copyright assignment is required.

Identify third-party code, dependencies, and assets with their own licenses.
Previously published MIT-licensed versions remain available under their
original terms; the historical notice is preserved in
[LICENSES/MIT-legacy.txt](LICENSES/MIT-legacy.txt).
See [LICENSE](LICENSE) for the full AGPLv3 terms, including source access
requirements for users interacting remotely with modified versions.
If you deploy a modified version, make its complete corresponding source
available to remote users under AGPLv3 section 13, and update the source
link presented in the API documentation to point to your modified source.

## Community

Be respectful in issues and reviews. Maintainers may request tests, migration
plans, or documentation before merging.
