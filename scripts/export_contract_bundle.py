"""Export the versioned Core contract bundle for app sync.

Usage:
    python -m scripts.export_contract_bundle
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.catalog.media_types import top_level_media_types  # noqa: E402
from app.catalog.metadata_fields import contract_rows  # noqa: E402
from app.main import app  # noqa: E402
from app.providers.registry import ProviderRegistry  # noqa: E402

CONTRACT_VERSION = "1.0.0"


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return result.stdout.strip() or "unknown"


def build_contract_bundle() -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    openapi = app.openapi()
    field_schema = {
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": generated_at,
        "fields": contract_rows(),
    }
    active_kinds = {
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": generated_at,
        "kinds": [media_type.kind.value for media_type in top_level_media_types],
    }
    registry = ProviderRegistry()
    provider_support = {
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": generated_at,
        "providers": [
            {
                "name": row.name,
                "displayName": row.display_name,
                "kind": row.kind.value,
                "supportedKinds": [kind.value for kind in row.supported_kinds],
                "isConfigured": row.is_configured,
                "statusMessage": row.status_message,
                "supportsSearch": row.supports_search,
                "supportsIngest": row.supports_ingest,
                "requiresUserKey": row.requires_user_key,
                "nonCommercialOnly": row.non_commercial_only,
                "allowsRedistribution": row.allows_redistribution,
                "allowsImageMirroring": row.allows_image_mirroring,
                "requiresAttribution": row.requires_attribution,
                "licenseName": row.license_name,
                "termsUrl": row.terms_url,
                "attributionUrl": row.attribution_url,
                "rateLimit": row.rate_limit,
                "cachePolicy": row.cache_policy,
            }
            for row in registry.status_entries()
        ],
    }
    return {
        "generatedAt": generated_at,
        "coreCommit": _git_commit(),
        "openapi": openapi,
        "field_schema": field_schema,
        "active_kinds": active_kinds,
        "provider_support": provider_support,
    }


def write_contract_bundle(out_dir: Path | None = None) -> dict[str, str]:
    bundle = build_contract_bundle()
    out_dir = out_dir or (ROOT / "contracts")
    out_dir.mkdir(parents=True, exist_ok=True)

    outputs = {
        "openapi.json": bundle["openapi"],
        "metadata-field-schema.json": bundle["field_schema"],
        "active-kinds.json": bundle["active_kinds"],
        "provider-support.json": bundle["provider_support"],
    }
    hashes: dict[str, str] = {}
    for filename, payload in outputs.items():
        text = _json_text(payload)
        data = text.encode("utf-8")
        (out_dir / filename).write_bytes(data)
        hashes[filename] = hashlib.sha256(data).hexdigest()

    manifest = {
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": bundle["generatedAt"],
        "coreCommit": bundle["coreCommit"],
        "openApiHash": hashes["openapi.json"],
        "fieldSchemaHash": hashes["metadata-field-schema.json"],
        "activeKindsHash": hashes["active-kinds.json"],
        "providerSupportHash": hashes["provider-support.json"],
    }
    manifest_text = _json_text(manifest)
    manifest_data = manifest_text.encode("utf-8")
    (out_dir / "contract-manifest.json").write_bytes(manifest_data)
    hashes["contract-manifest.json"] = hashlib.sha256(manifest_data).hexdigest()
    return hashes


def main() -> None:
    hashes = write_contract_bundle()
    out_dir = ROOT / "contracts"
    print(f"Wrote contract bundle -> {out_dir}")
    for name in sorted(hashes):
        print(f"  {name}: {hashes[name]}")


if __name__ == "__main__":
    main()
