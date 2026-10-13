from uuid import uuid4

from app.db.session import AsyncSessionLocal
from app.models.catalog_music_item import MusicItem


async def seed_music() -> str:
    async with AsyncSessionLocal() as db:
        item = MusicItem(
            title="Music edition",
            artist="Artist",
            discs=[
                {
                    "id": str(uuid4()),
                    "disc_number": 1,
                    "format": "CD",
                    "format_family": "opticalDisc",
                    "recording_locations": [],
                    "sound_types": [],
                    "credits": [],
                    "tracks": [
                        {
                            "id": str(uuid4()),
                            "position": "1",
                            "position_order": 0,
                            "title": "Track",
                            "duration_ms": 180000,
                            "is_header": False,
                            "indent_level": 0,
                        }
                    ],
                }
            ],
        )
        db.add(item)
        await db.commit()
        return str(item.id)
