# Admin user management with per-site access

**Status:** Design approved, ready for implementation plan
**Date:** 2026-05-29
**Scope:** Add a Users tab to the admin UI for creating users and restricting which properties (sites) each user can view.

## Goal

Today the admin UI manages properties, common areas, CLLI codes, maintenance windows, and MDU-OLT mapping. There is no UI for managing users or their per-property access; both must be done via the `wifimon` CLI or direct DB writes. This work adds a Users tab so a superuser can:

1. Create a new user with a username and password.
2. At creation time, choose which properties the user can view.
3. Later, grant or revoke property access on existing users.
4. Reset an existing user's password.

The site-restriction model already exists in the data layer: `UserPropertyAccess` rows determine which properties a non-superuser sees, per SPEC §5.1. Backend grant/revoke service functions and the `POST/DELETE /api/v1/admin/access` endpoints already work — this design adds user CRUD around them and a UI to drive everything.

## Non-goals

Explicitly out of scope for this iteration:

- Email field, `is_active` toggle, `is_staff` / `is_superuser` toggles in the UI. New users are always non-staff, non-superuser, active. Promoting a user to staff or superuser stays a CLI/DB operation.
- Delete user, rename username.
- Password complexity rules beyond a minimum length of 8 characters.
- Bulk grant/revoke, audit log surfacing (the `created_by_id` column exists on `UserPropertyAccess` but is not displayed).
- Password reset via email; user self-service password change.
- Bootstrapping the first superuser from the UI — that still goes through `wifimon` CLI.

## Permissions

User-management endpoints require `is_superuser=true`. A new `require_superuser` dependency is added; the existing `require_staff` is too permissive for this surface.

The Users tab is hidden in the frontend for non-superusers; backend enforcement is defense-in-depth.

## Backend

### New endpoints

All under `/api/v1/admin/users`, gated by `require_superuser` and the existing `_refuse_in_mock_mode()` helper.

| Method | Path | Body | Response | Notes |
|---|---|---|---|---|
| `GET` | `/admin/users` | — | `list[UserOut]` | Lists all users with their `property_ids`. |
| `POST` | `/admin/users` | `UserCreate` | `UserOut` (201) | Creates user + grants atomically. 409 on duplicate username. |
| `POST` | `/admin/users/{user_id}/password` | `UserPasswordReset` | 204 | Resets password only. |

Grant and revoke continue to use the existing `POST /api/v1/admin/access` and `DELETE /api/v1/admin/access` endpoints. No new endpoints are added for the per-property toggles in the detail panel.

### New schemas (`backend/app/schemas/admin.py`)

```python
class UserOut(BaseModel):
    id: int
    username: str
    is_staff: bool
    is_superuser: bool
    is_active: bool
    created_at: datetime
    last_login: datetime | None
    property_ids: list[int]  # empty for superusers (they get all properties)

class UserCreate(BaseModel):
    username: str = Field(min_length=1, max_length=150)
    password: str = Field(min_length=8, max_length=255)
    property_ids: list[int] = Field(default_factory=list)

class UserPasswordReset(BaseModel):
    password: str = Field(min_length=8, max_length=255)
```

### New service functions (`backend/app/services/admin.py`)

- `async def list_users_with_grants(session) -> list[tuple[User, list[int]]]` — returns each user with their sorted list of granted property_ids. Single query with a join to `user_property_accesses`.
- `async def create_user(session, payload: UserCreate, *, granted_by_user_id: int | None) -> User` — bcrypt-hashes the password, creates the user, and writes grants for each `property_id` in one transaction. Raises a 409-mapped exception on duplicate username (caught at the route boundary).
- `async def reset_user_password(session, user: User, new_password: str) -> None` — hashes the new password and writes it.

Password hashing uses `bcrypt.hashpw` / `bcrypt.checkpw` directly with manual 72-byte truncation, matching `app.services.auth` (per the known passlib/bcrypt incompatibility — gotcha #4 in project state).

### Error contracts

- Duplicate username on create → 409 `{"detail": "username already taken"}`.
- Weak password (< 8 chars) → 422 from Pydantic validation.
- Grant on a property that does not exist → 404 (existing behavior).
- Grant on a `(user, property)` pair that already exists → idempotent, returns the existing row, no error (existing behavior of `grant_property_access`).
- Revoke on a missing grant → 404 (existing behavior).
- Non-superuser hitting `/admin/users/*` → 403.
- Any `/admin/users/*` call in mock mode → 503 (existing `_refuse_in_mock_mode()`).

### Auth integration

No changes required to the existing access-resolution logic in `app/api/deps.py` — the `UserPropertyAccess` rows already drive per-property authorization for dashboard and detail endpoints per SPEC §5.1. New grants are immediately effective for the affected user's next request.

## Frontend

### Tab structure

`AdminClient.tsx` adds `'users'` to the `Tab` union and a fifth tab entry:

```ts
{ key: 'users', label: 'Users', sub: 'Create / grant access' }
```

A new `UsersTab` component is added in the same file, following the same shape as `PropertiesTab`.

### List + detail layout

Three-column grid matching `PropertiesTab`:

- **Left column (`col-span-1`)**: scrollable list of users. Each row: username + a small badge ("3 properties", "All properties (superuser)", or "No properties"). "+ New User" button at the top of the list opens an inline create form. Clicking a row sets `selectedUserId`.
- **Right column (`col-span-2`)**: detail panel for the selected user. Empty state if none selected.

Detail panel sections:

1. **Header:** username (read-only) and a role label ("Superuser", "Staff", or "Standard user").
2. **Reset password:** a button that reveals an inline single-field prompt with Save / Cancel.
3. **Property Access:**
   - If the user is a superuser: read-only banner "All properties (superuser)".
   - Otherwise: list of granted properties, each with a Revoke button, followed by an "Add property" single-select dropdown (populated from `listProperties()` minus the user's current `property_ids`) and a Grant button.

### Create user form

Triggered by "+ New User". Inline panel (not a modal) on the left column or replacing the detail panel — matching whichever pattern the existing Properties tab uses for its create flow.

Fields:
- Username (text, required)
- Password (password, required, hint "min 8 characters")
- Properties (checkbox list of all properties; multi-select)

Submit calls `POST /admin/users` with `{username, password, property_ids}`. On 201, the list refreshes via TanStack Query invalidation and the new user is auto-selected.

### Property Access section details

Per-row grant/revoke fires its own atomic call against `POST` or `DELETE /api/v1/admin/access`. No staged "Apply changes" button — each click is committed immediately. This matches how the existing endpoints work and avoids any "unsaved changes" UX.

### TanStack Query keys

- `['admin', 'users']` for the user list.
- The detail panel reads from the cached list — no separate per-user query.
- All mutations (create, reset password, grant, revoke) invalidate `['admin', 'users']`.

### API client additions (`frontend/src/lib/admin-api.ts`)

- `listUsers(): Promise<UserOut[]>`
- `createUser(payload: UserCreate): Promise<UserOut>`
- `resetUserPassword(userId: number, password: string): Promise<void>`
- `grantAccess(userId: number, propertyId: number): Promise<GrantOut>` (add if not present)
- `revokeAccess(userId: number, propertyId: number): Promise<void>` (add if not present)

### Types

After the backend changes, regenerate `backend/openapi.snapshot.json` and run `npm run gen:types`. The new `UserOut`, `UserCreate`, and `UserPasswordReset` types appear in `frontend/src/types/api.gen.ts` and are re-exported from `api.ts`. CI's openapi-snapshot drift guard catches it if missed.

### Error rendering

- 409 on create → inline "Username already taken" under the username field.
- 422 on create or password reset → inline "Password must be at least 8 characters".
- 404 / 403 on grant/revoke/reset → toast (matches existing pattern in admin UI).

## Testing

### Backend

- `tests/test_admin_users_service.py` (unit tests, no DB if possible; otherwise gated on `TEST_DATABASE_URL` like the existing integration tests):
  - `create_user` hashes the password (verify with `bcrypt.checkpw`).
  - `create_user` persists the requested grants atomically.
  - `create_user` raises on duplicate username.
  - `reset_user_password` updates only the hash, leaves other fields untouched.
  - `list_users_with_grants` returns property_ids in stable (sorted) order.

- `tests/test_admin_users_api.py` (API tests):
  - 401 unauthenticated.
  - 403 as staff-but-not-superuser.
  - 201 with a valid create payload and grants.
  - 409 on duplicate username.
  - 422 on password shorter than 8 chars.
  - 503 in mock mode.
  - 204 on password reset, hash actually changes.

### Frontend

No component unit tests — the project's existing posture (per project state memory) is manual verification for FE components. Verified manually:

- Create a user with selected properties; confirm the user can log in and sees only those properties on the dashboard.
- Reset password; confirm the new password works and the old one does not.
- Grant a new property; confirm it appears for the user on next dashboard load.
- Revoke a property; confirm it disappears for the user on next dashboard load.
- Confirm the Users tab is hidden for non-superuser staff accounts.
- Confirm the tab returns 503 with a friendly message in mock mode.

## Migrations

None. The `users` and `user_property_accesses` tables already exist with their full schema. No new columns are needed.

## OpenAPI / typegen workflow

1. Implement backend endpoints + schemas.
2. Regenerate `backend/openapi.snapshot.json`.
3. Run `npm run gen:types` in `frontend/`.
4. Build the FE against the regenerated types.
5. CI catches drift on PR.

## Risks and mitigations

- **Risk:** A typo in `require_superuser` could leave the new endpoints accessible to any staff member. **Mitigation:** explicit API test for 403-as-staff before merging.
- **Risk:** Half-created user if `create_user` fails between user insert and grant inserts. **Mitigation:** wrap both in a single transaction; the `create_user` service function commits once at the end.
- **Risk:** Granting `(user, property)` to a non-existent property silently succeeds via FK violation getting mapped to a generic error. **Mitigation:** validate `property_ids` exist before insert in `create_user`, return 404 with the specific id on miss.
- **Risk:** Bcrypt 72-byte truncation makes very long passwords behave unexpectedly. **Mitigation:** the existing auth service already truncates the same way; consistent behavior across login and admin password set.
