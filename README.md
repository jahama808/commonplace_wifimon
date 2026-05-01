# Common Area Monitor — Rebuild

Implements the dashboard from `design_handoff_common_area_monitor_redesign/` on
the stack defined in `SPEC.md` §2.

```
backend/    FastAPI + Pydantic + (SQLAlchemy/Alembic to come) + APScheduler worker
frontend/   Next.js 15 App Router + TypeScript + Tailwind + TanStack Query + Recharts
```

## Run via Docker Compose (full stack)

Brings up Postgres, runs migrations, then web + worker + frontend
(SPEC §11). The two app tiers bind to the host's loopback on ports chosen
to **not collide with the legacy MDULookingGlass Django app** on `:8000`,
so both can run side-by-side during cutover:

- `web` (FastAPI) → `127.0.0.1:8765`
- `frontend` (Next.js) → `127.0.0.1:3030`
- `db` (Postgres) → not bound to the host; reach via `docker compose exec db psql`

```bash
cp .env.example .env       # edit SECRET_KEY, EERO_API_TOKEN, DOMAIN, …
docker compose up --build -d
```

### Wire your existing Caddy

Drop the `Caddyfile.site` site block into your host's Caddyfile. Either
paste inline:

```caddyfile
mon.example.com {
    encode zstd gzip

    # SSE flushing — match before the broader /api/* rule
    @sse path /api/v1/dashboard/stream
    reverse_proxy @sse 127.0.0.1:8765 {
        flush_interval -1
    }

    @backend path /api/* /health /metrics /docs /openapi.json
    reverse_proxy @backend 127.0.0.1:8765
    reverse_proxy 127.0.0.1:3030
}
```

…or use `import` to keep the snippet maintained in this repo:

```caddyfile
mon.example.com {
    import /home/jahama/servers-prod/common-area-looking-glass-conversion/Caddyfile.site
}
```

Then `systemctl reload caddy` (or `caddy reload`). Caddy auto-provisions
Let's Encrypt TLS for any real domain — no extra config needed.

### Once it's up

- App: `https://mon.example.com/` (or hit `http://localhost:3030` direct to the FE for debugging)
- API docs: `/api/v1/docs`
- Metrics: `/metrics`
- Health: `/health`

The `migrate` service runs `alembic upgrade head` once on each `up` and
exits; `web` and `worker` wait for it to complete successfully.

To shell into the worker: `docker compose run --rm worker sh`.
To run the CLI: `docker compose run --rm worker wifimon --help`.

## Run locally

Three processes — web (FastAPI), worker (APScheduler), frontend (Next.js).
The frontend rewrites `/api/v1/*` to the backend (set `API_BASE_URL` to
override; default `http://localhost:8000`).

```bash
# backend web — port 8000
cd backend
python3 -m venv .venv
.venv/bin/pip install -e .
PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload --port 8000

# polling worker — separate process (SPEC §6.2)
PYTHONPATH=. .venv/bin/python -m app.worker

# frontend (new shell)
cd frontend
npm install
npm run dev
```

The worker won't run jobs until a real Postgres is reachable — it grabs
`pg_try_advisory_lock` at startup so a second worker process exits cleanly
instead of double-firing crons.

Open http://localhost:3000.

## What's wired

- Design tokens (OKLCH dark + light) in `frontend/src/app/globals.css`,
  surfaced through `tailwind.config.ts`.
- Atrium dashboard layout: header, ticker, greeting, island summary tiles,
  hero map, properties table, connected-devices stacked-area chart, 24h
  heatmap, alerts feed, skeleton loading state.
- `GET /api/v1/dashboard?island=...` — full payload (mocked for now).
- `GET /api/v1/properties/{id}/device-counts?days=...&ssid=...` — the
  must-retain stacked-bar contract from SPEC §3.

## Observability (SPEC §6.3)

- **Logs:** structured via `structlog`. `LOG_FORMAT=pretty` (dev, default) emits colored console output; `LOG_FORMAT=json` writes one JSON object per line for log shippers. `LOG_LEVEL=info|debug|warning|...`. Configured at process startup in both web and worker.
- **`/health`** — returns `{db, eero, last_poll, now}`. In `USE_MOCK_DATA` mode `db` is `"skipped"`. In real mode it pings the DB and reads the latest `network_status.checked_at` (a proxy for "is the worker still alive?"). Returns 503 on DB failure with the error in `error`.
- **`/metrics`** — Prometheus text format. Counters: `wifimon_polling_job_runs_total{job, outcome}`, `wifimon_dashboard_requests_total{mode}`. Gauge: `wifimon_polling_job_last_result{job}`. Toggle via `METRICS_ENABLED=false` to disable the route.

## Realtime (SSE)

`GET /api/v1/dashboard/stream` is a long-lived Server-Sent Events stream.
The frontend `useDashboardStream` hook subscribes and invalidates the
TanStack Query cache when the server emits `dashboard.invalidate`. A
"Live · Updated · 12s ago" indicator next to the search bar shows the
last event time and connection state.

- Mock mode: synthetic invalidate every 30s
- DB mode: polls `MAX(network_status.checked_at)` every 5s, emits on change
- 15s heartbeat comments keep proxies from killing the connection
- SPEC §5.4 fallback: when SSE drops, the FE flips to a 30s `refetchInterval` until reconnect

## Auth

Session-cookie auth (SPEC §5.1). Endpoints under `/api/v1/auth/*`:
`POST /login`, `POST /logout`, `GET /me`. Per-property access is enforced
by the `require_property_access` FastAPI dep — every endpoint that takes
`property_id` goes through it.

- 30 req/min rate limit per IP via `slowapi` (returns 429)
- Cookie signed by `SECRET_KEY`, HttpOnly, SameSite=Lax, 14d lifetime
- In **`USE_MOCK_DATA=true` mode** the auth deps return a synthetic
  `dev` superuser so the FE works without login wiring; `/auth/login`
  rejects 401 with an explicit "mock mode" detail. Real auth kicks in
  the moment `USE_MOCK_DATA=false`.

## Database

SPEC §4 entities are modeled in `backend/app/models/`. Async session
factory in `backend/app/db/session.py`. Migrations via Alembic.

```bash
cd backend
# generate a new migration after model changes
DATABASE_URL=postgresql+asyncpg://... .venv/bin/alembic revision --autogenerate -m "msg"
# apply
DATABASE_URL=postgresql+asyncpg://... .venv/bin/alembic upgrade head
# preview SQL only
DATABASE_URL=postgresql+asyncpg://... .venv/bin/alembic upgrade head --sql
```

Postgres-only (JSONB, ENUMs). Initial migration covers all 14 tables.

## Admin onboarding

CRUD endpoints under `/api/v1/admin/*` (staff-gated) and a `wifimon` CLI
deliver the SPEC §6.1 onboarding flow:

- `POST /admin/properties` · `PUT /admin/properties/{id}` · `DELETE …`
- `POST /admin/properties/{id}/areas` — add a common area to a property
- `POST /admin/areas/preview` — live eero validation (the `network_id`
  sanity check before saving)
- `POST /admin/access` · `DELETE /admin/access` — grant/revoke per-property access

CLI examples:

```bash
PYTHONPATH=. .venv/bin/python -m app.cli.main property add --name "Aston Kaanapali Shores" --address "..."
PYTHONPATH=. .venv/bin/python -m app.cli.main area preview --network-id 6422927
PYTHONPATH=. .venv/bin/python -m app.cli.main area add --property 1 --network-id 6422927 --location "Lobby"
PYTHONPATH=. .venv/bin/python -m app.cli.main access grant --user 5 --property 1
PYTHONPATH=. .venv/bin/python -m app.cli.main check --force
PYTHONPATH=. .venv/bin/python -m app.cli.main import --file seeds/properties.example.yaml          # dry-run
PYTHONPATH=. .venv/bin/python -m app.cli.main import --file seeds/properties.example.yaml --apply  # commit
PYTHONPATH=. .venv/bin/python -m app.cli.main test-notify                                          # smoke-test notifier
```

Idempotent YAML import: `Property` is keyed by `name`, `CommonArea` by
`network_id`. Re-running an unchanged file is a zero-op. Pass
`--allow-deletes` to actually delete properties/areas missing from the
YAML; default is upsert-only. Sample at `backend/seeds/properties.example.yaml`.

After `pip install -e .`, the entry point is just `wifimon`.

In **mock mode** (`USE_MOCK_DATA=true`), all admin endpoints return 503
"admin disabled in mock mode" — the mock data is hard-coded so
mutations are meaningless.

## PDF reports

`POST /api/v1/properties/{id}/report` `{"ssids": [...]}` streams a PDF
(SPEC §5.7). Empty `ssids` array means "include all". The drawer's
"Generate Report" button calls this and downloads the file with the
SPEC-correct `{property}_WiFi_Report_{YYYYMMDD_HHMMSS}.pdf` name.

Builder is sync (`reportlab` + `matplotlib` per SPEC §2 — kept from the
current Django app). The endpoint hands it to `run_in_executor` so the
event loop stays free.

## What's stubbed

Read endpoints (`/api/v1/dashboard`, `/api/v1/properties/{id}`) are still
backed by mock data in `backend/app/services/mock_dashboard.py`. Swap to
real DB queries once the polling worker (§5.2) starts writing rows — the
wire schemas in `backend/app/schemas/` won't change.

Pages beyond the dashboard (property detail, area detail, admin) are not
yet built.

## Backups

Postgres is the only stateful service — everything else is stateless and
rebuilt from images. Run a daily `pg_dump` and ship the dump to durable
storage (S3 / GCS):

```bash
docker compose exec db pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "wifimon-$(date +%F).sql.gz"
```

Restore tested against the same Postgres major version. The `connected_device_count`
table is the largest by row count; the worker's 7-day GC keeps it bounded
in steady state. `network_status` history is currently uncapped — add a
retention job before the table grows past comfort (SPEC §6.3 mentions a
90-day default).

## CI

GitHub Actions workflow at `.github/workflows/ci.yml` runs on every push
and PR:

- **Backend** — `ruff check .`, then `pytest -q` against a Postgres 16
  service container (so the 26 integration tests run too), then
  `alembic upgrade head --sql` to verify the migration compiles, then a
  diff-check that `backend/openapi.snapshot.json` is up to date.
- **Frontend** — `eslint .`, `tsc --noEmit`, `next build`.

Both jobs run in parallel; runs on stale branches are auto-cancelled when
superseded.

## Frontend types are generated from OpenAPI

`backend/openapi.snapshot.json` is the single source of truth for the FE
↔ BE wire shapes. Whenever you change a Pydantic schema:

```bash
# 1. Regenerate the snapshot
cd backend
PYTHONPATH=. .venv/bin/python -c \
  "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2, sort_keys=True))" \
  > openapi.snapshot.json

# 2. Regenerate the frontend types
cd ../frontend
npm run gen:types
```

CI fails if the snapshot is stale (someone edited a Pydantic schema
without regenerating). The generated types live in
`frontend/src/types/api.gen.ts` (don't edit) with named re-exports in
`frontend/src/types/api.ts`. The legacy `frontend/src/types/dashboard.ts`
is now a re-export shim of `api.ts` so existing imports keep working.

## Running the integration tests locally

26 tests under `backend/tests/integration/` exercise the DB-backed code
paths (admin CRUD, YAML `apply` round-trip + idempotency, polling jobs
end-to-end against a fake eero client, dashboard / property-detail /
device-counts / search repos, `get_affected_properties`). They skip
cleanly when the env isn't set, so the default `pytest -q` only runs the
145 unit tests.

```bash
# 1. Have a Postgres reachable. e.g. via docker:
docker run --rm -d --name wifimon-test-pg -p 5432:5432 \
  -e POSTGRES_USER=wifimon -e POSTGRES_PASSWORD=wifimon \
  -e POSTGRES_DB=wifimon_test postgres:16-alpine

# 2. Run the suite with the env pointing at it:
cd backend
TEST_DATABASE_URL=postgresql+asyncpg://wifimon:wifimon@localhost:5432/wifimon_test \
  PYTHONPATH=. .venv/bin/pytest -q
```

Without `TEST_DATABASE_URL`, integration tests skip with the message
"set TEST_DATABASE_URL to run integration tests".
