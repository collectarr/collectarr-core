"""Generate the Flutter app's edit-field list from the core field registry.

This keeps the app's ``kAdminMetadataScalarFields`` contract a *generated*
projection of ``app.catalog.metadata_fields`` (the single source of truth) so a
field can only be added/changed in one place. The app still owns presentation
nuances (min/max lines, hint text) via a small overlay in
``shared_metadata_editing_contract.dart``.

Usage:
    python -m scripts.export_app_edit_fields [APP_REPO_PATH]

Defaults to ``../collectarr-app`` relative to this repo.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog.metadata_fields import METADATA_FIELDS  # noqa: E402

# Core editable fields rendered by dedicated app widgets instead of a scalar
# text field. They are intentionally excluded from the generated list.
_APP_HANDLED_SPECIALLY = {
    "physical_format",  # release physical-format dropdown
    "track_count",  # music track list widget
    "tracks",  # music track list widget
}

# Map a core ``value_type`` to the app's SharedMetadataFieldValueType name.
_VALUE_TYPE = {
    "string": "text",
    "string_list": "stringList",
    "integer": "integer",
    "date": "date",
    "link_list": "text",
    "track_list": "stringList",
}

# Map a core ``input`` hint to the app's SharedMetadataFieldInputType name.
_INPUT_TYPE = {
    "text": "text",
    "multiline": "multiline",
    "number": "number",
    "date": "text",
    "list": "text",
}


def _dart_str(value: str | None) -> str:
    if value is None:
        return "null"
    escaped = value.replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def main() -> None:
    app_root = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parent / "collectarr-app"
    out = app_root / "lib" / "features" / "library" / "metadata" / "metadata_fields.g.dart"
    if not out.parent.exists():
        raise SystemExit(f"App metadata directory not found: {out.parent}")

    specs = [
        spec
        for spec in METADATA_FIELDS
        if spec.editable and spec.key not in _APP_HANDLED_SPECIALLY
    ]

    lines = [
        "// GENERATED CODE - DO NOT MODIFY BY HAND.",
        "//",
        "// Projected from collectarr-core app/catalog/metadata_fields.py via",
        "// `python -m scripts.export_app_edit_fields`. Edit the core registry and",
        "// re-run the generator; presentation nuances live in",
        "// shared_metadata_editing_contract.dart.",
        "",
        "/// One generated metadata edit field, sourced from the core registry.",
        "typedef GeneratedMetadataField = ({",
        "  String key,",
        "  String label,",
        "  String section,",
        "  String valueType,",
        "  String inputType,",
        "  String? normalizedValueType,",
        "});",
        "",
        "/// The canonical editable scalar fields, projected from the core registry.",
        "const List<GeneratedMetadataField> kGeneratedMetadataFields = [",
    ]
    for spec in specs:
        normalized = spec.value_type if spec.normalized else None
        lines.append(
            "  ("
            f"key: {_dart_str(spec.key)}, "
            f"label: {_dart_str(spec.label)}, "
            f"section: {_dart_str(spec.section)}, "
            f"valueType: {_dart_str(_VALUE_TYPE[spec.value_type])}, "
            f"inputType: {_dart_str(_INPUT_TYPE[spec.input])}, "
            f"normalizedValueType: {_dart_str(normalized)}"
            "),"
        )
    lines += ["];", ""]

    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out} ({len(specs)} fields)")


if __name__ == "__main__":
    main()
