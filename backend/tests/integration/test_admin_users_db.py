"""Integration tests for the admin user-management service."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.property import Property
from app.models.user import User, UserPropertyAccess
from app.schemas.admin import UserCreate
from app.services import admin as svc
from app.services.auth import verify_password

pytestmark = pytest.mark.integration


class TestCreateUser:
    async def test_creates_user_with_hashed_password(self, db_session):
        u = await svc.create_user(
            db_session,
            UserCreate(username="alice", password="hunter22pw"),
            granted_by_user_id=None,
        )
        assert u.id is not None
        assert u.username == "alice"
        assert u.is_staff is False
        assert u.is_superuser is False
        assert u.is_active is True
        assert verify_password("hunter22pw", u.password_hash) is True
        # Stored hash must not equal the plaintext — bcrypt prefix check
        assert u.password_hash.startswith("$2")

    async def test_creates_grants_for_property_ids(self, db_session):
        p1 = Property(name="P1")
        p2 = Property(name="P2")
        db_session.add_all([p1, p2])
        await db_session.flush()

        u = await svc.create_user(
            db_session,
            UserCreate(
                username="bob", password="bobsecret1", property_ids=[p1.id, p2.id]
            ),
            granted_by_user_id=None,
        )
        rows = (
            await db_session.execute(
                select(UserPropertyAccess.property_id).where(
                    UserPropertyAccess.user_id == u.id
                )
            )
        ).scalars().all()
        assert sorted(rows) == sorted([p1.id, p2.id])

    async def test_duplicate_username_raises_value_error(self, db_session):
        await svc.create_user(
            db_session,
            UserCreate(username="dup", password="firstpass1"),
            granted_by_user_id=None,
        )
        with pytest.raises(ValueError, match="username already taken"):
            await svc.create_user(
                db_session,
                UserCreate(username="dup", password="secondpass1"),
                granted_by_user_id=None,
            )

    async def test_unknown_property_id_raises_lookup_error(self, db_session):
        with pytest.raises(LookupError, match="property"):
            await svc.create_user(
                db_session,
                UserCreate(
                    username="carol", password="carolpass1", property_ids=[999999]
                ),
                granted_by_user_id=None,
            )


class TestResetUserPassword:
    async def test_changes_hash_and_only_hash(self, db_session):
        u = await svc.create_user(
            db_session,
            UserCreate(username="reset_me", password="oldpassword1"),
            granted_by_user_id=None,
        )
        old_hash = u.password_hash
        old_username = u.username

        await svc.reset_user_password(db_session, u, "newpassword2")

        assert u.password_hash != old_hash
        assert u.username == old_username
        assert verify_password("newpassword2", u.password_hash) is True
        assert verify_password("oldpassword1", u.password_hash) is False
