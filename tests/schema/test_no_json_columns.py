from sqlalchemy import JSON

from app.models import Base


def test_only_catalog_item_details_use_json_storage() -> None:
    json_columns = [
        f"{table.name}.{column.name}"
        for table in Base.metadata.tables.values()
        for column in table.columns
        if isinstance(column.type, JSON) or column.type.__class__.__name__.lower() == "jsonb"
    ]

    assert json_columns == ["catalog_items.details"]
