import pytest

from app.db.session import AsyncSessionLocal
from app.models.canonical_catalog_items import CanonicalCatalogItem
from app.worker.main import index_once


@pytest.mark.asyncio
async def test_index_once_indexes_catalog_item_v1_documents():
    async with AsyncSessionLocal() as db:
        db.add(
            CanonicalCatalogItem(
                kind="book",
                title="The Fellowship of the Ring",
                sort_title="Fellowship of the Ring, The",
                identifier_search="",
                details={
                    "kind": "book",
                    "title": "The Fellowship of the Ring",
                    "creators": [{"name": "J.R.R. Tolkien"}],
                    "publication_date": {"year": 1954, "month": 7, "day": 29},
                },
            )
        )
        await db.commit()

    class RecordingSearch:
        def __init__(self) -> None:
            self.documents: list[dict] = []

        async def replace_documents(self, documents: list[dict]) -> None:
            self.documents = documents

    search = RecordingSearch()
    await index_once(search)

    book_documents = [
        document for document in search.documents if document["kind"] == "book"
    ]
    assert len(book_documents) == 1
    assert book_documents[0]["creators"] == ["J.R.R. Tolkien"]
