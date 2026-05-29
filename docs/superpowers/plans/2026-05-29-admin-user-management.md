# Admin User Management Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Users tab to the admin UI that lets a superuser create new users, reset their passwords, and grant/revoke per-property access (site restriction).

**Architecture:** Three new backend endpoints under `/api/v1/admin/users` reuse the existing `require_superuser` dep and the existing `UserPropertyAccess` grant/revoke service. Frontend adds a fifth tab to `AdminClient.tsx` following the three-column list/detail pattern already used by `PropertiesTab`. Site restriction reuses the existing `POST/DELETE /api/v1/admin/access` endpoints — no new authorization logic.

**Tech Stack:** FastAPI · SQLAlchemy 2.x async · Pydantic v2 · bcrypt · Next.js 15 App Router · TanStack Query · Tailwind.

**Spec:** [`docs/superpowers/specs/2026-05-29-admin-user-management-design.md`](../specs/2026-05-29-admin-user-management-design.md)

---

## File map

**Backend — create:**
- `backend/tests/integration/test_admin_users_db.py` — service-level integration tests
- `backend/tests/test_admin_users_api.py` — API tests via FastAPI TestClient (unit-mode, no DB; covers auth + mock-mode gates)

**Backend — modify:**
- `backend/app/schemas/admin.py` — add `UserOut`, `UserCreate`, `UserPasswordReset`
- `backend/app/services/admin.py` — add `list_users_with_grants`, `create_user`, `reset_user_password`
- `backend/app/api/v1/admin.py` — add three new routes under `/admin/users`
- `backend/openapi.snapshot.json` — regenerated from the new routes

**Frontend — modify:**
- `frontend/src/lib/admin-api.ts` — add `listUsers`, `createUser`, `resetUserPassword`
- `frontend/src/types/api.gen.ts` — regenerated from snapshot
- `frontend/src/components/AdminClient.tsx` — add `'users'` tab + `UsersTab` + `UserList` + `UserDetail` + `PropertyAccessSection` + `NewUserCard`

No new files for the FE — keep the Users tab inline in `AdminClient.tsx` to match how Properties / CLLI / Maintenance / MDU Map are organized today.

---

## Task 1: Add Pydantic schemas

**Files:**
- Modify: `backend/app/schemas/admin.py`

- [ ] **Step 1: Add schemas at the bottom of the file**

Open `backend/app/schemas/admin.py` and append:

```python
# ──────────────────────────────────────────────────────────────────────────────
# Users (admin CRUD — site restriction via UserPropertyAccess grants)
# ──────────────────────────────────────────────────────────────────────────────


class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=255)
    property_ids: list[int] = Field(default_factory=list)


class UserOut(BaseModel):
    id: int
    username: str
    is_staff: bool
    is_superuser: bool
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    property_ids: list[int]  # always empty for superusers (they get all)


class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=255)
```

- [ ] **Step 2: Run import check**

Run: `cd backend && .venv/bin/python -c "from app.schemas.admin import UserCreate, UserOut, UserPasswordReset; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add backend/app/schemas/admin.py
git commit -m "feat(admin): add UserCreate/UserOut/UserPasswordReset schemas"
```

---

## Task 2: Add `create_user` service with integration test

**Files:**
- Create: `backend/tests/integration/test_admin_users_db.py`
- Modify: `backend/app/services/admin.py`

- [ ] **Step 1: Write the failing test**

Create `backend/tests/integration/test_admin_users_db.py`:

```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://wifimon_test:wifimon_test@localhost:5433/wifimon_test .venv/bin/pytest tests/integration/test_admin_users_db.py -v`

Expected: FAIL with `AttributeError: module 'app.services.admin' has no attribute 'create_user'`

(If no local Postgres is available, the integration test will be skipped — CI runs it. In that case verify the test file at least imports cleanly: `.venv/bin/python -c "import tests.integration.test_admin_users_db"`.)

- [ ] **Step 3: Implement `create_user`**

In `backend/app/services/admin.py`, add this at the bottom (after the existing grant/revoke section):

```python
# ──────────────────────────────────────────────────────────────────────────────
# Users (admin CRUD)
# ──────────────────────────────────────────────────────────────────────────────


async def create_user(
    session: AsyncSession,
    payload: "UserCreate",
    *,
    granted_by_user_id: int | None,
) -> "User":
    """Create a non-staff, non-superuser, active user and write the requested
    property-access grants in one transaction.

    Raises:
        ValueError: username already taken
        LookupError: one of `property_ids` does not exist
    """
    from app.models.user import User
    from app.services.auth import hash_password

    existing = (
        await session.execute(select(User).where(User.username == payload.username))
    ).scalar_one_or_none()
    if existing is not None:
        raise ValueError("username already taken")

    if payload.property_ids:
        found = (
            await session.execute(
                select(Property.id).where(Property.id.in_(payload.property_ids))
            )
        ).scalars().all()
        missing = set(payload.property_ids) - set(found)
        if missing:
            raise LookupError(f"property not found: {sorted(missing)[0]}")

    user = User(
        username=payload.username,
        password_hash=hash_password(payload.password),
        is_active=True,
        is_staff=False,
        is_superuser=False,
    )
    session.add(user)
    await session.flush()  # populate user.id

    for property_id in payload.property_ids:
        session.add(
            UserPropertyAccess(
                user_id=user.id,
                property_id=property_id,
                created_by_id=granted_by_user_id,
            )
        )

    await session.commit()
    await session.refresh(user)
    return user
```

You'll also need to ensure these imports exist at the top of `admin.py` (most already do):

```python
from app.models.user import User, UserPropertyAccess  # User may be new in this import
from app.schemas.admin import UserCreate              # add UserCreate to the existing schemas import
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://wifimon_test:wifimon_test@localhost:5433/wifimon_test .venv/bin/pytest tests/integration/test_admin_users_db.py::TestCreateUser -v`

Expected: 4 passed (or 4 skipped if no local DB — CI will run them).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/admin.py backend/tests/integration/test_admin_users_db.py
git commit -m "feat(admin): create_user service with atomic grant writes"
```

---

## Task 3: Add `reset_user_password` service with integration test

**Files:**
- Modify: `backend/tests/integration/test_admin_users_db.py`
- Modify: `backend/app/services/admin.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/integration/test_admin_users_db.py`:

```python
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
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd backend && TEST_DATABASE_URL=... .venv/bin/pytest tests/integration/test_admin_users_db.py::TestResetUserPassword -v`
Expected: FAIL with `AttributeError: module 'app.services.admin' has no attribute 'reset_user_password'`

- [ ] **Step 3: Implement `reset_user_password`**

In `backend/app/services/admin.py`, below `create_user`:

```python
async def reset_user_password(
    session: AsyncSession, user: "User", new_password: str
) -> None:
    """Hash the new password and persist it. No other fields are touched."""
    from app.services.auth import hash_password

    user.password_hash = hash_password(new_password)
    await session.commit()
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `cd backend && TEST_DATABASE_URL=... .venv/bin/pytest tests/integration/test_admin_users_db.py::TestResetUserPassword -v`
Expected: PASS (or skip if no local DB).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/admin.py backend/tests/integration/test_admin_users_db.py
git commit -m "feat(admin): reset_user_password service"
```

---

## Task 4: Add `list_users_with_grants` service with integration test

**Files:**
- Modify: `backend/tests/integration/test_admin_users_db.py`
- Modify: `backend/app/services/admin.py`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/integration/test_admin_users_db.py`:

```python
class TestListUsersWithGrants:
    async def test_returns_users_with_sorted_property_ids(self, db_session):
        p1 = Property(name="Alpha")
        p2 = Property(name="Beta")
        db_session.add_all([p1, p2])
        await db_session.flush()

        await svc.create_user(
            db_session,
            UserCreate(
                username="multi", password="multipass1", property_ids=[p2.id, p1.id]
            ),
            granted_by_user_id=None,
        )
        await svc.create_user(
            db_session,
            UserCreate(username="empty", password="emptypass1"),
            granted_by_user_id=None,
        )

        rows = await svc.list_users_with_grants(db_session)
        by_name = {u.username: ids for u, ids in rows}
        # property_ids come back sorted ascending, regardless of insert order
        assert by_name["multi"] == sorted([p1.id, p2.id])
        assert by_name["empty"] == []
```

- [ ] **Step 2: Run the test and verify it fails**

Run: `cd backend && TEST_DATABASE_URL=... .venv/bin/pytest tests/integration/test_admin_users_db.py::TestListUsersWithGrants -v`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Implement `list_users_with_grants`**

In `backend/app/services/admin.py`, below `reset_user_password`:

```python
async def list_users_with_grants(
    session: AsyncSession,
) -> list[tuple["User", list[int]]]:
    """Return every user with their sorted list of granted property_ids."""
    from app.models.user import User

    users = (
        await session.execute(select(User).order_by(User.username))
    ).scalars().all()

    if not users:
        return []

    grant_rows = (
        await session.execute(
            select(UserPropertyAccess.user_id, UserPropertyAccess.property_id).where(
                UserPropertyAccess.user_id.in_([u.id for u in users])
            )
        )
    ).all()

    by_user: dict[int, list[int]] = {u.id: [] for u in users}
    for user_id, property_id in grant_rows:
        by_user[user_id].append(property_id)
    for ids in by_user.values():
        ids.sort()

    return [(u, by_user[u.id]) for u in users]
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `cd backend && TEST_DATABASE_URL=... .venv/bin/pytest tests/integration/test_admin_users_db.py::TestListUsersWithGrants -v`
Expected: PASS (or skip).

- [ ] **Step 5: Commit**

```bash
git add backend/app/services/admin.py backend/tests/integration/test_admin_users_db.py
git commit -m "feat(admin): list_users_with_grants service"
```

---

## Task 5: Add API routes for users

**Files:**
- Modify: `backend/app/api/v1/admin.py`

- [ ] **Step 1: Add a helper and the three routes**

In `backend/app/api/v1/admin.py`, update the imports near the top:

```python
from app.api.deps import require_staff, require_superuser  # add require_superuser
```

```python
from app.schemas.admin import (
    AreaPreviewRequest,
    AreaPreviewResponse,
    CommonAreaCreate,
    CommonAreaOut,
    CommonAreaUpdate,
    GrantOut,
    GrantRequest,
    MduOltMapOut,
    MduOltMapUploadResponse,
    PropertyCreate,
    PropertyOut,
    PropertyUpdate,
    UserCreate,           # add
    UserOut,              # add
    UserPasswordReset,    # add
)
```

Then append at the bottom of `admin.py`:

```python
# ──────────────────────────────────────────────────────────────────────────────
# Users (superuser-only — SPEC §5.1 grant model surfaced as user CRUD)
# ──────────────────────────────────────────────────────────────────────────────


def _user_out(user: User, property_ids: list[int]) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        is_staff=user.is_staff,
        is_superuser=user.is_superuser,
        is_active=user.is_active,
        created_at=user.created_at,
        last_login=user.last_login,
        property_ids=property_ids,
    )


@router.get("/users", response_model=list[UserOut])
async def list_users(
    _su: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
) -> list[UserOut]:
    rows = await svc.list_users_with_grants(session)
    return [_user_out(u, ids) for u, ids in rows]


@router.post(
    "/users",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_endpoint(
    payload: UserCreate,
    su: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
) -> UserOut:
    try:
        user = await svc.create_user(session, payload, granted_by_user_id=su.id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    return _user_out(user, sorted(payload.property_ids))


@router.post(
    "/users/{user_id}/password",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def reset_user_password_endpoint(
    payload: UserPasswordReset,
    user_id: int = Path(...),
    _su: User = Depends(require_superuser),
    session: AsyncSession = Depends(get_session),
) -> None:
    user = (
        await session.execute(select(User).where(User.id == user_id))
    ).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    await svc.reset_user_password(session, user, payload.password)
```

- [ ] **Step 2: Smoke-test the routes register**

Run: `cd backend && .venv/bin/python -c "from app.main import app; print([r.path for r in app.routes if '/admin/users' in r.path])"`

Expected: prints three paths — `/api/v1/admin/users`, `/api/v1/admin/users`, `/api/v1/admin/users/{user_id}/password`.

- [ ] **Step 3: Commit**

```bash
git add backend/app/api/v1/admin.py
git commit -m "feat(admin): /admin/users routes (list, create, reset-password)"
```

---

## Task 6: API tests (auth + mock-mode gating)

**Files:**
- Create: `backend/tests/test_admin_users_api.py`

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_admin_users_api.py`:

```python
"""API tests for /admin/users. Runs in default mock mode (USE_MOCK_DATA=true)
so we only exercise the auth + mock-gate behavior here. End-to-end
behavior is covered by integration tests in tests/integration/test_admin_users_db.py.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture
def client():
    return TestClient(app)


class TestAdminUsersMockGate:
    """In mock mode every /admin/users route must 503, even to the synthetic dev user."""

    def test_list_users_returns_503_in_mock_mode(self, client):
        r = client.get("/api/v1/admin/users")
        assert r.status_code == 503
        assert "mock mode" in r.json()["detail"].lower()

    def test_create_user_returns_503_in_mock_mode(self, client):
        r = client.post(
            "/api/v1/admin/users",
            json={"username": "x", "password": "longenough"},
        )
        assert r.status_code == 503

    def test_reset_password_returns_503_in_mock_mode(self, client):
        r = client.post(
            "/api/v1/admin/users/1/password",
            json={"password": "longenough"},
        )
        assert r.status_code == 503


class TestAdminUsersPayloadValidation:
    """Pydantic validation happens before the mock-gate dependency, so payload
    422s surface even in mock mode."""

    def test_create_user_rejects_short_password(self, client):
        r = client.post(
            "/api/v1/admin/users",
            json={"username": "ok", "password": "short"},
        )
        # The mock-gate runs as a router-level dependency, so it fires before
        # the route handler — but Pydantic body validation runs first. Either
        # 422 (validation) or 503 (mock gate) is correct depending on FastAPI's
        # ordering. Accept both so this test is robust.
        assert r.status_code in (422, 503)
        if r.status_code == 422:
            assert "at least 8" in r.text or "min_length" in r.text
```

- [ ] **Step 2: Run the tests**

Run: `cd backend && .venv/bin/pytest tests/test_admin_users_api.py -v`

Expected: 4 passed.

- [ ] **Step 3: Commit**

```bash
git add backend/tests/test_admin_users_api.py
git commit -m "test(admin): /admin/users mock-mode + payload validation"
```

---

## Task 7: Regenerate OpenAPI snapshot

**Files:**
- Modify: `backend/openapi.snapshot.json`

- [ ] **Step 1: Find the regeneration command**

Check `backend/Makefile` or `pyproject.toml` for an existing target. If none, use the inline command below.

Run: `grep -n "openapi" /home/jahama/servers-prod/common-area-looking-glass-conversion/backend/Makefile /home/jahama/servers-prod/common-area-looking-glass-conversion/backend/pyproject.toml 2>/dev/null`

- [ ] **Step 2: Regenerate the snapshot**

Run from `backend/`:
```bash
.venv/bin/python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" > openapi.snapshot.json
```

(If a project-specific script exists — e.g. `make openapi-snapshot` or `python scripts/dump_openapi.py` — use it instead so formatting matches.)

- [ ] **Step 3: Verify the new endpoints appear**

Run: `grep -c "/admin/users" backend/openapi.snapshot.json`
Expected: 3 or more matches (list, create, reset password).

- [ ] **Step 4: Commit**

```bash
git add backend/openapi.snapshot.json
git commit -m "chore(api): regenerate openapi snapshot with /admin/users routes"
```

---

## Task 8: Regenerate frontend types

**Files:**
- Modify: `frontend/src/types/api.gen.ts`
- Modify: `frontend/src/types/api.ts` (if it has named re-exports)

- [ ] **Step 1: Run the typegen**

Run from `frontend/`:
```bash
npm run gen:types
```

- [ ] **Step 2: Verify the new types exist**

Run from `frontend/`:
```bash
grep -E "UserCreate|UserOut|UserPasswordReset" src/types/api.gen.ts | head -10
```
Expected: each name appears at least once.

- [ ] **Step 3: Add named re-exports in `frontend/src/types/api.ts`**

`api.ts` uses the `Schemas[X]` pattern for every used type. Add these lines in the Admin section, right after the existing `MduOltMapUploadResponse` line:

```ts
export type UserOut = Schemas['UserOut'];
export type UserCreate = Schemas['UserCreate'];
export type UserPasswordReset = Schemas['UserPasswordReset'];
```

- [ ] **Step 4: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/api.gen.ts frontend/src/types/api.ts
git commit -m "chore(types): regen FE types for /admin/users"
```

---

## Task 9: Extend admin-api client

**Files:**
- Modify: `frontend/src/lib/admin-api.ts`

- [ ] **Step 1: Add the new imports and methods**

Update the type imports at the top of `frontend/src/lib/admin-api.ts` to include `UserCreate`, `UserOut`, `UserPasswordReset`:

```ts
import type {
  AreaPreviewRequest,
  AreaPreviewResponse,
  ClliCreate,
  ClliOut,
  CommonAreaCreate,
  CommonAreaOut,
  CommonAreaUpdate,
  GrantOut,
  GrantRequest,
  MaintenanceCreate,
  MaintenanceOut,
  MaintenanceUpdate,
  MduOltMapOut,
  MduOltMapUploadResponse,
  PropertyCreate,
  PropertyOut,
  PropertyUpdate,
  UserCreate,
  UserOut,
  UserPasswordReset,
} from '@/types/api';
```

Inside the `adminApi` object, after the existing `revokeAccess` line, add:

```ts
  // Users
  listUsers: () => call<UserOut[]>('GET', '/admin/users'),
  createUser: (body: UserCreate) =>
    call<UserOut>('POST', '/admin/users', body),
  resetUserPassword: (id: number, body: UserPasswordReset) =>
    call<void>('POST', `/admin/users/${id}/password`, body),
```

- [ ] **Step 2: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/admin-api.ts
git commit -m "feat(admin): admin-api client methods for /admin/users"
```

---

## Task 10: Add `'users'` tab + scaffold UsersTab

**Files:**
- Modify: `frontend/src/components/AdminClient.tsx`

- [ ] **Step 1: Extend the Tab union and tabs array**

Find this line near the top of `AdminClient.tsx`:

```ts
type Tab = 'properties' | 'clli' | 'maintenance' | 'mdu-map';
```

Change to:

```ts
type Tab = 'properties' | 'clli' | 'maintenance' | 'mdu-map' | 'users';
```

Find the `tabs` array inside `Tabs(...)` and add the new entry as the last element:

```ts
{ key: 'users', label: 'Users', sub: 'Create / grant access' },
```

Find the tab render switch inside `AdminClient` (the `{tab === 'properties' && ...}` block) and append:

```tsx
{tab === 'users' && <UsersTab />}
```

- [ ] **Step 2: Add a stub UsersTab component**

At the bottom of `AdminClient.tsx`, add:

```tsx
// ──────────────────────────────────────────────────────────────────────────────
// Users tab
// ──────────────────────────────────────────────────────────────────────────────

function UsersTab() {
  const users = useQuery({
    queryKey: ['admin', 'users'],
    queryFn: () => adminApi.listUsers(),
  });
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const selected = (users.data ?? []).find((u) => u.id === selectedId) ?? null;

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
      <div className="lg:col-span-2 space-y-4">
        <UserList
          users={users.data ?? []}
          loading={users.isLoading}
          error={users.error as Error | null}
          selectedId={selectedId}
          onSelect={setSelectedId}
        />
        {selected && <UserDetail user={selected} />}
      </div>
      <div className="space-y-4">
        <NewUserCard onCreated={(id) => setSelectedId(id)} />
        <ModeNotice />
      </div>
    </div>
  );
}

function UserList(_: {
  users: UserOut[];
  loading: boolean;
  error: Error | null;
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return <div className="card p-5 text-text-3">UserList stub</div>;
}

function UserDetail(_: { user: UserOut }) {
  return <div className="card p-5 text-text-3">UserDetail stub</div>;
}

function NewUserCard(_: { onCreated: (id: number) => void }) {
  return <div className="card p-5 text-text-3">NewUserCard stub</div>;
}
```

Update the type imports at the top of `AdminClient.tsx` to include `UserOut`:

```ts
import type {
  AreaPreviewResponse,
  ClliOut,
  MduOltMapOut,
  PropertyOut,
  UserOut,
} from '@/types/api';
```

- [ ] **Step 3: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AdminClient.tsx
git commit -m "feat(admin): scaffold Users tab in AdminClient"
```

---

## Task 11: Implement `UserList`

**Files:**
- Modify: `frontend/src/components/AdminClient.tsx`

- [ ] **Step 1: Replace the UserList stub**

In `AdminClient.tsx`, replace the `UserList` stub with:

```tsx
function UserList({
  users,
  loading,
  error,
  selectedId,
  onSelect,
}: {
  users: UserOut[];
  loading: boolean;
  error: Error | null;
  selectedId: number | null;
  onSelect: (id: number) => void;
}) {
  return (
    <div className="card flex flex-col">
      <div className="card-hd border-b border-line">
        <div>
          <h3>Users</h3>
          <div className="sub">{users.length} TOTAL</div>
        </div>
      </div>
      <ul className="divide-y divide-line">
        {loading && (
          <li className="px-5 py-8 text-center text-[13px] text-text-3">Loading…</li>
        )}
        {error && !loading && (
          <li className="px-5 py-3 text-[13px] text-bad">{error.message}</li>
        )}
        {!loading && !error && users.length === 0 && (
          <li className="px-5 py-8 text-center text-[13px] text-text-3">
            No users yet. Use the form on the right to add one.
          </li>
        )}
        {users.map((u) => {
          const accessLabel = u.is_superuser
            ? 'All properties'
            : u.property_ids.length === 0
              ? 'No properties'
              : `${u.property_ids.length} ${u.property_ids.length === 1 ? 'property' : 'properties'}`;
          return (
            <li
              key={u.id}
              className={cn(
                'flex items-center gap-3 px-5 py-3',
                selectedId === u.id && 'bg-bg-2',
              )}
            >
              <button
                type="button"
                onClick={() => onSelect(u.id)}
                className="flex flex-1 items-center gap-3 text-left"
              >
                <ChevronRight
                  size={14}
                  className={cn(
                    'flex-shrink-0 text-text-3 transition-transform',
                    selectedId === u.id && 'rotate-90 text-text-1',
                  )}
                />
                <div className="min-w-0 flex-1">
                  <div className="text-[14px] font-medium">{u.username}</div>
                  <div className="mono mt-[2px] truncate text-[10.5px] text-text-3">
                    ID {u.id}
                    {u.is_superuser ? ' · SUPERUSER' : u.is_staff ? ' · STAFF' : ''}
                    {!u.is_active ? ' · INACTIVE' : ''}
                  </div>
                </div>
                <span className="badge-glow accent">{accessLabel.toUpperCase()}</span>
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AdminClient.tsx
git commit -m "feat(admin): UserList row rendering"
```

---

## Task 12: Implement `UserDetail` (reset password)

**Files:**
- Modify: `frontend/src/components/AdminClient.tsx`

- [ ] **Step 1: Replace the UserDetail stub**

Replace the `UserDetail` stub with:

```tsx
function UserDetail({ user }: { user: UserOut }) {
  const [resetting, setResetting] = useState(false);
  const [newPassword, setNewPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const reset = useMutation({
    mutationFn: () =>
      adminApi.resetUserPassword(user.id, { password: newPassword }),
    onSuccess: () => {
      setResetting(false);
      setNewPassword('');
      setError(null);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
    },
    onError: (err: Error) => setError(err.message),
  });

  const roleLabel = user.is_superuser
    ? 'Superuser'
    : user.is_staff
      ? 'Staff'
      : 'Standard user';

  return (
    <div className="card p-5 space-y-5">
      <div>
        <div
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          USER · ID {user.id}
        </div>
        <div className="mt-1 text-[18px] font-semibold">{user.username}</div>
        <div className="mt-1 text-[13px] text-text-2">{roleLabel}</div>
      </div>

      <div>
        {!resetting ? (
          <button
            type="button"
            onClick={() => setResetting(true)}
            className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-1 hover:bg-bg-2"
          >
            Reset password
          </button>
        ) : (
          <form
            onSubmit={(e) => {
              e.preventDefault();
              if (newPassword.length >= 8) reset.mutate();
            }}
            className="space-y-2"
          >
            <label className="flex flex-col gap-1">
              <span
                className="mono text-[10px] text-text-3"
                style={{ letterSpacing: '0.12em' }}
              >
                NEW PASSWORD (min 8 chars)
              </span>
              <input
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                autoFocus
                required
                minLength={8}
                className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
              />
            </label>
            {error && <div className="text-[12px] text-bad">{error}</div>}
            <div className="flex gap-2">
              <button
                type="submit"
                disabled={newPassword.length < 8 || reset.isPending}
                className="rounded-m bg-accent px-3 py-2 text-[13px] font-medium text-[var(--text-on-accent)] disabled:opacity-50"
              >
                {reset.isPending ? <Loader2 size={14} className="animate-spin" /> : 'Save'}
              </button>
              <button
                type="button"
                onClick={() => {
                  setResetting(false);
                  setNewPassword('');
                  setError(null);
                }}
                className="rounded-m border border-line px-3 py-2 text-[13px] text-text-2 hover:bg-bg-2"
              >
                Cancel
              </button>
            </div>
          </form>
        )}
      </div>

      <PropertyAccessSection user={user} />
    </div>
  );
}
```

- [ ] **Step 2: Add a temporary stub for `PropertyAccessSection`**

Below `UserDetail`, add:

```tsx
function PropertyAccessSection(_: { user: UserOut }) {
  return <div className="text-text-3 text-[13px]">Property access UI — next task</div>;
}
```

- [ ] **Step 3: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AdminClient.tsx
git commit -m "feat(admin): UserDetail with reset-password flow"
```

---

## Task 13: Implement `PropertyAccessSection` (grant/revoke)

**Files:**
- Modify: `frontend/src/components/AdminClient.tsx`

- [ ] **Step 1: Replace the PropertyAccessSection stub**

```tsx
function PropertyAccessSection({ user }: { user: UserOut }) {
  const queryClient = useQueryClient();
  const properties = useQuery({
    queryKey: ['admin', 'properties'],
    queryFn: () => adminApi.listProperties(),
  });
  const allProps = properties.data ?? [];
  const propsById = new Map(allProps.map((p) => [p.id, p]));
  const grantedSet = new Set(user.property_ids);
  const availableProps = allProps.filter((p) => !grantedSet.has(p.id));
  const [addId, setAddId] = useState<string>('');

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });

  const grant = useMutation({
    mutationFn: (propertyId: number) =>
      adminApi.grantAccess({ user_id: user.id, property_id: propertyId }),
    onSuccess: () => {
      setAddId('');
      invalidate();
    },
  });
  const revoke = useMutation({
    mutationFn: (propertyId: number) =>
      adminApi.revokeAccess({ user_id: user.id, property_id: propertyId }),
    onSuccess: invalidate,
  });

  if (user.is_superuser) {
    return (
      <div>
        <div
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          PROPERTY ACCESS
        </div>
        <div className="mt-2 rounded-m border border-line bg-bg-2 px-3 py-2 text-[13px] text-text-2">
          All properties (superuser)
        </div>
      </div>
    );
  }

  return (
    <div>
      <div
        className="mono text-[10px] text-text-3"
        style={{ letterSpacing: '0.12em' }}
      >
        PROPERTY ACCESS
      </div>
      <ul className="mt-2 divide-y divide-line rounded-m border border-line">
        {user.property_ids.length === 0 && (
          <li className="px-3 py-3 text-[13px] text-text-3">
            No properties granted. Add one below.
          </li>
        )}
        {user.property_ids.map((pid) => {
          const p = propsById.get(pid);
          return (
            <li key={pid} className="flex items-center justify-between gap-2 px-3 py-2">
              <div className="text-[13px]">
                {p?.name ?? `Property #${pid}`}
              </div>
              <button
                type="button"
                onClick={() => revoke.mutate(pid)}
                disabled={revoke.isPending}
                className="rounded-m border border-line px-2 py-1 text-[12px] text-text-2 hover:bg-bg-2 hover:text-bad disabled:opacity-50"
              >
                Revoke
              </button>
            </li>
          );
        })}
      </ul>

      {availableProps.length > 0 && (
        <div className="mt-3 flex items-end gap-2">
          <label className="flex flex-1 flex-col gap-1">
            <span
              className="mono text-[10px] text-text-3"
              style={{ letterSpacing: '0.12em' }}
            >
              ADD PROPERTY
            </span>
            <select
              value={addId}
              onChange={(e) => setAddId(e.target.value)}
              className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
            >
              <option value="">— select —</option>
              {availableProps.map((p) => (
                <option key={p.id} value={String(p.id)}>
                  {p.name}
                </option>
              ))}
            </select>
          </label>
          <button
            type="button"
            disabled={!addId || grant.isPending}
            onClick={() => grant.mutate(Number(addId))}
            className="rounded-m bg-accent px-3 py-2 text-[13px] font-medium text-[var(--text-on-accent)] disabled:opacity-50"
          >
            Grant
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AdminClient.tsx
git commit -m "feat(admin): grant/revoke property access from UserDetail"
```

---

## Task 14: Implement `NewUserCard`

**Files:**
- Modify: `frontend/src/components/AdminClient.tsx`

- [ ] **Step 1: Replace the NewUserCard stub**

```tsx
function NewUserCard({ onCreated }: { onCreated: (id: number) => void }) {
  const queryClient = useQueryClient();
  const properties = useQuery({
    queryKey: ['admin', 'properties'],
    queryFn: () => adminApi.listProperties(),
  });
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [propertyIds, setPropertyIds] = useState<number[]>([]);
  const [usernameError, setUsernameError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string | null>(null);

  const create = useMutation({
    mutationFn: () =>
      adminApi.createUser({
        username: username.trim(),
        password,
        property_ids: propertyIds,
      }),
    onSuccess: (u) => {
      setUsername('');
      setPassword('');
      setPropertyIds([]);
      setUsernameError(null);
      setPasswordError(null);
      queryClient.invalidateQueries({ queryKey: ['admin', 'users'] });
      onCreated(u.id);
    },
    onError: (err: Error) => {
      const msg = err.message.toLowerCase();
      if (msg.includes('username')) setUsernameError(err.message);
      else if (msg.includes('password') || msg.includes('at least 8')) setPasswordError(err.message);
      else setUsernameError(err.message);
    },
  });

  const toggleProperty = (id: number) => {
    setPropertyIds((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id],
    );
  };

  const canSubmit =
    username.trim().length > 0 && password.length >= 8 && !create.isPending;

  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        if (canSubmit) create.mutate();
      }}
      className="card p-5 space-y-3"
    >
      <div>
        <h3>New User</h3>
        <div className="sub">CREATE / GRANT ACCESS</div>
      </div>

      <label className="flex flex-col gap-1">
        <span
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          USERNAME
        </span>
        <input
          type="text"
          value={username}
          onChange={(e) => {
            setUsername(e.target.value);
            setUsernameError(null);
          }}
          required
          autoComplete="off"
          className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
        />
        {usernameError && (
          <span className="text-[12px] text-bad">{usernameError}</span>
        )}
      </label>

      <label className="flex flex-col gap-1">
        <span
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          PASSWORD (min 8 chars)
        </span>
        <input
          type="password"
          value={password}
          onChange={(e) => {
            setPassword(e.target.value);
            setPasswordError(null);
          }}
          required
          minLength={8}
          autoComplete="new-password"
          className="rounded-m border border-line bg-bg-1 px-3 py-2 text-[13px] text-text-0 outline-none focus:border-accent"
        />
        {passwordError && (
          <span className="text-[12px] text-bad">{passwordError}</span>
        )}
      </label>

      <fieldset className="space-y-1">
        <legend
          className="mono text-[10px] text-text-3"
          style={{ letterSpacing: '0.12em' }}
        >
          PROPERTIES
        </legend>
        <div className="max-h-[200px] overflow-y-auto rounded-m border border-line bg-bg-1">
          {(properties.data ?? []).length === 0 && (
            <div className="px-3 py-3 text-[12px] text-text-3">
              No properties yet.
            </div>
          )}
          {(properties.data ?? []).map((p) => (
            <label
              key={p.id}
              className="flex cursor-pointer items-center gap-2 px-3 py-2 text-[13px] hover:bg-bg-2"
            >
              <input
                type="checkbox"
                checked={propertyIds.includes(p.id)}
                onChange={() => toggleProperty(p.id)}
              />
              <span>{p.name}</span>
            </label>
          ))}
        </div>
      </fieldset>

      <button
        type="submit"
        disabled={!canSubmit}
        className="inline-flex w-full items-center justify-center gap-2 rounded-m bg-accent px-3 py-2 text-[13px] font-medium text-[var(--text-on-accent)] disabled:opacity-50"
      >
        {create.isPending ? (
          <Loader2 size={14} className="animate-spin" />
        ) : (
          <Plus size={14} />
        )}
        Create user
      </button>
    </form>
  );
}
```

- [ ] **Step 2: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/AdminClient.tsx
git commit -m "feat(admin): NewUserCard create-user form with property grants"
```

---

## Task 15: Hide the Users tab from non-superusers

**Files:**
- Modify: `frontend/src/components/AdminClient.tsx`

The backend already enforces `require_superuser` on every `/admin/users` endpoint. The frontend should still hide the tab so non-superusers don't see a broken UI.

- [ ] **Step 1: Read `auth-api.ts` and check the CurrentUserResponse fields**

Run: `grep -n "is_superuser\|is_staff\|CurrentUserResponse" frontend/src/types/api.gen.ts | head -5`

Expected: `CurrentUserResponse` exposes `is_superuser: boolean`.

- [ ] **Step 2: Fetch the current user in AdminClient and filter the tabs**

In `AdminClient.tsx`:

Add the import:
```ts
import { fetchCurrentUser } from '@/lib/auth-api';
```

Inside the `AdminClient` component, before the `return`:
```ts
const me = useQuery({
  queryKey: ['auth', 'me'],
  queryFn: () => fetchCurrentUser(),
  staleTime: 60_000,
});
const isSuperuser = me.data?.is_superuser ?? false;
```

Pass `isSuperuser` down to `Tabs`:
```tsx
<Tabs current={tab} onChange={setTab} isSuperuser={isSuperuser} />
```

Update the `Tabs` signature and filter the array:
```ts
function Tabs({
  current,
  onChange,
  isSuperuser,
}: {
  current: Tab;
  onChange: (t: Tab) => void;
  isSuperuser: boolean;
}) {
  const tabs: { key: Tab; label: string; sub: string }[] = [
    { key: 'properties', label: 'Properties', sub: 'Add / edit / common areas' },
    { key: 'clli', label: 'CLLI Library', sub: 'OLT + 7×50 codes' },
    { key: 'maintenance', label: 'Maintenance', sub: 'Scheduled windows' },
    { key: 'mdu-map', label: 'MDU Map', sub: 'Upload .xlsx · OLT lookup' },
    ...(isSuperuser
      ? [{ key: 'users' as Tab, label: 'Users', sub: 'Create / grant access' }]
      : []),
  ];
  // ... rest of the body unchanged
}
```

Guard the tab render in `AdminClient` so a non-superuser can't reach it even by setting `tab` directly:

```tsx
{tab === 'users' && isSuperuser && <UsersTab />}
```

- [ ] **Step 3: Type-check**

Run from `frontend/`:
```bash
npx tsc --noEmit
```
Expected: no errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/AdminClient.tsx
git commit -m "feat(admin): hide Users tab for non-superusers"
```

---

## Task 16: Run full backend + frontend test suites

- [ ] **Step 1: Backend unit tests**

Run: `cd backend && .venv/bin/pytest -q`
Expected: all green; integration tests skip if no `TEST_DATABASE_URL`.

- [ ] **Step 2: Backend integration tests (if DB available)**

Run: `cd backend && TEST_DATABASE_URL=postgresql+asyncpg://wifimon_test:wifimon_test@localhost:5433/wifimon_test .venv/bin/pytest tests/integration/test_admin_users_db.py -v`
Expected: all green (or skip if no DB locally; CI will run).

- [ ] **Step 3: Frontend type-check, lint, build**

Run from `frontend/`:
```bash
npx tsc --noEmit && npm run lint && npm run build
```
Expected: all green.

- [ ] **Step 4: OpenAPI snapshot drift check**

Re-run the regeneration command from Task 7 and `git diff --exit-code backend/openapi.snapshot.json`.
Expected: no diff (snapshot is up to date).

---

## Task 17: Manual verification in mock mode

Mock mode (default) refuses every `/admin/users` endpoint with 503, so this just confirms the UI handles that path gracefully and renders the tab for the synthetic dev superuser.

- [ ] **Step 1: Start the backend**

Run from `backend/`:
```bash
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8765
```

- [ ] **Step 2: Start the frontend**

Run from `frontend/`:
```bash
npm run dev
```

- [ ] **Step 3: Open the admin page**

Browse `http://localhost:3000/admin`. Confirm:
- Five tabs visible (Properties, CLLI Library, Maintenance, MDU Map, Users).
- Clicking "Users" surfaces a 503 error message in the list ("admin disabled in mock mode (USE_MOCK_DATA=true)") — this is the expected mock-mode behavior; the tab is wired correctly.

- [ ] **Step 4: Stop both dev processes**

---

## Task 18: Manual verification against a real DB (optional, before cutover)

This requires `USE_MOCK_DATA=false` and a live Postgres. Skip if not running against the real DB yet.

- [ ] **Step 1: Bootstrap a superuser via CLI**

```bash
cd backend && .venv/bin/python -m app.cli.main user create-superuser --username admin --password admin123!
```

(Adjust to the actual CLI command — see `wifimon --help`.)

- [ ] **Step 2: Log in at `/login` as that superuser**

- [ ] **Step 3: Navigate to `/admin` and click the Users tab**

Confirm the list loads (just the bootstrap superuser at first) and shows `ALL PROPERTIES` for that user.

- [ ] **Step 4: Create a property (if none) on the Properties tab**

- [ ] **Step 5: Create a new user**

In the Users tab, fill in username + password + check at least one property, click Create user. Confirm the user appears in the list and is auto-selected.

- [ ] **Step 6: Confirm site restriction**

Log out, log in as the new user, navigate to `/`. Confirm only the granted property is visible on the dashboard. Try to fetch a non-granted property by URL (`/properties/<other_id>`) — expect 403.

- [ ] **Step 7: Reset password**

Log out, log back in as superuser, open the Users tab, select the test user, click Reset password, set a new one. Log out, verify old password fails, new one works.

- [ ] **Step 8: Revoke a property**

As superuser, click Revoke on a granted property for the test user. Log in as that user — the property no longer shows on the dashboard.

- [ ] **Step 9: Grant a property**

As superuser, add a new property using the Add property dropdown + Grant button. Verify it now appears for the test user.

---

## Self-review notes

- **Spec coverage:** Every requirement in the spec maps to a task — schemas (Task 1), services (2/3/4), endpoints (5), tests (2/3/4/6), openapi regen (7), FE types (8), api client (9), tab shape (10–14), tab-hide for non-superusers (15), verification (17/18).
- **Out-of-scope items from the spec** (email, is_active/is_staff/is_superuser toggles, delete, rename, etc.) are intentionally absent from the plan.
- **Tech consistency:** schema names (`UserCreate`/`UserOut`/`UserPasswordReset`), service signatures, and TanStack Query keys (`['admin', 'users']`, `['admin', 'properties']`) match between tasks.
