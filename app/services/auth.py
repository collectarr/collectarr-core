from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.errors import ApiHTTPException
from app.core.security import create_access_token, hash_password, verify_password
from app.models.base import UserRole
from app.repositories.users import UserRepository
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.users = UserRepository(db)

    async def register(self, payload: RegisterRequest) -> TokenResponse:
        email = str(payload.email).lower()
        existing = await self.users.get_by_email(email)
        if existing:
            raise ApiHTTPException(
                status_code=status.HTTP_409_CONFLICT,
                code="email_already_registered",
                detail="Email already registered",
            )

        settings = get_settings()
        is_bootstrap_admin = email in {admin.lower() for admin in settings.bootstrap_admin_emails}
        user = await self.users.create(
            email=email,
            password_hash=hash_password(payload.password),
            display_name=payload.display_name,
            is_admin=is_bootstrap_admin,
            role=UserRole.admin if is_bootstrap_admin else UserRole.viewer,
        )
        await self.db.commit()
        return TokenResponse(access_token=create_access_token(user.id), user=user)

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.users.get_by_email(str(payload.email))
        if user is None or not verify_password(payload.password, user.password_hash):
            raise ApiHTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                code="invalid_credentials",
                detail="Invalid email or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise ApiHTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                code="user_inactive",
                detail="User is inactive",
            )
        if await self.users.reconcile_role_flags(user):
            await self.db.commit()
            await self.db.refresh(user)
        return TokenResponse(access_token=create_access_token(user.id), user=user)
