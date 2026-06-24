"""Export the unified metadata field schema to docs/field-schema.md.

The registry in ``app.catalog.metadata_fields`` is the single source of truth the
admin edit panel and the Flutter app edit dialog render from. Re-run this script
after changing the registry so the docs stay in sync:

Usage:
    python -m scripts.export_field_schema
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog.metadata_fields import METADATA_FIELDS, fields_for_kind  # noqa: E402
from app.metadata_normalized import NORMALIZED_SCHEMA_VERSION  # noqa: E402
from app.models.base import ItemKind  # noqa: E402


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def main() -> None:
    out = ROOT / "docs" / "field-schema.md"
    out.parent.mkdir(parents=True, exist_ok=True)

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
        "| Key | Value type | Common | Typed column | Kinds |",
        "| --- | --- | --- | --- | --- |",
    ]

    for spec in METADATA_FIELDS:
        if spec.common:
            kinds = "_all_"
        else:
            kinds = ", ".join(sorted(k.value for k in spec.kinds))
        lines.append(
            f"| `{spec.key}` | {spec.value_type} | {_yes_no(spec.common)} | "
            f"{_yes_no(spec.typed)} | {kinds} |"
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
