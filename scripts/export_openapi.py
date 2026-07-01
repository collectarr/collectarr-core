"""Export the OpenAPI schema to docs/openapi.json.

Usage:
    python -m scripts.export_openapi
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.main import app  # noqa: E402


def main() -> None:
    schema = app.openapi()
    out = ROOT / "docs" / "openapi.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(schema, indent=2) + "\n", encoding="utf-8")
    version = schema.get("info", {}).get("version", "unknown")
    endpoints = sum(len(methods) for methods in schema.get("paths", {}).values())
    schemas_count = len(schema.get("components", {}).get("schemas", {}))
    print(f"OpenAPI {version} -> {out}  ({endpoints} endpoints, {schemas_count} schemas)")


if __name__ == "__main__":
    main()
