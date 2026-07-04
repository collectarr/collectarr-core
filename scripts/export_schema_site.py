from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from time import sleep
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    Enum,
    ForeignKeyConstraint,
    PrimaryKeyConstraint,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.schema import Column, Table

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app.models  # noqa: E402, F401
from app.models.base import Base  # noqa: E402

POSTGRES_DIALECT = postgresql.dialect()
DOCS_DIR = REPO_ROOT / "docs"
JSON_OUTPUT = DOCS_DIR / "schema-data.json"
MARKDOWN_OUTPUT = DOCS_DIR / "schema-full.md"
LEGACY_TABLE_NAMES = {"items", "editions", "variants"}
LEGACY_BRIDGE_TABLE_NAMES: set[str] = set()
HIDDEN_TABLE_NAMES = {
    "item" + "_kind_metadata",
    "item" + "_kind_metadata_taxonomies",
}
SOURCE_MODULES = [
    "app/models/base.py",
    "app/models/canonical_anime.py",
    "app/models/canonical_board_games.py",
    "app/models/canonical_books.py",
    "app/models/canonical_comics.py",
    "app/models/canonical_common.py",
    "app/models/canonical_games.py",
    "app/models/canonical_manga.py",
    "app/models/canonical_support.py",
    "app/models/canonical_video.py",
    "app/models/user.py",
]

DOMAIN_SPECS: list[dict[str, Any]] = [
    {
        "id": "catalog",
        "title": "Catalog Spine",
        "description": "Historical generic projection tables were removed from the canonical schema. All canonical metadata is kind-specific, and bundle composition is polymorphic.",
        "tables": [
            "bundle_releases",
            "bundle_release_components",
        ],
    },
    {
        "id": "editorial",
        "title": "Editorial and Taxonomy",
        "description": "People, organizations, characters, story arcs, and shared tagging tables.",
        "tables": [
            "organizations",
            "persons",
            "entity_organizations",
            "entity_persons",
            "entity_aliases",
            "entity_links",
            "story_arcs",
            "story_arc_items",
            "characters",
            "character_appearances",
            "tags",
            "entity_tags",
            "metadata_taxonomies",
        ],
    },
    {
        "id": "identity",
        "title": "Identity and Source Mapping",
        "description": "Users and external provider identifiers that map upstream ids back to catalog entities.",
        "tables": [
            "users",
            "external_provider_ids",
        ],
    },
    {
        "id": "operations",
        "title": "Images and Operations",
        "description": "Image storage, cache tracking, ingest jobs, admin audit trails, and proposal workflow tables.",
        "tables": [
            "image_assets",
            "image_cache_entries",
            "provider_ingest_jobs",
            "metadata_proposals",
            "admin_audit_logs",
        ],
    },
]

TABLE_TO_DOMAIN = {
    table_name: domain["id"]
    for domain in DOMAIN_SPECS
    for table_name in domain["tables"]
}

KIND_SPECS: list[dict[str, str]] = [
    {"id": "comic", "title": "Comics", "description": "Comic-specific schema slice."},
    {"id": "manga", "title": "Manga", "description": "Manga-specific schema slice."},
    {"id": "anime", "title": "Anime", "description": "Anime-specific schema slice."},
    {"id": "movie", "title": "Movies", "description": "Movie-specific schema slice."},
    {"id": "tv", "title": "TV", "description": "TV-specific schema slice."},
    {"id": "game", "title": "Games", "description": "Video game schema slice."},
    {"id": "boardgame", "title": "Board Games", "description": "Board game schema slice."},
    {"id": "book", "title": "Books", "description": "Books v1 work/edition schema slice."},
    {"id": "music", "title": "Music", "description": "Music schema slice."},
    {"id": "collection", "title": "Collections", "description": "Collection schema slice."},
]

KIND_SHARED_TABLES = [
    "entity_aliases",
    "entity_links",
    "organizations",
    "persons",
    "entity_organizations",
    "entity_persons",
    "tags",
    "entity_tags",
    "external_provider_ids",
    "provider_payload_snapshots",
]

KIND_SPECIFIC_TABLES: dict[str, list[str]] = {
    "comic": [
        "comic_volumes",
        "comic_works",
        "comic_issues",
        "comic_contributions",
        "comic_identifiers",
        "comic_series_memberships",
        "comic_story_arc_memberships",
        "comic_character_appearances",
        "characters",
        "character_appearances",
        "story_arcs",
        "story_arc_items",
    ],
    "manga": [
        "manga_works",
        "manga_chapters",
        "manga_contributions",
        "manga_identifiers",
        "manga_character_appearances",
        "characters",
        "character_appearances",
        "story_arcs",
        "story_arc_items",
    ],
    "anime": [
        "anime_series",
        "anime_episodes",
        "anime_contributions",
        "anime_identifiers",
        "anime_character_appearances",
    ],
    "movie": [
        "movie_works",
        "movie_releases",
        "movie_release_media",
        "movie_work_contributions",
        "movie_work_identifiers",
        "bundle_releases",
    ],
    "tv": [
        "tv_series",
        "tv_seasons",
        "tv_episodes",
        "tv_release_media",
        "tv_release_episode_map",
        "tv_release_contributions",
        "tv_release_identifiers",
        "bundle_releases",
    ],
    "game": [
        "game_works",
        "game_releases",
    ],
    "boardgame": [
        "boardgame_works",
        "boardgame_editions",
    ],
    "book": [
        "book_series",
        "book_works",
        "book_editions",
        "book_printings",
        "book_contributions",
        "book_identifiers",
        "book_series_memberships",
    ],
    "music": [
        "music_releases",
        "music_media",
        "music_tracks",
        "music_release_contributions",
        "music_release_identifiers",
        "bundle_releases",
    ],
    "collection": [
        "bundle_releases",
    ],
}

POLYMORPHIC_LINK_TABLES = {
    "entity_aliases",
    "entity_links",
    "entity_organizations",
    "entity_persons",
    "entity_tags",
    "external_provider_ids",
    "image_assets",
}

STATIC_NOTES = [
    "Polymorphic support tables such as entity_aliases, entity_links, entity_tags, and external_provider_ids deliberately use entity_type + entity_id instead of concrete foreign keys for every target entity.",
    "Historical generic projection tables were removed from the canonical schema. All canonical metadata is kind-specific.",
    "The viewer below is generated from SQLAlchemy metadata, so columns, enums, indexes, foreign keys, unique constraints, and defaults stay aligned with the model layer.",
    "For migration history and any constraints introduced outside model declarations, cross-check the Alembic revisions in alembic/versions.",
]


def compile_type(column: Column[Any]) -> str:
    try:
        return str(column.type.compile(dialect=POSTGRES_DIALECT))
    except Exception:
        return str(column.type)


def format_default(default: Any) -> str | None:
    if default is None:
        return None

    arg = getattr(default, "arg", default)
    if callable(arg):
        module = getattr(arg, "__module__", None)
        qualname = getattr(arg, "__qualname__", getattr(arg, "__name__", None))
        if module and qualname:
            return f"python:{module}.{qualname}"
        return repr(arg)
    if isinstance(arg, str):
        return arg
    return str(arg)


def enum_values(enum_type: Enum) -> list[str]:
    if enum_type.enum_class is not None:
        return [str(member.value) for member in enum_type.enum_class]
    return [str(value) for value in enum_type.enums]


def collect_column_uniques(table: Table) -> dict[str, str | None]:
    result: dict[str, str | None] = {}
    for constraint in table.constraints:
        if isinstance(constraint, UniqueConstraint) and len(constraint.columns) == 1:
            column_name = next(iter(constraint.columns)).name
            result[column_name] = constraint.name
    for column in table.columns:
        if column.unique and column.name not in result:
            result[column.name] = None
    return result


def collect_column_indexes(table: Table) -> dict[str, list[str]]:
    result: dict[str, list[str]] = defaultdict(list)
    for index in table.indexes:
        if len(index.columns) == 1:
            column_name = next(iter(index.columns)).name
            result[column_name].append(index.name)
    for column in table.columns:
        if column.index and not result[column.name]:
            result[column.name].append(column.name)
    return result


def serialize_foreign_key(column_name: str, foreign_key: Any) -> dict[str, Any]:
    target_column = foreign_key.column
    return {
        "column": column_name,
        "target_table": target_column.table.name,
        "target_column": target_column.name,
        "target": f"{target_column.table.name}.{target_column.name}",
        "ondelete": foreign_key.ondelete,
        "onupdate": foreign_key.onupdate,
        "name": foreign_key.constraint.name,
    }


def serialize_column(
    table: Table,
    column: Column[Any],
    unique_by_column: dict[str, str | None],
    indexes_by_column: dict[str, list[str]],
    enums: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    foreign_keys = [serialize_foreign_key(column.name, foreign_key) for foreign_key in column.foreign_keys]
    column_type = column.type
    enum_name: str | None = None
    if isinstance(column_type, Enum):
        enum_name = column_type.name or f"enum_{table.name}_{column.name}"
        enums[enum_name] = {
            "name": enum_name,
            "values": enum_values(column_type),
        }

    return {
        "name": column.name,
        "type": compile_type(column),
        "nullable": column.nullable,
        "primary_key": column.primary_key,
        "unique": column.name in unique_by_column,
        "unique_constraint": unique_by_column.get(column.name),
        "index": bool(indexes_by_column.get(column.name)) or bool(column.index),
        "indexes": indexes_by_column.get(column.name, []),
        "default": format_default(column.default),
        "server_default": format_default(column.server_default),
        "autoincrement": bool(column.autoincrement),
        "foreign_keys": foreign_keys,
        "enum": enum_name,
    }


def serialize_constraints(table: Table) -> dict[str, Any]:
    primary_key = next(
        (constraint for constraint in table.constraints if isinstance(constraint, PrimaryKeyConstraint)),
        None,
    )
    uniques = [
        {
            "name": constraint.name,
            "columns": [column.name for column in constraint.columns],
        }
        for constraint in table.constraints
        if isinstance(constraint, UniqueConstraint)
    ]
    checks = [
        {
            "name": constraint.name,
            "sqltext": str(constraint.sqltext),
        }
        for constraint in table.constraints
        if isinstance(constraint, CheckConstraint)
    ]
    foreign_keys = [
        {
            "name": constraint.name,
            "columns": [element.parent.name for element in constraint.elements],
            "targets": [f"{element.column.table.name}.{element.column.name}" for element in constraint.elements],
            "ondelete": next((element.ondelete for element in constraint.elements if element.ondelete), None),
            "onupdate": next((element.onupdate for element in constraint.elements if element.onupdate), None),
        }
        for constraint in table.constraints
        if isinstance(constraint, ForeignKeyConstraint)
    ]
    indexes = [
        {
            "name": index.name,
            "columns": [column.name for column in index.columns],
            "unique": index.unique,
        }
        for index in sorted(table.indexes, key=lambda current: current.name or "")
    ]
    existing_unique_sets = {tuple(constraint["columns"]) for constraint in uniques}
    for column in table.columns:
        if column.unique and (column.name,) not in existing_unique_sets:
            uniques.append(
                {
                    "name": f"uq_{table.name}_{column.name}",
                    "columns": [column.name],
                }
            )
    return {
        "primary_key": {
            "name": primary_key.name if primary_key is not None else None,
            "columns": [column.name for column in primary_key.columns] if primary_key is not None else [],
        },
        "foreign_keys": foreign_keys,
        "unique_constraints": uniques,
        "check_constraints": checks,
        "indexes": indexes,
    }


def mermaid_entity_name(table_name: str) -> str:
    return table_name.upper()


def mermaid_column_type(column: dict[str, Any]) -> str:
    normalized = "".join(character if character.isalnum() else "_" for character in column["type"])
    return normalized.strip("_") or "TYPE"


def build_domain_diagram(domain: dict[str, Any], tables_by_name: dict[str, dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    table_names = [name for name in domain["tables"] if name in tables_by_name and name not in HIDDEN_TABLE_NAMES]
    lines = ["erDiagram"]
    external_refs: list[dict[str, Any]] = []

    for table_name in table_names:
        table = tables_by_name[table_name]
        lines.append(f"  {mermaid_entity_name(table_name)} {{")
        for column in table["columns"]:
            flags = []
            if column["primary_key"]:
                flags.append("PK")
            if column["foreign_keys"]:
                flags.append("FK")
            if column["unique"]:
                flags.append("UK")
            # Mermaid ER attributes require multiple key constraints to be
            # comma-separated (e.g. "PK, FK"); a space-separated list like
            # "FK UK" is a parse error.
            flags_suffix = f" {', '.join(flags)}" if flags else ""
            lines.append(f"    {mermaid_column_type(column)} {column['name']}{flags_suffix}")
        lines.append("  }")

    included = set(table_names)
    # Merge multiple foreign keys between the same pair of entities into a
    # single relationship line. Emitting parallel edges (e.g. SERIES has both
    # source_series_id and target_series_id pointing at SERIES_RELATIONS) makes
    # Mermaid's ER layout fail and renders an empty diagram.
    edges: dict[tuple[str, str], dict[str, Any]] = {}
    edge_order: list[tuple[str, str]] = []
    for table_name in table_names:
        table = tables_by_name[table_name]
        for foreign_key in table["constraints"]["foreign_keys"]:
            source_columns = ", ".join(foreign_key["columns"])
            nullable = any(
                tables_by_name[table_name]["column_lookup"][column]["nullable"]
                for column in foreign_key["columns"]
            )
            for target in foreign_key["targets"]:
                target_table, _target_column = target.split(".", 1)
                if target_table in HIDDEN_TABLE_NAMES:
                    continue
                if target_table in included:
                    key = (target_table, table_name)
                    if key not in edges:
                        edges[key] = {"labels": [], "nullable": False}
                        edge_order.append(key)
                    if source_columns not in edges[key]["labels"]:
                        edges[key]["labels"].append(source_columns)
                    edges[key]["nullable"] = edges[key]["nullable"] or nullable
                else:
                    external_refs.append(
                        {
                            "from_table": table_name,
                            "from_columns": foreign_key["columns"],
                            "to_table": target_table,
                            "targets": foreign_key["targets"],
                            "ondelete": foreign_key["ondelete"],
                            "onupdate": foreign_key["onupdate"],
                        }
                    )

    for target_table, table_name in edge_order:
        info = edges[(target_table, table_name)]
        left_cardinality = "o|" if info["nullable"] else "||"
        label = ", ".join(info["labels"])
        # Mermaid relationship labels containing separators must be quoted.
        rendered_label = f'"{label}"' if ("," in label or " " in label) else label
        lines.append(
            f"  {mermaid_entity_name(target_table)} {left_cardinality}--o{{ "
            f"{mermaid_entity_name(table_name)} : {rendered_label}"
        )

    return "\n".join(lines), external_refs


def format_markdown_value(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("|", "\\|")


def build_kind_tables(kind_id: str, tables_by_name: dict[str, dict[str, Any]]) -> list[str]:
    requested = [*KIND_SHARED_TABLES, *(KIND_SPECIFIC_TABLES.get(kind_id) or [])]
    seen: set[str] = set()
    ordered: list[str] = []
    for table_name in requested:
        if table_name not in tables_by_name:
            continue
        if table_name in seen:
            continue
        seen.add(table_name)
        ordered.append(table_name)
    return ordered


def render_markdown(data: dict[str, Any]) -> str:
    lines = [
        "# Collectarr Core Full Schema Snapshot",
        "",
        f"Generated from SQLAlchemy metadata on `{data['generated_at']}`.",
        "",
        "This file is generated by `python scripts/export_schema_site.py`.",
        "",
        "## Notes",
        "",
    ]
    for note in data["notes"]:
        lines.append(f"- {note}")

    lines.extend(["", "## Enums", ""])
    for enum_name, enum_data in data["enums"].items():
        lines.append(f"### {enum_name}")
        lines.append("")
        for value in enum_data["values"]:
            lines.append(f"- `{value}`")
        lines.append("")

    lines.extend(["## Kind-focused Views", ""])
    for kind in data.get("kinds", []):
        lines.append(f"### {kind['title']}")
        lines.append("")
        lines.append(kind["description"])
        lines.append("")
        lines.append("Tables:")
        lines.append("")
        for table_name in kind["tables"]:
            lines.append(f"- `{table_name}`")
        lines.append("")

    tables_by_name = {table["name"]: table for table in data["tables"]}
    for domain in data["domains"]:
        lines.append(f"## {domain['title']}")
        lines.append("")
        lines.append(domain["description"])
        lines.append("")
        for table_name in domain["tables"]:
            table = tables_by_name[table_name]
            lines.append(f"### {table_name}")
            lines.append("")
            lines.append("| Column | Type | Nullable | PK | Unique | Indexed | Default | Server default | References |")
            lines.append("|---|---|---|---|---|---|---|---|---|")
            for column in table["columns"]:
                refs = ", ".join(reference["target"] for reference in column["foreign_keys"]) or "-"
                lines.append(
                    "| {name} | {type} | {nullable} | {pk} | {unique} | {index} | {default} | {server_default} | {refs} |".format(
                        name=column["name"],
                        type=format_markdown_value(column["type"]),
                        nullable="yes" if column["nullable"] else "no",
                        pk="yes" if column["primary_key"] else "no",
                        unique="yes" if column["unique"] else "no",
                        index="yes" if column["index"] else "no",
                        default=format_markdown_value(column["default"]),
                        server_default=format_markdown_value(column["server_default"]),
                        refs=format_markdown_value(refs),
                    )
                )
            lines.append("")
            lines.append("#### Constraints")
            lines.append("")
            primary_key = table["constraints"]["primary_key"]
            lines.append(f"- Primary key: `{', '.join(primary_key['columns']) or '-'}`")
            if table["constraints"]["unique_constraints"]:
                for constraint in table["constraints"]["unique_constraints"]:
                    lines.append(
                        f"- Unique `{constraint['name'] or '(anonymous)'}`: `{', '.join(constraint['columns'])}`"
                    )
            else:
                lines.append("- Unique constraints: none")
            if table["constraints"]["indexes"]:
                for index in table["constraints"]["indexes"]:
                    lines.append(
                        f"- Index `{index['name']}` ({'unique' if index['unique'] else 'non-unique'}): `{', '.join(index['columns'])}`"
                    )
            else:
                lines.append("- Indexes: none")
            if table["constraints"]["check_constraints"]:
                for check in table["constraints"]["check_constraints"]:
                    lines.append(
                        f"- Check `{check['name'] or '(anonymous)'}`: `{check['sqltext']}`"
                    )
            else:
                lines.append("- Check constraints: none")
            if table["constraints"]["foreign_keys"]:
                for foreign_key in table["constraints"]["foreign_keys"]:
                    lines.append(
                        f"- Foreign key `{foreign_key['name'] or '(anonymous)'}`: `{', '.join(foreign_key['columns'])}` -> `{', '.join(foreign_key['targets'])}`"
                    )
            else:
                lines.append("- Foreign keys: none")
            if table["polymorphic_note"]:
                lines.append(f"- Note: {table['polymorphic_note']}")
            if table["legacy_projection_note"]:
                lines.append(f"- Note: {table['legacy_projection_note']}")
            if table["legacy_bridge_note"]:
                lines.append(f"- Note: {table['legacy_bridge_note']}")
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_schema_data() -> dict[str, Any]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    tables = []
    enums: dict[str, dict[str, Any]] = {}
    relationships = []

    for table in Base.metadata.sorted_tables:
        if table.name in HIDDEN_TABLE_NAMES:
            continue
        unique_by_column = collect_column_uniques(table)
        indexes_by_column = collect_column_indexes(table)
        columns = [serialize_column(table, column, unique_by_column, indexes_by_column, enums) for column in table.columns]
        constraints = serialize_constraints(table)
        for foreign_key in constraints["foreign_keys"]:
            if any(target.split(".", 1)[0] in HIDDEN_TABLE_NAMES for target in foreign_key["targets"]):
                continue
            relationships.append(
                {
                    "from_table": table.name,
                    "from_columns": foreign_key["columns"],
                    "to_targets": foreign_key["targets"],
                    "name": foreign_key["name"],
                    "ondelete": foreign_key["ondelete"],
                    "onupdate": foreign_key["onupdate"],
                }
            )
        table_entry = {
            "name": table.name,
            "domain": TABLE_TO_DOMAIN.get(table.name, "misc"),
            "columns": columns,
            "column_lookup": {column["name"]: column for column in columns},
            "constraints": constraints,
            "polymorphic_note": (
                "Uses entity_type + entity_id as a polymorphic reference; target integrity is enforced in application logic rather than with a single database foreign key."
                if table.name in POLYMORPHIC_LINK_TABLES
                else None
            ),
            "legacy_projection_note": (
                "Legacy compatibility / projection table for migrated kinds; canonical writes should target kind-specific tables."
                if table.name in LEGACY_TABLE_NAMES
                else None
            ),
            "legacy_bridge_note": (
                "Bundle composition is polymorphic through entity_type + entity_id."
                if table.name in LEGACY_BRIDGE_TABLE_NAMES
                else None
            ),
        }
        tables.append(table_entry)

    tables_by_name = {table["name"]: table for table in tables}
    domains = []
    assigned_tables: set[str] = set()
    for domain in DOMAIN_SPECS:
        domain_tables = [table_name for table_name in domain["tables"] if table_name in tables_by_name]
        diagram, external_refs = build_domain_diagram(domain, tables_by_name)
        domains.append(
            {
                "id": domain["id"],
                "title": domain["title"],
                "description": domain["description"],
                "tables": domain_tables,
                "diagram": diagram,
                "external_references": external_refs,
            }
        )
        assigned_tables.update(domain_tables)

    kind_tables = {
        table_name
        for kind in KIND_SPECS
        for table_name in build_kind_tables(kind["id"], tables_by_name)
    }
    remaining_tables = sorted(
        table_name
        for table_name in tables_by_name
        if table_name not in assigned_tables and table_name not in kind_tables
    )
    if remaining_tables:
        misc_domain = {
            "id": "misc",
            "title": "Miscellaneous",
            "description": "Tables not yet mapped to a primary domain bucket.",
            "tables": remaining_tables,
        }
        diagram, external_refs = build_domain_diagram(misc_domain, tables_by_name)
        domains.append(
            {
                "id": misc_domain["id"],
                "title": misc_domain["title"],
                "description": misc_domain["description"],
                "tables": remaining_tables,
                "diagram": diagram,
                "external_references": external_refs,
            }
        )

    kinds = []
    for kind in KIND_SPECS:
        kind_tables = build_kind_tables(kind["id"], tables_by_name)
        if not kind_tables:
            continue
        kind_diagram, kind_external_refs = build_domain_diagram(
            {
                "id": f"kind-{kind['id']}",
                "title": kind["title"],
                "description": kind["description"],
                "tables": kind_tables,
            },
            tables_by_name,
        )
        kinds.append(
            {
                "id": kind["id"],
                "title": kind["title"],
                "description": kind["description"],
                "tables": kind_tables,
                "diagram": kind_diagram,
                "external_references": kind_external_refs,
            }
        )
        assigned_tables.update(kind_tables)

    for table in tables:
        del table["column_lookup"]

    return {
        "generated_at": generated_at,
        "generator": "scripts/export_schema_site.py",
        "source_modules": SOURCE_MODULES,
        "notes": [
            *STATIC_NOTES,
            "Legacy generic tables (`items`, `editions`, `variants`) are no longer part of the canonical schema or interactive view.",
        ],
        "domains": domains,
        "kinds": kinds,
        "tables": tables,
        "enums": dict(sorted(enums.items())),
        "relationships": relationships,
        "summary": {
            "tables": len(tables),
            "columns": sum(len(table["columns"]) for table in tables),
            "foreign_keys": sum(len(table["constraints"]["foreign_keys"]) for table in tables),
            "indexes": sum(len(table["constraints"]["indexes"]) for table in tables),
            "unique_constraints": sum(len(table["constraints"]["unique_constraints"]) for table in tables),
            "check_constraints": sum(len(table["constraints"]["check_constraints"]) for table in tables),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Export the interactive schema site.")
    parser.add_argument("--watch", action="store_true", help="Rebuild when model or migration files change.")
    parser.add_argument("--interval", type=float, default=1.0, help="Polling interval for --watch mode.")
    args = parser.parse_args()

    def write_outputs() -> None:
        schema_data = build_schema_data()
        JSON_OUTPUT.write_text(json.dumps(schema_data, indent=2), encoding="utf-8")
        MARKDOWN_OUTPUT.write_text(render_markdown(schema_data), encoding="utf-8")
        print(f"Wrote {JSON_OUTPUT.relative_to(REPO_ROOT)}")
        print(f"Wrote {MARKDOWN_OUTPUT.relative_to(REPO_ROOT)}")

    if not args.watch:
        write_outputs()
        return

    watched_roots = [REPO_ROOT / "app" / "models", REPO_ROOT / "alembic" / "versions"]
    watched_files = {REPO_ROOT / "scripts" / "export_schema_site.py", REPO_ROOT / "scripts" / "export_openapi.py"}

    def snapshot() -> dict[Path, float]:
        current: dict[Path, float] = {}
        for path in watched_files:
            if path.exists():
                current[path] = path.stat().st_mtime
        for root in watched_roots:
            if not root.exists():
                continue
            for path in root.rglob("*.py"):
                current[path] = path.stat().st_mtime
        return current

    print("Watching schema inputs for changes. Press Ctrl+C to stop.")
    last_snapshot = snapshot()
    write_outputs()
    while True:
        sleep(args.interval)
        current_snapshot = snapshot()
        if current_snapshot != last_snapshot:
            last_snapshot = current_snapshot
            write_outputs()


if __name__ == "__main__":
    main()