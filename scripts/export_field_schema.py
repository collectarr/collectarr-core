"""Export the unified metadata field schema to docs/field-schema.md.

The registry in ``app.catalog.metadata_fields`` is the single source of truth the
admin edit panel and the Flutter app edit dialog render from. Re-run this script
after changing the registry so the docs stay in sync:

Usage:
    python -m scripts.export_field_schema
"""

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog.kind_registry import CATALOG_KIND_DEFINITIONS  # noqa: E402
from app.catalog.metadata_fields import (  # noqa: E402
    METADATA_FIELD_SCHEMA_VERSION,  # noqa: E402
    METADATA_FIELDS,
    contract_rows,
    fields_for_kind,
)


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _join_unique(values: list[str]) -> str:
    unique = list(dict.fromkeys(value.strip() for value in values if value and value.strip()))
    if not unique:
        return "—"
    return ", ".join(unique)


def main() -> None:
    out = ROOT / "docs" / "field-schema.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    rows_by_key: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in contract_rows():
        rows_by_key[str(row["key"])].append(row)

    lines = [
        "# Metadata Field Schema",
        "",
        "> Generated from `app.catalog.metadata_fields`. Re-run "
        "`python -m scripts.export_field_schema` after changing the registry.",
        "",
        f"Schema version: **{METADATA_FIELD_SCHEMA_VERSION}**",
        "",
        "This is the single source of truth that the admin edit panel and the "
        "Flutter app edit dialog render from, exposed at `GET /api/v1/metadata/field-schema`.",
        "",
        "## Fields",
        "",
        "| Key | Value type | Section | Input | Editable | Kinds |",
        "| --- | --- | --- | --- | --- | --- |",
    ]

    for spec in METADATA_FIELDS:
        rows = rows_by_key.get(spec.key, [])
        kinds = _join_unique([str(row["kind"]) for row in rows])
        lines.append(
            f"| `{spec.key}` | {spec.value_type} | {spec.section} | {spec.input} | "
            f"{_yes_no(spec.editable)} | {kinds} |"
        )

    lines += ["", "## Fields per kind", ""]
    for definition in CATALOG_KIND_DEFINITIONS:
        kind = definition.kind
        keys = ", ".join(f"`{spec.key}`" for spec in fields_for_kind(kind))
        lines.append(f"- **{kind.value}**: {keys}")

    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
