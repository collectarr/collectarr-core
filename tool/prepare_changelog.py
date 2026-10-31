"""Record a release before it is tagged: file the Unreleased CHANGELOG.md entries under the version and set the package version."""
import argparse
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def file_changelog(text, version, date):
    """Move the Unreleased entries under a `## version - date` heading, leaving Unreleased empty."""
    match = re.search(r'^## Unreleased\n(.*?)(?=^## |\Z)', text, re.MULTILINE | re.DOTALL)
    if not match:
        sys.exit('CHANGELOG.md has no "## Unreleased" section.')
    entries = match.group(1).strip()
    if not entries:
        sys.exit('CHANGELOG.md has no Unreleased entries to release.')
    if re.search(rf'^## {re.escape(version)}\b', text, re.MULTILINE):
        sys.exit(f'CHANGELOG.md already has a {version} section.')
    filed = f'## Unreleased\n\n## {version} - {date}\n\n{entries}\n\n'
    return text[:match.start()] + filed + text[match.end():]


def set_package_version(text, version):
    updated, count = re.subn(r'^version = "[^"]*"', f'version = "{version}"', text, count=1, flags=re.MULTILINE)
    if count != 1:
        sys.exit('pyproject.toml has no version line.')
    return updated


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', required=True, help='Release version without leading v')
    parser.add_argument('--date', default=datetime.now(UTC).date().isoformat(), help='Release date, YYYY-MM-DD')
    args = parser.parse_args()
    changelog = ROOT / 'CHANGELOG.md'
    changelog.write_text(file_changelog(changelog.read_text(encoding='utf-8'), args.version, args.date), encoding='utf-8', newline='\n')
    pyproject = ROOT / 'pyproject.toml'
    pyproject.write_text(set_package_version(pyproject.read_text(encoding='utf-8'), args.version), encoding='utf-8', newline='\n')
    print(f'Recorded {args.version} ({args.date}) in CHANGELOG.md and pyproject.toml.')


if __name__ == '__main__':
    main()
