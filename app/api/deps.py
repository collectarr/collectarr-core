from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ApiHTTPException
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models.base import UserRole
from app.models.user import User
from app.repositories.users import UserRepository

bearer_scheme = HTTPBearer(auto_error=False)
DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User:
    if credentials is None:
        raise ApiHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="missing_bearer_token",
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user_id = decode_access_token(credentials.credentials)
    if user_id is None:
        raise ApiHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="invalid_bearer_token",
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await UserRepository(db).get_by_id(user_id)
    if user is None or not user.is_active:
        raise ApiHTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            code="user_not_found",
            detail="User not found",
        )
    if await UserRepository(db).reconcile_role_flags(user):
        await db.commit()
        await db.refresh(user)
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def get_current_admin(user: CurrentUser) -> User:
    if user.role != UserRole.admin and not user.is_admin:
        raise ApiHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="admin_required",
            detail="Admin access required",
        )
    return user


CurrentAdmin = Annotated[User, Depends(get_current_admin)]
