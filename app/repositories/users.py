from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import UserRole
from app.models.user import User


class UserRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email.lower()))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id) -> User | None:
        return await self.db.get(User, user_id)

    async def create(
        self,
        email: str,
        password_hash: str,
        display_name: str | None,
        is_admin: bool = False,
        role: UserRole | None = None,
    ) -> User:
        resolved_role = role or (UserRole.admin if is_admin else UserRole.viewer)
        user = User(
            email=email.lower(),
            password_hash=password_hash,
            display_name=display_name,
            is_admin=resolved_role == UserRole.admin,
            role=resolved_role,
        )
        self.db.add(user)
        await self.db.flush()
        return user

    async def reconcile_role_flags(self, user: User) -> bool:
        changed = False

        if user.role == UserRole.admin and not user.is_admin:
            user.is_admin = True
            changed = True
        elif user.is_admin and user.role != UserRole.admin:
            user.role = UserRole.admin
            changed = True
        elif not user.is_admin and user.role == UserRole.admin:
            user.role = UserRole.viewer
            changed = True

        return changed
