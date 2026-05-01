"""Integration tests for the admin service against a real Postgres."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.common_area import LocationType
from app.models.property import Property
from app.schemas.admin import (
    CommonAreaCreate,
    CommonAreaUpdate,
    PropertyCreate,
    PropertyUpdate,
)
from app.services import admin as svc

pytestmark = pytest.mark.integration


class TestPropertyCrud:
    async def test_create_then_read(self, db_session):
        p = await svc.create_property(
            db_session, PropertyCreate(name="Test 1", address="addr")
        )
        assert p.id is not None
        loaded = await svc.get_property(db_session, p.id)
        assert loaded is not None
        assert loaded.name == "Test 1"
        assert loaded.address == "addr"

    async def test_update(self, db_session):
        p = await svc.create_property(db_session, PropertyCreate(name="To Update"))
        updated = await svc.update_property(
            db_session, p, PropertyUpdate(address="new addr")
        )
        assert updated.address == "new addr"

    async def test_delete_cascades_to_common_areas(self, db_session):
        p = await svc.create_property(db_session, PropertyCreate(name="Doomed"))
        await svc.create_common_area(
            db_session,
            p,
            CommonAreaCreate(
                location_name="Lobby",
                network_id="DOOM-001",
                location_type="indoor",
            ),
        )
        await svc.delete_property(db_session, p)
        rows = (await db_session.execute(select(Property).where(Property.name == "Doomed"))).all()
        assert rows == []
        # Cascade: the common area should be gone too.
        from app.models.common_area import CommonArea

        rows = (
            await db_session.execute(
                select(CommonArea).where(CommonArea.network_id == "DOOM-001")
            )
        ).all()
        assert rows == []


class TestCommonAreaCrud:
    async def test_create_with_island_coercion(self, db_session):
        p = await svc.create_property(db_session, PropertyCreate(name="Big Isl Place"))
        ca = await svc.create_common_area(
            db_session,
            p,
            CommonAreaCreate(
                location_name="Lobby",
                network_id="BIG-001",
                island="big-island",  # wire-form → Island.HAWAII
                location_type="outdoor",
            ),
        )
        assert ca.id is not None
        # `big-island` ↔ Island.HAWAII (SPEC §4.1)
        from app.models.common_area import Island

        assert ca.island == Island.HAWAII
        assert ca.location_type == LocationType.OUTDOOR

    async def test_update_partial(self, db_session):
        p = await svc.create_property(db_session, PropertyCreate(name="P"))
        ca = await svc.create_common_area(
            db_session, p,
            CommonAreaCreate(
                location_name="Lobby", network_id="N1", location_type="indoor"
            ),
        )
        ca = await svc.update_common_area(
            db_session, ca,
            CommonAreaUpdate(description="moved location"),
        )
        assert ca.description == "moved location"
        # Untouched fields stay
        assert ca.location_name == "Lobby"


class TestAccessGrants:
    async def test_grant_is_idempotent(self, db_session):
        from app.models.user import User
        from app.services.auth import hash_password

        user = User(username="u", password_hash=hash_password("x"), is_active=True)
        db_session.add(user)
        await db_session.flush()
        prop = await svc.create_property(db_session, PropertyCreate(name="P"))

        g1 = await svc.grant_property_access(db_session, user.id, prop.id)
        g2 = await svc.grant_property_access(db_session, user.id, prop.id)
        # Second call returns the existing grant rather than raising on the unique
        assert g1.id == g2.id

    async def test_revoke_returns_false_when_no_grant(self, db_session):
        result = await svc.revoke_property_access(db_session, 99999, 99999)
        assert result is False
