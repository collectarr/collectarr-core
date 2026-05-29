from collections.abc import Callable
from typing import Any
from uuid import UUID

from fastapi import status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiHTTPException
from app.models.base import UserRole
from app.models.user import User
from app.schemas.admin import UserResponse


class AdminUserService:
    def __init__(
        self,
        db: AsyncSession,
        audit_recorder: Callable[..., None],
    ) -> None:
        self.db = db
        self._audit_recorder = audit_recorder

    async def list_users(self) -> list[UserResponse]:
        result = await self.db.execute(select(User).order_by(User.created_at.desc()))
        return [UserResponse.model_validate(user) for user in result.scalars()]

    async def get_user(self, user_id: UUID) -> UserResponse:
        user = await self.db.get(User, user_id)
        if user is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="user_not_found",
                detail="User not found",
            )
        return UserResponse.model_validate(user)

    async def update_user(self, user_id: UUID, payload: Any) -> UserResponse:
        user = await self.db.get(User, user_id)
        if user is None:
            raise ApiHTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                code="user_not_found",
                detail="User not found",
            )
        if payload.role is not None:
            user.role = payload.role
            user.is_admin = payload.role == UserRole.admin
        if payload.is_active is not None:
            user.is_active = payload.is_active
        if payload.display_name is not None:
            user.display_name = payload.display_name
        await self.db.commit()
        await self.db.refresh(user)
        self._audit_recorder(
            "update_user",
            "user",
            entity_id=user.id,
            details=payload.model_dump(exclude_none=True),
        )
        await self.db.commit()
        return UserResponse.model_validate(user)