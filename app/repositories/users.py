from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User, UserCollection


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id) -> User | None:
        return await self.db.get(User, user_id)

    async def create(
        self, email: str, password_hash: str, display_name: str | None, is_admin: bool = False
    ) -> User:
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            display_name=display_name,
            is_admin=is_admin,
        )
        self.db.add(user)
        await self.db.flush()
        self.db.add(UserCollection(user_id=user.id, name="Default"))
        await self.db.flush()
        return user
