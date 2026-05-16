from fastapi import APIRouter, Depends

from app.api.deps import CurrentUser, DbSession
from app.core.rate_limit import auth_rate_limit
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse, UserResponse
from app.services.auth import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=201,
    dependencies=[Depends(auth_rate_limit)],
)
async def register(payload: RegisterRequest, db: DbSession) -> TokenResponse:
    return await AuthService(db).register(payload)


@router.post("/login", response_model=TokenResponse, dependencies=[Depends(auth_rate_limit)])
async def login(payload: LoginRequest, db: DbSession) -> TokenResponse:
    return await AuthService(db).login(payload)


@router.get("/me", response_model=UserResponse)
async def current_user(user: CurrentUser) -> UserResponse:
    return user
