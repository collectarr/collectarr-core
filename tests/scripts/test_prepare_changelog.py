import importlib.util
from pathlib import Path

import pytest

_spec = importlib.util.spec_from_file_location(
    "prepare_changelog", Path(__file__).resolve().parents[2] / "tool" / "prepare_changelog.py"
)
prepare_changelog = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(prepare_changelog)

CHANGELOG = """# Changelog

## Unreleased

### Features
- A new thing.

### Fixes
- A fixed thing.

## 1.0.0 - 2026-01-01

### Features
- The first thing.
"""


def test_unreleased_entries_are_filed_under_the_release():
    filed = prepare_changelog.file_changelog(CHANGELOG, "1.1.0", "2026-10-31")

    assert filed == """# Changelog

## Unreleased

## 1.1.0 - 2026-10-31

### Features
- A new thing.

### Fixes
- A fixed thing.

## 1.0.0 - 2026-01-01

### Features
- The first thing.
"""


def test_a_release_without_entries_or_already_filed_is_refused():
    empty = CHANGELOG.replace(
        "### Features\n- A new thing.\n\n### Fixes\n- A fixed thing.\n\n", "", 1
    )
    with pytest.raises(SystemExit):
        prepare_changelog.file_changelog(empty, "1.1.0", "2026-10-31")
    with pytest.raises(SystemExit):
        prepare_changelog.file_changelog(CHANGELOG, "1.0.0", "2026-10-31")


def test_the_package_version_is_set():
    pyproject = '[project]\nname = "collectarr"\nversion = "1.0.0"\n'

    assert prepare_changelog.set_package_version(pyproject, "1.1.0") == (
        '[project]\nname = "collectarr"\nversion = "1.1.0"\n'
    )
