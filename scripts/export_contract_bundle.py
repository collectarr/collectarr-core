"""Export the versioned Core contract bundle for app sync.

Usage:
    python -m scripts.export_contract_bundle
"""

from __future__ import annotations

import argparse
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
from scripts.export_provider_golden_fixtures import (  # noqa: E402
    generate_envelope_schema,
    generate_golden_envelopes,
)

CONTRACT_VERSION = "2.0.0"

MUSIC_CATALOG_SCHEMAS = {
    "releaseGroup": "MusicReleaseGroupV1Response",
    "releaseSummary": "MusicReleaseSummaryV1Response",
    "release": "MusicReleaseV1Response",
    "medium": "MusicMediumV1Response",
    "track": "MusicTrackV1Response",
}


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _stable_payload(payload: Any) -> Any:
    """Remove export metadata that is expected to change on every run."""
    if isinstance(payload, dict):
        return {
            key: value for key, value in payload.items() if key not in {"generatedAt", "coreCommit"}
        }
    return payload


def _git_commit() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
    except OSError, subprocess.CalledProcessError:
        return "unknown"
    return result.stdout.strip() or "unknown"


def _music_catalog_contract(openapi: dict[str, Any], generated_at: str) -> dict[str, Any]:
    component_schemas = openapi.get("components", {}).get("schemas", {})
    included: set[str] = set()
    pending = list(MUSIC_CATALOG_SCHEMAS.values())

    while pending:
        name = pending.pop()
        if name in included:
            continue
        schema = component_schemas.get(name)
        if schema is None:
            raise KeyError(f"OpenAPI is missing Music response schema {name}")
        included.add(name)
        _collect_component_refs(schema, pending)

    definitions: dict[str, Any] = {}
    for name in sorted(included):
        definitions[name] = _rewrite_component_refs(component_schemas[name])

    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://schemas.collectarr.app/music-catalog/v1",
        "title": "Collectarr Music Catalog API Graph",
        "schemaVersion": 1,
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": generated_at,
        "coreCommit": _git_commit(),
        "roots": {
            name: {"$ref": f"#/$defs/{schema_name}"}
            for name, schema_name in MUSIC_CATALOG_SCHEMAS.items()
        },
        "$defs": definitions,
    }


def _collect_component_refs(value: Any, pending: list[str]) -> None:
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str) and ref.startswith("#/components/schemas/"):
            pending.append(ref.rsplit("/", 1)[-1])
        for child in value.values():
            _collect_component_refs(child, pending)
    elif isinstance(value, list):
        for child in value:
            _collect_component_refs(child, pending)


def _rewrite_component_refs(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if (
                key == "$ref"
                and isinstance(child, str)
                and child.startswith("#/components/schemas/")
            ):
                result[key] = child.replace("#/components/schemas/", "#/$defs/", 1)
            else:
                result[key] = _rewrite_component_refs(child)
        return result
    if isinstance(value, list):
        return [_rewrite_component_refs(child) for child in value]
    return value


def build_contract_bundle() -> dict[str, Any]:
    generated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    openapi = app.openapi()
    music_catalog = _music_catalog_contract(openapi, generated_at)
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
    provider_envelope_schema = generate_envelope_schema()
    golden_provider_envelopes = generate_golden_envelopes()
    return {
        "generatedAt": generated_at,
        "coreCommit": _git_commit(),
        "openapi": openapi,
        "music_catalog": music_catalog,
        "field_schema": field_schema,
        "active_kinds": active_kinds,
        "provider_support": provider_support,
        "provider_envelope_schema": provider_envelope_schema,
        "golden_provider_envelopes": golden_provider_envelopes,
    }


def build_contract_outputs() -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = build_contract_bundle()
    outputs = {
        "openapi.json": bundle["openapi"],
        "music-catalog-v1.json": bundle["music_catalog"],
        "metadata-field-schema.json": bundle["field_schema"],
        "active-kinds.json": bundle["active_kinds"],
        "provider-support.json": bundle["provider_support"],
        "provider-envelope-schema-v1.json": bundle["provider_envelope_schema"],
        "golden-provider-envelopes.json": bundle["golden_provider_envelopes"],
    }
    hashes: dict[str, str] = {}
    for filename, payload in outputs.items():
        text = _json_text(payload)
        hashes[filename] = hashlib.sha256(text.encode("utf-8")).hexdigest()

    manifest = {
        "contractVersion": CONTRACT_VERSION,
        "generatedAt": bundle["generatedAt"],
        "coreCommit": bundle["coreCommit"],
        "openApiHash": hashes["openapi.json"],
        "musicCatalogHash": hashes["music-catalog-v1.json"],
        "fieldSchemaHash": hashes["metadata-field-schema.json"],
        "activeKindsHash": hashes["active-kinds.json"],
        "providerSupportHash": hashes["provider-support.json"],
        "providerEnvelopeSchemaHash": hashes["provider-envelope-schema-v1.json"],
        "goldenProviderEnvelopesHash": hashes["golden-provider-envelopes.json"],
    }
    outputs["contract-manifest.json"] = manifest
    return outputs, hashes


def write_contract_bundle(out_dir: Path | None = None) -> dict[str, str]:
    out_dir = out_dir or (ROOT / "contracts")
    out_dir.mkdir(parents=True, exist_ok=True)
    outputs, hashes = build_contract_outputs()
    for filename, payload in outputs.items():
        (out_dir / filename).write_text(_json_text(payload), encoding="utf-8")
    manifest_data = (out_dir / "contract-manifest.json").read_bytes()
    hashes["contract-manifest.json"] = hashlib.sha256(manifest_data).hexdigest()
    return hashes


def check_contract_bundle(contracts_dir: Path | None = None) -> None:
    contracts_dir = contracts_dir or (ROOT / "contracts")
    generated, _ = build_contract_outputs()
    manifest_path = contracts_dir / "contract-manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise SystemExit(f"Cannot read contract manifest: {error}") from error

    hash_key_by_file = {
        "openapi.json": "openApiHash",
        "music-catalog-v1.json": "musicCatalogHash",
        "metadata-field-schema.json": "fieldSchemaHash",
        "active-kinds.json": "activeKindsHash",
        "provider-support.json": "providerSupportHash",
        "provider-envelope-schema-v1.json": "providerEnvelopeSchemaHash",
        "golden-provider-envelopes.json": "goldenProviderEnvelopesHash",
    }
    errors: list[str] = []
    for filename, generated_payload in generated.items():
        path = contracts_dir / filename
        try:
            checked_in = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            errors.append(f"{filename}: cannot read checked-in artifact ({error})")
            continue
        if filename == "contract-manifest.json":
            checked_stable = {
                key: value
                for key, value in _stable_payload(checked_in).items()
                if not key.endswith("Hash")
            }
            generated_stable = {
                key: value
                for key, value in _stable_payload(generated_payload).items()
                if not key.endswith("Hash")
            }
        else:
            checked_stable = _stable_payload(checked_in)
            generated_stable = _stable_payload(generated_payload)
        if checked_stable != generated_stable:
            errors.append(f"{filename}: differs from the generated contract")
        hash_key = hash_key_by_file.get(filename)
        if hash_key is not None:
            actual_hash = hashlib.sha256(path.read_bytes()).hexdigest()
            if manifest.get(hash_key) != actual_hash:
                errors.append(f"{filename}: hash does not match contract-manifest.json")

    if errors:
        raise SystemExit("Contract bundle is stale:\n- " + "\n- ".join(errors))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail if the checked-in contract bundle differs from current schemas",
    )
    args = parser.parse_args()
    if args.check:
        check_contract_bundle()
        print("Checked-in contract bundle matches the current Core schemas.")
        return

    hashes = write_contract_bundle()
    out_dir = ROOT / "contracts"
    print(f"Wrote contract bundle -> {out_dir}")
    for name in sorted(hashes):
        print(f"  {name}: {hashes[name]}")


if __name__ == "__main__":
    main()
