from datetime import date

import pytest

from app.db.session import AsyncSessionLocal
from app.models import Person
from app.models.catalog_book_item import BookItem
from app.worker.main import index_once


@pytest.mark.asyncio
async def test_index_once_eager_loads_flat_book_item_credits():
    async with AsyncSessionLocal() as db:
        person = Person(name="J.R.R. Tolkien")
        db.add(person)
        await db.flush()

        item = BookItem(
            title="The Fellowship of the Ring",
            details={
                "release_date": date(1954, 7, 29).isoformat(),
                "creators": [
                    {
                        "name": "J.R.R. Tolkien",
                        "role": "author",
                        "sequence": 1,
                    }
                ],
            },
        )
        db.add(item)
        await db.commit()

    class RecordingSearch:
        def __init__(self):
            self.documents = []

        async def index_documents(self, documents):
            self.documents.extend(documents)

    search = RecordingSearch()
    await index_once(search)

    book_documents = [document for document in search.documents if document["kind"] == "book"]
    assert len(book_documents) == 1
    assert book_documents[0]["creators"] == ["J.R.R. Tolkien"]
