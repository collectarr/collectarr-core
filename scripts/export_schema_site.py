from __future__ import annotations

import json
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import CheckConstraint, Enum, ForeignKeyConstraint, Index, PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.schema import Column, Table

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import app.models  # noqa: F401
from app.models.base import Base

POSTGRES_DIALECT = postgresql.dialect()
DOCS_DIR = REPO_ROOT / "docs"
JSON_OUTPUT = DOCS_DIR / "schema-data.json"
MARKDOWN_OUTPUT = DOCS_DIR / "schema-full.md"

DOMAIN_SPECS: list[dict[str, Any]] = [
    {
        "id": "catalog",
        "title": "Catalog Spine",
        "description": "Core catalog hierarchy, releases, bundle composition, and series-to-series catalog links.",
        "tables": [
            "franchises",
            "series",
            "volumes",
            "items",
            "editions",
            "variants",
            "bundle_releases",
            "bundle_release_items",
            "series_relations",
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
            "story_arcs",
            "story_arc_items",
            "characters",
            "character_appearances",
            "tags",
            "entity_tags",
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

POLYMORPHIC_LINK_TABLES = {
    "entity_organizations",
    "entity_persons",
    "entity_tags",
    "external_provider_ids",
    "image_assets",
}

STATIC_NOTES = [
    "Polymorphic support tables such as entity_tags and external_provider_ids deliberately use entity_type + entity_id instead of concrete foreign keys for every target entity.",
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
    table_names = [name for name in domain["tables"] if name in tables_by_name]
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
            flags_suffix = f" {' '.join(flags)}" if flags else ""
            lines.append(f"    {mermaid_column_type(column)} {column['name']}{flags_suffix}")
        lines.append("  }")

    included = set(table_names)
    seen_edges: set[tuple[str, str, str]] = set()
    for table_name in table_names:
        table = tables_by_name[table_name]
        for foreign_key in table["constraints"]["foreign_keys"]:
            source_columns = ", ".join(foreign_key["columns"])
            for target in foreign_key["targets"]:
                target_table, _target_column = target.split(".", 1)
                if target_table in included:
                    edge = (target_table, table_name, source_columns)
                    if edge in seen_edges:
                        continue
                    seen_edges.add(edge)
                    left_cardinality = "||"
                    nullable = any(tables_by_name[table_name]["column_lookup"][column]["nullable"] for column in foreign_key["columns"])
                    if nullable:
                        left_cardinality = "o|"
                    lines.append(
                        f"  {mermaid_entity_name(target_table)} {left_cardinality}--o{{ {mermaid_entity_name(table_name)} : {source_columns}"
                    )
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

    return "\n".join(lines), external_refs


def format_markdown_value(value: str | None) -> str:
    if not value:
        return "-"
    return value.replace("|", "\\|")


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
            lines.append("")

    return "\n".join(lines).rstrip() + "\n"


def build_schema_data() -> dict[str, Any]:
    generated_at = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    tables = []
    enums: dict[str, dict[str, Any]] = {}
    relationships = []

    for table in Base.metadata.sorted_tables:
        unique_by_column = collect_column_uniques(table)
        indexes_by_column = collect_column_indexes(table)
        columns = [serialize_column(table, column, unique_by_column, indexes_by_column, enums) for column in table.columns]
        constraints = serialize_constraints(table)
        for foreign_key in constraints["foreign_keys"]:
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
        }
        tables.append(table_entry)

    tables_by_name = {table["name"]: table for table in tables}
    domains = []
    for domain in DOMAIN_SPECS:
        diagram, external_refs = build_domain_diagram(domain, tables_by_name)
        domains.append(
            {
                "id": domain["id"],
                "title": domain["title"],
                "description": domain["description"],
                "tables": [table_name for table_name in domain["tables"] if table_name in tables_by_name],
                "diagram": diagram,
                "external_references": external_refs,
            }
        )

    for table in tables:
        del table["column_lookup"]

    return {
        "generated_at": generated_at,
        "generator": "scripts/export_schema_site.py",
        "source_modules": [
            "app/models/base.py",
            "app/models/user.py",
            "app/models/canonical.py",
        ],
        "notes": STATIC_NOTES,
        "domains": domains,
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
    schema_data = build_schema_data()
    JSON_OUTPUT.write_text(json.dumps(schema_data, indent=2), encoding="utf-8")
    MARKDOWN_OUTPUT.write_text(render_markdown(schema_data), encoding="utf-8")
    print(f"Wrote {JSON_OUTPUT.relative_to(REPO_ROOT)}")
    print(f"Wrote {MARKDOWN_OUTPUT.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()