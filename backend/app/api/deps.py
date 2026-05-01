"""Reusable FastAPI dependencies.

  • `get_current_user`           — pulls the user from the session cookie or 401
  • `get_optional_user`          — same, but returns None instead of 401
  • `require_superuser`          — current user must be `is_superuser`
  • `require_staff`              — current user must be `is_staff` or superuser
  • `require_property_access`    — `Depends(require_property_access)` 403s on mismatch

Per SPEC §5.1: every endpoint that accepts a `property_id` MUST go through
`require_property_access` so the check can't be forgotten.
"""
from __future__ import annotations

from fastapi import Depends, HTTPException, Path, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_session
from app.models.user import User
from app.services.auth import accessible_property_ids_for, load_user

_SESSION_USER_KEY = "user_id"


def _dev_bypass_user() -> User:
    """Synthetic in-memory user used when `USE_MOCK_DATA` is True so the
    frontend can run without a real DB or login UI. NEVER persisted."""
    u = User()
    u.id = 0
    u.username = "dev"
    u.email = "dev@local"
    u.is_active = True
    u.is_staff = True
    u.is_superuser = True  # dev bypass sees everything
    u.password_hash = ""
    return u


async def get_optional_user(
    request: Request, session: AsyncSession = Depends(get_session)
) -> User | None:
    user_id = request.session.get(_SESSION_USER_KEY)
    if user_id is None:
        if settings.USE_MOCK_DATA:
            return _dev_bypass_user()
        return None
    user = await load_user(session, int(user_id))
    if user is None or not user.is_active:
        return None
    return user


async def get_current_user(
    user: User | None = Depends(get_optional_user),
) -> User:
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
    return user


async def require_staff(user: User = Depends(get_current_user)) -> User:
    if not (user.is_staff or user.is_superuser):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="staff only")
    return user


async def require_superuser(user: User = Depends(get_current_user)) -> User:
    if not user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="superuser only")
    return user


async def require_property_access(
    property_id: int = Path(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> int:
    """Returns the property_id when access is granted; 403s otherwise.

    Use as `Depends(require_property_access)` — the path parameter is
    auto-detected, no extra wiring needed.
    """
    accessible = await accessible_property_ids_for(session, user)
    if property_id not in accessible:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="no access to this property")
    return property_id


def login_user(request: Request, user: User) -> None:
    request.session[_SESSION_USER_KEY] = user.id


def logout_user(request: Request) -> None:
    request.session.pop(_SESSION_USER_KEY, None)
