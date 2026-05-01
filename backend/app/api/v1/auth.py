"""Auth endpoints (SPEC §7)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_optional_user,
    login_user,
    logout_user,
)
from app.db.session import get_session
from app.models.user import User
from app.schemas.auth import CurrentUserResponse, LoginRequest
from app.services.auth import accessible_property_ids_for, authenticate

router = APIRouter(tags=["auth"], prefix="/auth")


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(
    payload: LoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> None:
    from app.core.config import settings

    if settings.USE_MOCK_DATA:
        # Mock mode has no users — the synthetic dev bypass user covers
        # the FE in dev. Always reject explicitly so callers don't think
        # they've authenticated against a real backend.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="login disabled in mock mode (USE_MOCK_DATA=true)",
        )

    user = await authenticate(session, payload.username, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid username or password",
        )
    login_user(request, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(request: Request) -> None:
    logout_user(request)


@router.get("/me", response_model=CurrentUserResponse)
async def me(
    user: User | None = Depends(get_optional_user),
    session: AsyncSession = Depends(get_session),
) -> CurrentUserResponse:
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated"
        )
    accessible = sorted(await accessible_property_ids_for(session, user))
    return CurrentUserResponse(
        id=user.id,
        username=user.username,
        email=user.email,
        is_active=user.is_active,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        accessible_property_ids=accessible,
    )
