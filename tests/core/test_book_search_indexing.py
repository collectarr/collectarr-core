from uuid import uuid4

import pytest

from app.db.session import AsyncSessionLocal
from app.models.catalog_music_item import MusicItem
from app.worker.main import index_once


@pytest.mark.db
@pytest.mark.usefixtures("clean_database")
@pytest.mark.asyncio
async def test_index_once_eager_loads_flat_book_item_credits():
    async with AsyncSessionLocal() as db:
        item = MusicItem(
            title="The Fellowship of the Ring",
            artist="J.R.R. Tolkien",
            credits=[{"id": str(uuid4()), "name": "J.R.R. Tolkien", "role": "writer", "sequence": 1, "instruments": []}],
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

    book_documents = [document for document in search.documents if document["kind"] == "music"]
    assert len(book_documents) == 1
    assert book_documents[0]["creators"] == ["J.R.R. Tolkien"]
