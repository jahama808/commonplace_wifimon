"""Auth service — password hashing + per-property access resolution.

SPEC §5.1 resolution rules:
  • Anonymous user → no properties.
  • Superuser → all properties.
  • Authenticated non-superuser with no grants → no properties.
  • Authenticated user with grants → only those properties.

Pure logic for `resolve_accessible_property_ids` is testable without a DB.

Password verification accepts both bcrypt (the rebuild's native format) AND
Django's pbkdf2_sha256 — so users migrated from the legacy app can keep
logging in with their existing credentials. New users always get bcrypt.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from collections.abc import Iterable
from datetime import UTC

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.property import Property
from app.models.user import User, UserPropertyAccess

# bcrypt has a 72-byte ceiling; longer passwords get truncated. We treat that
# as "use the first 72 bytes" rather than refusing — the SHA-256 pre-hash dance
# is the alternative, but it makes us non-portable to other hashers, so accept
# the 72-byte trade for now.
_BCRYPT_MAX = 72


def _encode(plain: str) -> bytes:
    return plain.encode("utf-8")[:_BCRYPT_MAX]


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_encode(plain), bcrypt.gensalt()).decode("ascii")


def verify_password(plain: str, hashed: str) -> bool:
    """Verify a password against its stored hash.

    Recognizes two formats:
      • bcrypt — `$2{a,b,y}$<cost>$<22-char-salt><31-char-hash>` (native to this app)
      • Django pbkdf2_sha256 — `pbkdf2_sha256$<iter>$<salt>$<b64-hash>` (legacy)

    Returning False for any malformed input rather than raising — auth
    callers treat a False as "wrong password" and never inspect the reason.
    """
    if not hashed:
        return False
    try:
        if hashed.startswith("pbkdf2_sha256$"):
            return _verify_pbkdf2_sha256(plain, hashed)
        return bcrypt.checkpw(_encode(plain), hashed.encode("ascii"))
    except (ValueError, TypeError):
        return False


def _verify_pbkdf2_sha256(plain: str, hashed: str) -> bool:
    """Verify Django's `pbkdf2_sha256$<iter>$<salt>$<b64-hash>` format.

    Django produces a base64 of the raw PBKDF2-HMAC-SHA256 output. Standard
    iteration counts vary by Django version (260000 for Django 4, 600000+
    for newer). `iterations` is parsed from the hash string itself so this
    works across versions.
    """
    parts = hashed.split("$", 3)
    if len(parts) != 4 or parts[0] != "pbkdf2_sha256":
        return False
    try:
        iterations = int(parts[1])
    except ValueError:
        return False
    salt = parts[2]
    expected = base64.b64decode(parts[3])
    actual = hashlib.pbkdf2_hmac(
        "sha256", plain.encode("utf-8"), salt.encode("utf-8"), iterations, dklen=len(expected)
    )
    return hmac.compare_digest(expected, actual)


def resolve_accessible_property_ids(
    user: User | None, *, all_property_ids: Iterable[int], grants: Iterable[int]
) -> set[int]:
    """SPEC §5.1 four-case resolution.

    `all_property_ids` and `grants` are passed in (rather than queried) so
    this function is pure and testable without a session.
    """
    if user is None or not user.is_active:
        return set()
    if user.is_superuser:
        return set(all_property_ids)
    return set(grants)


async def authenticate(
    session: AsyncSession, username: str, password: str
) -> User | None:
    """Look up by username, verify password, return the user or None.

    Bumps `last_login` on success. Returns None for missing user, wrong
    password, or inactive accounts (no information leak between cases).
    """
    from datetime import datetime

    user = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()

    if user is None or not user.is_active:
        # Burn a hash anyway to prevent username-existence timing leaks.
        # Use a real bcrypt hash that won't verify (random plaintext).
        verify_password(password, "$2b$12$abcdefghijklmnopqrstuu1234567890abcdefghijklmnopqrstuvw")
        return None
    if not verify_password(password, user.password_hash):
        return None

    user.last_login = datetime.now(tz=UTC)
    await session.commit()
    return user


async def load_user(session: AsyncSession, user_id: int) -> User | None:
    """Cookie-resume path: pull the user from the DB by the id stored in the session."""
    return (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()


async def accessible_property_ids_for(
    session: AsyncSession, user: User | None
) -> set[int]:
    """Async wrapper around `resolve_accessible_property_ids` that does the
    needed lookups. Short-circuits the synthetic dev-bypass user (id == 0)
    so mock mode doesn't touch the DB."""
    if user is None or not user.is_active:
        return set()
    if user.id == 0:  # dev bypass — sees the world conceptually but no real ids
        return set()
    if user.is_superuser:
        rows = (await session.execute(select(Property.id))).scalars().all()
        return set(rows)
    grants = (
        await session.execute(
            select(UserPropertyAccess.property_id).where(UserPropertyAccess.user_id == user.id)
        )
    ).scalars().all()
    return set(grants)
