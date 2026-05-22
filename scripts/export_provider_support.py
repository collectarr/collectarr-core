"""Export provider capability support data to docs/provider-support.md.

Usage:
    python -m scripts.export_provider_support
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.providers.registry import ProviderRegistry  # noqa: E402


def _yes_no(value: bool) -> str:
    return "Yes" if value else "No"


def main() -> None:
    registry = ProviderRegistry()
    rows = registry.status_entries()
    out = ROOT / "docs" / "provider-support.md"
    out.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        "# Provider Support Matrix",
        "",
        "> Generated from `ProviderRegistry`. Re-run `python -m scripts.export_provider_support` after changing provider capabilities.",
        "",
        "| Provider | Display Name | Kinds | Search | Ingest | User Key | Image Mirroring | Attribution | License |",
        "|----------|--------------|-------|--------|--------|----------|-----------------|-------------|---------|",
    ]

    for row in rows:
        kinds = ", ".join(kind.value for kind in row.supported_kinds)
        license_name = row.license_name or "-"
        lines.append(
            "| {name} | {display_name} | {kinds} | {search} | {ingest} | {user_key} | {mirroring} | {attribution} | {license_name} |".format(
                name=row.name,
                display_name=row.display_name,
                kinds=kinds,
                search=_yes_no(row.supports_search),
                ingest=_yes_no(row.supports_ingest),
                user_key=_yes_no(row.requires_user_key),
                mirroring=_yes_no(row.allows_image_mirroring),
                attribution=_yes_no(row.requires_attribution),
                license_name=license_name,
            )
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Provider support matrix -> {out} ({len(rows)} providers)")


if __name__ == "__main__":
    main()