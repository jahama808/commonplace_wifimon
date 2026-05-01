"""End-to-end auth tests against a real DB (SPEC §5.1).

Exercises the cookie session round-trip + the four-case access resolution
through `accessible_property_ids_for`. Uses the FastAPI app with
`USE_MOCK_DATA` flipped to false so the real auth path runs.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.config import settings
from app.models.property import Property
from app.models.user import User, UserPropertyAccess
from app.services.auth import accessible_property_ids_for, hash_password

pytestmark = pytest.mark.integration


@pytest.fixture
async def real_mode():
    """Flip `USE_MOCK_DATA` to False for the duration of the test, then
    restore it. Ensures the real auth path runs even when the rest of the
    suite runs in mock mode."""
    prev = settings.USE_MOCK_DATA
    settings.USE_MOCK_DATA = False
    try:
        yield
    finally:
        settings.USE_MOCK_DATA = prev


@pytest.fixture
async def client(real_mode):
    """Override `get_session` so the FastAPI app reads from the test DB
    rather than its own engine (which targets a different DSN)."""
    # We don't need to override anything — get_session uses _ensure_engine()
    # which respects DATABASE_URL. But the test DB is at TEST_DATABASE_URL.
    # Cleanest path: override DATABASE_URL via the conftest's session fixture
    # by overriding the dependency.
    import os

    from app.main import app

    test_db_url = os.environ["TEST_DATABASE_URL"]
    settings.DATABASE_URL = test_db_url

    # Reset the engine so it picks up the new URL
    from app.db import session as db_session_mod

    db_session_mod._engine = None
    db_session_mod._sessionmaker = None

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
    ) as c:
        yield c


async def _seed_user(db_session, *, username: str, password: str, **kw) -> User:
    user = User(
        username=username,
        password_hash=hash_password(password),
        is_active=kw.get("is_active", True),
        is_staff=kw.get("is_staff", False),
        is_superuser=kw.get("is_superuser", False),
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


# ──────────────────────────────────────────────────────────────────────────────
# Login / logout / me
# ──────────────────────────────────────────────────────────────────────────────


class TestLoginLogoutMe:
    async def test_login_with_valid_credentials_then_me_returns_user(
        self, db_session, client
    ):
        await _seed_user(db_session, username="alice", password="hunter2")

        r = await client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "hunter2"}
        )
        assert r.status_code == 204

        # The session cookie should now be set; /me returns the user
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 200
        body = r.json()
        assert body["username"] == "alice"
        assert body["is_superuser"] is False
        assert body["accessible_property_ids"] == []

    async def test_login_with_wrong_password_returns_401(self, db_session, client):
        await _seed_user(db_session, username="bob", password="correct")
        r = await client.post(
            "/api/v1/auth/login", json={"username": "bob", "password": "WRONG"}
        )
        assert r.status_code == 401

    async def test_login_unknown_user_returns_401(self, client):
        r = await client.post(
            "/api/v1/auth/login", json={"username": "nobody", "password": "x"}
        )
        assert r.status_code == 401

    async def test_inactive_user_cannot_login(self, db_session, client):
        await _seed_user(db_session, username="dormant", password="x", is_active=False)
        r = await client.post(
            "/api/v1/auth/login", json={"username": "dormant", "password": "x"}
        )
        assert r.status_code == 401

    async def test_me_without_cookie_is_401(self, client):
        r = await client.get("/api/v1/auth/me")
        assert r.status_code == 401

    async def test_logout_clears_session(self, db_session, client):
        await _seed_user(db_session, username="loggy", password="x")
        await client.post(
            "/api/v1/auth/login", json={"username": "loggy", "password": "x"}
        )
        # Logged in
        assert (await client.get("/api/v1/auth/me")).status_code == 200

        r = await client.post("/api/v1/auth/logout")
        assert r.status_code == 204

        # Logged out
        assert (await client.get("/api/v1/auth/me")).status_code == 401


# ──────────────────────────────────────────────────────────────────────────────
# Per-property access resolution (SPEC §5.1 four cases)
# ──────────────────────────────────────────────────────────────────────────────


class TestAccessibleProperties:
    async def test_anonymous_returns_empty(self, db_session):
        ids = await accessible_property_ids_for(db_session, None)
        assert ids == set()

    async def test_inactive_user_returns_empty(self, db_session):
        u = await _seed_user(db_session, username="zz", password="x", is_active=False)
        ids = await accessible_property_ids_for(db_session, u)
        assert ids == set()

    async def test_superuser_sees_all_real_properties(self, db_session):
        # Seed a few properties + a superuser
        for name in ("P1", "P2", "P3"):
            db_session.add(Property(name=name))
        await db_session.commit()
        super_u = await _seed_user(
            db_session, username="root", password="x", is_superuser=True
        )

        ids = await accessible_property_ids_for(db_session, super_u)
        # Should be exactly the IDs of the seeded properties
        all_ids = (await db_session.execute(select(Property.id))).scalars().all()
        assert ids == set(all_ids)
        assert len(ids) == 3

    async def test_authenticated_with_no_grants_returns_empty(self, db_session):
        for name in ("A", "B"):
            db_session.add(Property(name=name))
        await db_session.commit()
        plain = await _seed_user(db_session, username="u", password="x")

        ids = await accessible_property_ids_for(db_session, plain)
        assert ids == set()

    async def test_authenticated_with_grants_returns_only_granted(self, db_session):
        # Seed three properties; grant only two
        props = []
        for name in ("X", "Y", "Z"):
            p = Property(name=name)
            db_session.add(p)
            props.append(p)
        await db_session.commit()
        for p in props:
            await db_session.refresh(p)

        u = await _seed_user(db_session, username="u", password="x")
        db_session.add(UserPropertyAccess(user_id=u.id, property_id=props[0].id))
        db_session.add(UserPropertyAccess(user_id=u.id, property_id=props[2].id))
        await db_session.commit()

        ids = await accessible_property_ids_for(db_session, u)
        assert ids == {props[0].id, props[2].id}
