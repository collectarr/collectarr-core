from datetime import date

import pytest

from app.db.session import AsyncSessionLocal
from app.models import BookContribution, BookEdition, BookWork, Person
from app.worker.main import index_once


@pytest.mark.asyncio
async def test_index_once_eager_loads_book_edition_contributions():
    async with AsyncSessionLocal() as db:
        person = Person(name="J.R.R. Tolkien")
        db.add(person)
        await db.flush()

        work = BookWork(title="The Fellowship of the Ring")
        db.add(work)
        await db.flush()

        edition = BookEdition(
            work_id=work.id,
            display_title="The Fellowship of the Ring",
            publication_date=date(1954, 7, 29),
        )
        db.add(edition)
        await db.flush()
        db.add(
            BookContribution(
                edition_id=edition.id,
                person_id=person.id,
                role="author",
                sequence=1,
            )
        )
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
