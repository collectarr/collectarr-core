from __future__ import annotations

from types import SimpleNamespace
import pytest

from app.models.base import ItemKind
from app.services.facade import MetadataFacade


@pytest.mark.asyncio
async def test_metadata_facade_routes_search_to_composed_service() -> None:
    facade = MetadataFacade(db=SimpleNamespace())
    result = [SimpleNamespace(kind="book", title="The Hobbit")]

    async def fake_search(*args, **kwargs):
        assert kwargs["query"] == "hobbit"
        assert kwargs["kind"] == ItemKind.book
        return result

    facade.search_service.search = fake_search

    assert await facade.search(query="hobbit", kind=ItemKind.book) is result


def test_no_caller_imports_deprecated_metadata_module() -> None:
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[3]
    pattern = re.compile(r"from\s+app\.services\.metadata\s+import\s+MetadataService")

    offenders = []
    for path in root.rglob("*.py"):
        if path.name == "metadata.py":
            continue
        if "tests" in path.parts and path.parts[-3:] == ("tests", "services", "metadata"):
            continue
        text = path.read_text(encoding="utf-8")
        if pattern.search(text):
            offenders.append(path.relative_to(root).as_posix())

    assert offenders == []
