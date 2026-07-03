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

from app.catalog.metadata_fields import (  # noqa: E402
    METADATA_FIELDS,
    contract_rows,
    fields_for_kind,
)
from app.metadata_normalized import NORMALIZED_SCHEMA_VERSION  # noqa: E402
from app.models.base import ItemKind  # noqa: E402


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def _join_unique(values: list[str]) -> str:
    unique = list(
        dict.fromkeys(value.strip() for value in values if value and value.strip())
    )
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
        f"Schema version: **{NORMALIZED_SCHEMA_VERSION}**",
        "",
        "This is the single source of truth that the admin edit panel and the "
        "Flutter app edit dialog render from, exposed at `GET /metadata/field-schema`.",
        "",
        "## Fields",
        "",
        "| Key | Value type | Scope | Write target | Source entity type | Source table | Section | Input | Editable | Normalized | Kinds |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]

    for spec in METADATA_FIELDS:
        rows = rows_by_key.get(spec.key, [])
        scope = _join_unique([str(row["scope"]) for row in rows])
        write_target = _join_unique([str(row["writeTarget"]) for row in rows])
        entity_types = _join_unique([str(row["sourceEntityType"]) for row in rows])
        tables = _join_unique([str(row["sourceTable"]) for row in rows])
        if spec.common:
            kinds = "_all_"
        else:
            kinds = _join_unique([str(row["kind"]) for row in rows])
        lines.append(
            f"| `{spec.key}` | {spec.value_type} | {scope} | {write_target} | {entity_types} | {tables} | "
            f"{spec.section} | {spec.input} | {_yes_no(spec.editable)} | {_yes_no(spec.normalized)} | {kinds} |"
        )

    lines += ["", "## Fields per kind", ""]
    for kind in sorted(ItemKind, key=lambda k: k.value):
        keys = ", ".join(f"`{spec.key}`" for spec in fields_for_kind(kind))
        lines.append(f"- **{kind.value}**: {keys}")

    lines.append("")
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
