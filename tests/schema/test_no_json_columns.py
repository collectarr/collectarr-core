from sqlalchemy import JSON

from app.models import Base


def test_canonical_schema_has_no_json_columns() -> None:
    json_columns = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, JSON) or column.type.__class__.__name__.lower() == "jsonb"
    ]

    assert json_columns == []
