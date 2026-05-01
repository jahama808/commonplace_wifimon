"""Auth tests — pure logic only, no DB required.

SPEC §5.1 four-case access resolution + bcrypt round-trip.
"""
from __future__ import annotations

from app.models.user import User
from app.services.auth import (
    hash_password,
    resolve_accessible_property_ids,
    verify_password,
)


def _user(**kw) -> User:
    u = User()
    u.id = kw.get("id", 1)
    u.username = kw.get("username", "alice")
    u.password_hash = kw.get("password_hash", "")
    u.is_active = kw.get("is_active", True)
    u.is_staff = kw.get("is_staff", False)
    u.is_superuser = kw.get("is_superuser", False)
    return u


class TestResolveAccessibleProperties:
    """SPEC §5.1 four cases."""

    def test_anonymous_has_no_access(self):
        # Anonymous user → no properties.
        assert resolve_accessible_property_ids(
            None, all_property_ids=[1, 2, 3], grants=[]
        ) == set()

    def test_inactive_user_has_no_access(self):
        u = _user(is_active=False)
        assert resolve_accessible_property_ids(
            u, all_property_ids=[1, 2, 3], grants=[1]
        ) == set()

    def test_superuser_sees_all(self):
        # Superuser → all properties.
        u = _user(is_superuser=True)
        assert resolve_accessible_property_ids(
            u, all_property_ids=[1, 2, 3], grants=[]
        ) == {1, 2, 3}

    def test_authenticated_no_grants_has_no_access(self):
        # Non-superuser with no grants → no properties.
        u = _user()
        assert resolve_accessible_property_ids(
            u, all_property_ids=[1, 2, 3], grants=[]
        ) == set()

    def test_authenticated_with_grants_sees_only_those(self):
        # Authenticated user with grants → only those properties.
        u = _user()
        assert resolve_accessible_property_ids(
            u, all_property_ids=[1, 2, 3, 4, 5], grants=[2, 5]
        ) == {2, 5}

    def test_grants_outside_all_property_ids(self):
        # If a grant references a deleted property, the resolver still
        # returns it — the caller's downstream join will filter it out
        # naturally. Defensive but not aggressive.
        u = _user()
        assert resolve_accessible_property_ids(
            u, all_property_ids=[1, 2], grants=[2, 99]
        ) == {2, 99}


class TestPasswordHashing:
    def test_hash_and_verify_round_trip(self):
        h = hash_password("hunter2")
        assert h != "hunter2"
        assert verify_password("hunter2", h)

    def test_wrong_password_rejected(self):
        h = hash_password("hunter2")
        assert verify_password("wrong", h) is False

    def test_empty_hash_rejected(self):
        assert verify_password("anything", "") is False

    def test_garbage_hash_rejected(self):
        # Should not raise — returns False for unverifiable hashes.
        assert verify_password("anything", "not-a-bcrypt-hash") is False
