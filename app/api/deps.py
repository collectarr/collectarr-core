from typing import Annotated

from fastapi import Depends, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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


async def get_admin_reader(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    db: DbSession,
) -> User | None:
    settings = get_settings()
    allow_unauthenticated_read = (
        not settings.admin_read_requires_auth_in_public
        or settings.environment in {"development", "test"}
    )
    if credentials is None and allow_unauthenticated_read:
        return None
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
    if user.role not in {UserRole.editor, UserRole.admin} and not user.is_admin:
        raise ApiHTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            code="admin_read_access_required",
            detail="Admin read access required",
        )
    return user


CurrentAdminReader = Annotated[User | None, Depends(get_admin_reader)]
