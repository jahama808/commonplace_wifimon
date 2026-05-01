# WiFi Common Area Monitor — Rebuild Specification

**Audience:** Engineering team rebuilding this app on a modern stack.
**Source app:** Django 5 + SQLite/PostgreSQL + APScheduler + server-rendered templates (Chart.js).
**Target stack:** **FastAPI (Python) + PostgreSQL + Next.js (React/TypeScript)**, with background polling running as a separate Python worker process.
**Goal:** Rebuild on a modern stack that's easier to onboard new properties/common areas into, with a redesigned UI, while **fully retaining the per-SSID connected-devices-over-time charting** — the most-used feature of the product.

---

## 1. Product Summary

This is a network operations dashboard for a property management organization that operates **eero-based WiFi networks** in shared/common areas across multiple Hawaiian-island properties (apartments, hotels, condos, etc.).

For each property there are one or more "common areas" (lobby, pool, gym, parking, etc.). Each common area is a single eero network identified by a `network_id`. Each eero network contains 1..N physical eero units (access points). Each network broadcasts 1..N SSIDs, and at any time some number of client devices (phones, laptops, IoT) are connected to each SSID.

The app continuously polls the eero cloud API to:

1. Determine whether each network is online or offline.
2. Determine whether each individual eero unit is online or offline.
3. Record how many client devices are connected to each network — broken down per SSID — over time.

Then it presents an at-a-glance dashboard, sends push notifications when something fails, supports drill-down into a property and into a single network, and generates PDF reports.

### Primary users

- **Network operations / NOC staff** — watch the dashboard to spot outages.
- **Property managers** — log in and see only the properties they're authorized for, view trend graphs, generate PDF reports for ownership.
- **Administrators** — add new properties, add new common areas, manage user access, configure scheduled maintenance windows.

---

## 2. Target Stack

### Why this stack

The current Django app does three things that don't sit cleanly together: (1) async-ish polling against an external API on a schedule, (2) a server-rendered dashboard, and (3) PDF generation with embedded matplotlib charts. Django handles all three but none of them especially well, and APScheduler-in-the-web-process is the source of most operational pain.

The rebuild splits those concerns:

| Layer | Tech | Why |
|---|---|---|
| **API server** | FastAPI + Pydantic + SQLAlchemy 2.x | Async-native (polling and HTTP-handling share an event loop), Pydantic schemas double as API contracts, auto-generated OpenAPI for the frontend. |
| **Database** | PostgreSQL 16+ | Already the production DB. Same schema migrates over. |
| **Background worker** | Standalone Python process running APScheduler **or** Celery + Redis (pick one — see §6.2) | Polls the eero API on cron, writes to the same DB. Crashes don't take the API down. |
| **PDF generation** | `reportlab` + `matplotlib` (kept from current app) | The PDF report logic is non-trivial; porting it to JS would be a multi-week distraction. Run it inside the API server (sync endpoint that streams the PDF). |
| **Frontend** | Next.js (App Router) + TypeScript | Real component model, deep-linkable URLs, first-class realtime via SSE/WebSockets, modern design-system support. |
| **Charts** | Recharts or ECharts (TypeScript) | Replaces server-rendered Chart.js. Better tooltips, color-blind-safe palettes, animation. |
| **Auth** | FastAPI session cookies (or JWT) + per-property authorization middleware | Replaces Django auth. Simpler model. |
| **Notifications** | Pluggable adapter; Pushover default | Same contract as today, behind an interface. |
| **Deployment** | Docker Compose (single host) or Kubernetes (multi-host); separate `web` and `worker` containers | Stateless web tier; worker is the only stateful piece (it owns the polling lock). |

### What stays Python

PDF report generation, eero response parsing, online/offline determination ladder, the chronic-state and notification-throttle state machines. All of this has tested behavior in the current app and zero benefit from being rewritten in TypeScript.

### What becomes TypeScript

The entire frontend. No more Django templates, no more inline `<style>` blocks, no more inline `<script>` per page.

---

## 3. Critical, Must-Retain Feature

> **CONNECTED DEVICES OVER TIME, FILTERED BY SSID.**
> This feature MUST be retained verbatim in behavior. UI may be redesigned, but the data model, sampling cadence, and filtering capabilities must not change.

### 3.1 What it does today

Every 15 minutes during the day (06:00–22:00 HST) and every 30 minutes overnight (22:00–06:00 HST), the system:

1. Calls the eero API endpoint `GET {EERO_API_BASE_URL}{network_id}/devices` for **every** common area.
2. Filters the response to only devices where `connected: true`.
3. Buckets those connected devices by `ssid` (string field on each device record). Devices without an SSID are bucketed under `"Unknown SSID"`.
4. Writes one `connected_device_count` row per network with `ssid=""` and `count=<total connected>`. **This empty-SSID row represents the network total.**
5. Writes one additional `connected_device_count` row per (network, ssid) pair with `count=<count for that ssid>`.
6. Deletes all `connected_device_count` rows older than 7 days.

### 3.2 What the UI shows today (and must continue to show)

On the **Property Detail** page there are TWO charts, both stacked bar charts (x = time, y = device count, one stack-segment color per common area):

**Chart A — "Connected Devices Over Time"** (totals)
- Pulls all `connected_device_count` rows where `common_area.property == this property` AND `ssid == ""` for the selected window (1 day or 7 days).
- Stacked bars: x-axis is each sample timestamp, each network in the property contributes one colored segment showing its total connected devices at that timestamp.
- Tooltip footer shows the sum across all stacks ("Total: N devices").
- Toggle: `[1 Day] [7 Days]` (rebuild should also offer 30 days).

**Chart B — "Connected Devices by SSID"**
- Dropdown of all distinct SSIDs ever seen in the time window for this property.
- When a user picks an SSID:
  - Pulls `connected_device_count` rows for that property and that exact SSID.
  - Stacks the same way: each common area is a colored layer showing how many devices on **that SSID** are connected to **that common area's network** at each sample.
  - Tooltip footer shows "Total: N devices on {ssid}".
- "Clear" button resets the chart.
- If SSID has no data in window → empty-state message.

### 3.3 Why this matters

Property owners need to prove network usage to investors and tenants. They specifically need answers like:
- "How many people use the guest WiFi on weekends vs. weekdays?"
- "Did we just shed 30 staff devices because the back-of-house SSID went down?"
- "Is the lobby SSID being saturated at 6pm?"

The per-SSID time-series IS the report. Removing or degrading it is unacceptable.

### 3.4 Hard requirements for the rebuild

- Sampling cadence: **15 min** (06:00–22:00 local HST) and **30 min** (22:00–06:00 HST). Configurable, but defaults must match.
- Storage retention: 7 days (configurable).
- A single sample run writes:
  - **One** "total" record per network (canonical: `ssid` field is empty/null sentinel).
  - **N** per-SSID records per network.
- Time storage: store UTC; render in HST.
- The network-total chart and per-SSID chart must look at the **same** sample timestamps (no separate sampling pipeline).
- Per-SSID drilldown must be done client-side after a server-driven dropdown selection (or via API param), but it must not require re-polling the eero API — only re-querying the database.
- The PDF report (see §7) reuses the same per-SSID stacked chart logic. Keep that contract.
- Adding a new common area must Just Work — the next sampling tick should start collecting both total and per-SSID counts for it with no manual code change.

---

## 4. Domain Model

The data model below is what the rebuild needs. Treat field names as a contract for migration; types/constraints as required.

### 4.1 Entities

#### `Property`
A physical property (apartment building, hotel, etc.). One property has many common areas.

| Field | Type | Notes |
|---|---|---|
| `id` | int / uuid | PK. |
| `name` | string, unique | Human-readable property name. |
| `address` | text, optional | |
| `created_at`, `updated_at` | timestamps | |
| `olt_cllis` | M:N → `OltClli` | Optional, used for maintenance impact. |
| `seven_fifty_cllis` | M:N → `SevenFiftyClli` | Optional, used for maintenance impact. |

Computed/derived (UI uses these):
- `total_areas`, `online_areas_count`, `offline_areas_count`, `has_offline_areas`
- `central_office` = first 8 chars of the first OLT CLLI's `clli_code`, or `"--"`.

#### `CommonArea`
One WiFi network at a property. This is the unit the system polls.

| Field | Type | Notes |
|---|---|---|
| `id` | int / uuid | PK. |
| `property` | FK → `Property` | Cascade delete. |
| `island` | enum: `kauai`, `oahu`, `molokai`, `lanai`, `maui`, `hawaii` | Hawaii island where this network lives. Optional. |
| `location_type` | enum: `indoor`, `outdoor` | Default `indoor`. |
| `location_name` | string | "Lobby", "Pool Deck", etc. Unique per property. |
| `network_id` | string, **globally unique** | The eero network ID used in API calls. This is the lookup key. |
| `description` | text, optional | |
| `api_endpoint` | URL, optional | Override URL if non-default API. Falls back to `{EERO_API_BASE_URL}{network_id}`. |
| `network_name` | string | Auto-populated from eero API response. |
| `ssid` | string | Auto-populated; the network's primary SSID. **Note**: this is the eero "network SSID" — not to be confused with the per-device SSID used for time-series filtering. Both exist. |
| `wan_ip` | IPv4/IPv6 | Auto-populated. |
| `is_online` | bool | Cached current status. |
| `last_checked` | timestamp | |
| `offline_since` | timestamp, nullable | Set when first detected offline; cleared on recovery. |
| `is_chronic` | bool | Set true once `offline_since` is older than 1 hour. |
| `created_at`, `updated_at` | timestamps | |

Constraint: `unique_together (property, location_name)`.

Computed: `can_check_status()` — true if `last_checked` is null or > 1 hour ago.

#### `NetworkStatus`
Append-only history of every network status check.

| Field | Type | Notes |
|---|---|---|
| `id` | int | PK. |
| `common_area` | FK → `CommonArea` | Cascade. |
| `is_online` | bool | |
| `checked_at` | timestamp | Auto. Indexed. |
| `response_time_ms` | int, nullable | API latency. |
| `error_message` | text | Empty string if none. |
| `raw_response` | JSONB | Whole API payload, for debugging. |

Indexes: `(checked_at desc)`, `(common_area, checked_at desc)`.

#### `EeroDevice`
A physical eero unit. Multiple per common area.

| Field | Type | Notes |
|---|---|---|
| `id` | int | PK. |
| `common_area` | FK → `CommonArea` | Cascade. |
| `serial` | string | Device serial. Unique per common_area. |
| `location` | string, optional | "Living Room", "Garage", etc. — labeled in the eero app. |
| `location_type` | enum: `indoor`, `outdoor` | |
| `model` | string | "eero Pro 6E", "eero Outdoor 7", etc. |
| `firmware_version` | string | Updated daily at 03:00 HST. |
| `is_online` | bool | |
| `offline_since` | timestamp, nullable | |
| `is_chronic` | bool | True after 24h offline. |
| `last_notification_sent` | timestamp, nullable | For per-day throttling. |
| `created_at`, `last_updated` | timestamps | |

Constraint: `unique_together (common_area, serial)`.

#### `ConnectedDeviceCount` ⭐ CRITICAL FOR §3

| Field | Type | Notes |
|---|---|---|
| `id` | int | PK. |
| `common_area` | FK → `CommonArea` | Cascade. |
| `count` | int | |
| `ssid` | string | **Empty string `""` means "network total".** Otherwise the SSID name. |
| `timestamp` | timestamp | Auto. Indexed. |

Indexes: `(timestamp desc)`, `(common_area, timestamp desc)`, `(ssid, timestamp desc)`.

> Sentinel-empty-string convention is what the current charts depend on. If the rebuild prefers `null` or a separate `is_total` boolean, that's fine, but the rule is **one canonical "total" row + N per-SSID rows per sample**.

#### `OltClli`, `SevenFiftyClli`
Telecom equipment identifiers (CLLI codes for OLT shelves and 7x50 aggregation routers). Many properties can share one CLLI; one property can have many CLLIs. Used purely to compute "which properties does this scheduled maintenance affect?"

| Field | Type | Notes |
|---|---|---|
| `clli_code` | string, unique | |
| `description` | string, optional | |
| `created_at`, `updated_at` | timestamps | |

#### `ScheduledMaintenance`
Operator-entered notice of planned downtime.

| Field | Type | Notes |
|---|---|---|
| `id` | int | PK. |
| `island` | enum + `all` | Which island (or all). |
| `olt_cllis` | M:N → `OltClli` | Affected OLT shelves. |
| `seven_fifty_cllis` | M:N → `SevenFiftyClli` | Affected aggregation routers. |
| `scheduled` | timestamp | When maintenance happens. |
| `is_active` | bool | Hide from dashboard if false. |
| `created_at`, `updated_at` | timestamps | |

Method: `get_affected_properties()` → all properties whose CLLIs intersect this maintenance.

#### `UserPropertyAccess`
Authorization grant: a non-superuser user can only see properties they've been explicitly granted.

| Field | Type | Notes |
|---|---|---|
| `user` | FK → User | |
| `property` | FK → `Property` | |
| `created_at` | timestamp | |
| `created_by` | FK → User, nullable | Who granted it. |

Constraint: `unique_together (user, property)`.

Resolution rules:
- Anonymous user → no properties.
- Superuser → all properties.
- Authenticated non-superuser with no grants → no properties.
- Authenticated user with grants → only those properties.

---

## 5. Functional Features

### 5.1 Authentication & authorization

- **Login** at `/login`. Username + password. Sets a secure session cookie (HttpOnly, SameSite=Lax, 2-week lifetime).
- **Logout** at `/logout`.
- **Admin UI** (FastAPI-served or a Next.js admin route — operator preference) for superusers and staff.
- **All non-login pages require authentication** (Next.js middleware redirects to `/login`; FastAPI endpoints return 401).
- **Per-property access enforcement**: every endpoint that accepts a `property_id` or `area_id` must check `user_property_access` and 403 on miss. Implement as a FastAPI dependency: `Depends(require_property_access)` so it can't be forgotten.
- **Rate limit middleware**: 30 req/min per IP, returns `429`. Use `slowapi` or equivalent.

### 5.2 Background polling pipeline

The system runs four scheduled jobs. The worker is a separate Python process; the web tier never runs jobs.

| Job | Cadence | What it does |
|---|---|---|
| `check_all_networks` | every 15 min | Calls `GET {base}{network_id}` for every network whose `last_checked` is null or > 1 hour ago. Updates `is_online`, `offline_since`, `is_chronic`. Writes `network_status`. Sends push notification on transition (subject to chronic-throttle). |
| `check_all_devices` | every 15 min | For every common area, calls `GET {base}{network_id}/eeros`. Upserts `eero_device` rows. Deletes any devices not in the response. Tracks per-device offline / chronic / notification throttle. |
| `record_device_counts` | every 15 min day, 30 min night (HST-aware cron) | Calls `GET {base}{network_id}/devices`, filters to `connected: true`, buckets by `ssid`. Writes total (ssid="") + per-SSID rows to `connected_device_count`. Garbage-collects rows older than 7 days. |
| `update_firmware_versions` | daily 03:00 HST | Re-runs `check_all_devices` to refresh firmware strings. |

Behaviors that must be preserved:

- **Per-network 1-hour rate limit** for `check_network_status`. Admin "force check" can bypass.
- **Online/offline determination** is layered (fall through in order):
  1. `health.internet.status` → online if in `{"connected","online","up","ok","green"}`.
  2. `health.internet.isp_up` boolean.
  3. `health.status` → online if in `{"green","yellow","healthy","ok"}`.
  4. Top-level `status` → `"green"` and `"yellow"` are online; `"red"` is offline.
  5. Boolean fields: `online`, `is_online`, `connected`.
  6. Presence of `url` → assume online (defensive).
  7. Else offline.
- **eero responses are sometimes nested under `data`** — try both shapes for every field.
- **Metadata extraction**: pull `name`, `ssid`, `wan_ip` from various locations (`raw`, `data.*`, `ip_settings.wan_ip`, `dns.wan_ip`).
- **Device-list response** is sometimes `{data: [...]}` and sometimes `[...]`.
- **Use `httpx.AsyncClient`** for eero calls so the worker can poll many networks concurrently. 10-second per-request timeout.

### 5.3 Notifications

Push notifications via **Pushover** by default (HTTPS POST to `https://api.pushover.net/1/messages.json` with `token`/`user`/`message`/`title`/`priority`/`sound`).

Trigger rules:

| Event | Title | Sound | Priority | Throttle |
|---|---|---|---|---|
| Network goes offline | "NETWORK OFFLINE" | `updown` | 1 (high) | Suppress if already chronic (> 1h offline). |
| Network comes back online | "NETWORK RECOVERED" | `magic` | 0 | Always send on transition. |
| Eero device goes offline | "EERO DEVICE OFFLINE" | `falling` | 1 | Suppress if chronic (> 24h); else max 1/day. |
| Eero device comes back online | "EERO DEVICE RECOVERED" | `magic` | 0 | Always send on transition. |

Message body always includes property name, network/location, and (for devices) model + indoor/outdoor.

Implement as a `Notifier` interface with `send_network_offline()`, `send_network_recovered()`, `send_device_offline()`, `send_device_recovered()`. Default impl is `PushoverNotifier`. Alternatives (Slack, email, Twilio SMS) can be added later without touching the polling code.

### 5.4 Dashboard (`/`)

The home page after login. Three-zone layout that **must** collapse cleanly to single column on mobile (the current app is broken below 1200px — a known regression to fix).

**Header (global, every page):**
- Brand logo + name.
- Global search bar (properties, common areas, network IDs).
- Username + logout.
- Theme toggle (dark/light, dark default).

**Left zone:**
- **Last Observed Outage** card. Shows the more recent of (latest offline `network_status`, latest still-offline `eero_device`). Includes type, time, property, network, device (if device).

**Center zone:**
- **Network Health** card. Donut showing online/total + side legend with online/offline counts.
- **Service Status** table: row per (accessible) property, columns `[● status, Property name (linked), Central Office, Total Networks, Current State]`. The state column is `"ALL ONLINE"` (green) or `"N OFFLINE"` (red).
- **Outage History (Last 24 Hours)** table. Mixed list of network outages and device outages from the past 24h. Columns: `[TYPE, DATE & TIME, PROPERTY, NETWORK, DEVICE, DURATION]`. Type badges: `NETWORK` (red), `DEVICE` (orange), `CHRONIC` (dark red, > 4h continuous). Sort newest first. Group continuous outages of the same target into a single row, computing duration from first sighting; if still offline, extend duration to now.

**Right zone:**
- **Filter by Island** (chips, not just a dropdown). Applies to dashboard scope.
- **Hawaii Standard Time** as a small badge in the header (not a whole card — the current app wastes a column on it).
- **Scheduled Network Maintenance** list. Future, active maintenance entries with island, scheduled date/time, affected CLLIs/properties.

**Realtime:** Use SSE (server-sent events) from `/api/v1/dashboard/stream` to push updates when a status check writes a row. Falls back to 30s polling if the SSE connection drops. **No `<meta refresh>` page reloads.**

### 5.5 Property detail (`/properties/{id}`)

- Header: back link, property name, "Generate Report" button (sticky on scroll), address, created-at.
- Stat tiles: Total Networks · Online · Offline; Total Eero Units · Units Online · Units Offline.
- Side-by-side cards: **Eero Models** (count per model), **Firmware Versions** (count per firmware string).
- ⭐ **Connected Devices Over Time** card (Chart A, see §3.2). Time-window chips: `24h`, `7d`, `30d`. Stacked bar, one color per common area.
- ⭐ **Connected Devices by SSID** card (Chart B, see §3.2). SSID dropdown + Filter + Clear. Stacked bar broken down by common area for the selected SSID. Empty/loading states.
- **Common Areas** list: each row shows status indicator, location name, type, network ID, description, **a glowing pill with the latest total connected-device count**, current-state badge, last-checked label, and a "View Details" button.

URL state: time window and selected SSID are query params (`?days=7&ssid=Guest`). Operators paste these links into Slack.

### 5.6 Common-area detail (`/areas/{id}`)

- Identification card: property (linked), location type, network name, network ID (deep-links to `https://insight.eero.com/networks/{network_id}`), WAN IP, current status badge, last-checked, "Force check now" button (superuser only).
- **Eero Units** table: serial, location, location type, model, firmware, **connected device count for that specific eero unit**, state. The per-eero count is computed live from `/devices` by counting where `device.source.serial_number == eero.serial`.
- **Connected Devices** card: live total currently connected to this network.
- **Status History** card: line chart of response time over the last 50 checks, with point color = online (green) / offline (red).

### 5.7 Reports (`POST /api/v1/properties/{id}/report`)

Click "Generate Report" on a property page. Modal opens, fetches `/api/v1/properties/{id}/ssids`, user checks zero or more SSIDs (zero = include all), submits. Server runs the existing `reportlab` + `matplotlib` PDF builder and streams the PDF back. Browser downloads as `{property}_WiFi_Report_{YYYYMMDD_HHMMSS}.pdf`.

PDF contents (in order):
1. Title page: property name, "WiFi Network Report", generation timestamp in HST.
2. **Device Inventory**:
   - Summary: total / online / offline.
   - Models table.
   - Device details table: location, model, current connected-device count (fetched live from API), status.
3. **Connected Devices by SSID** (page break before): one stacked bar chart per selected SSID, last 24 sample points, with a network-color legend table beneath.

Run PDF generation in a FastAPI background-thread executor (`run_in_executor`) so it doesn't block the event loop.

---

## 6. Backend Design Requirements

### 6.1 Onboarding new properties and common areas (the #1 backend pain point)

Today, adding a property and its common areas requires SSHing into Django admin, creating each row by hand, and waiting for the next polling tick. The rebuild MUST support **all four** of the following:

1. **A first-class admin UI** (Next.js, not auto-generated):
   - "Add Property" wizard: name → address → island defaults → optional CLLIs → success.
   - "Add Common Area" form launched from a property page, with **eero `network_id` validation in real time**: the form hits `POST /api/v1/admin/areas/preview` which calls the eero API server-side, confirms the ID is valid, returns `network_name`, `ssid`, detected eero unit count. Operator confirms before saving.
   - "Add multiple common areas" — paste a CSV or list of `(location_name, network_id, location_type, island)` tuples and bulk-create.
   - Edit + delete with confirmation on properties and common areas.

2. **A REST API** (the same FastAPI endpoints) for external scripts and CI to onboard programmatically. OpenAPI docs at `/api/v1/docs` for free.

3. **A CLI** (`wifimon` console script via `pyproject.toml`):
   - `wifimon property add --name … --address …`
   - `wifimon area add --property … --network-id … --location …`
   - `wifimon import --file properties.yaml`
   - `wifimon access grant --user … --property …` / `revoke`
   - `wifimon check --force` (manual poll trigger)
   - `wifimon test-notify` (smoke-test Pushover)

4. **Idempotent seeding from a YAML file** checked into git:
   ```yaml
   properties:
     - name: Kapahulu Tower
       address: 1234 Kapahulu Ave, Honolulu, HI
       island: oahu
       olt_cllis: [HNLLHIXAOLT01]
       common_areas:
         - location_name: Lobby
           location_type: indoor
           network_id: "6422927"
         - location_name: Pool Deck
           location_type: outdoor
           network_id: "6422928"
   ```
   Running `wifimon import properties.yaml` should converge state — re-runs are no-ops, edits are diffs, deletes are explicit (separate flag).

### 6.2 Web vs worker split

- **Web (FastAPI)**: stateless, horizontally scalable, never runs jobs. Reads/writes the DB. Handles HTTP + SSE.
- **Worker**: single instance (acquires an advisory lock at startup so two workers can't run cron jobs concurrently). Owns the polling schedule.

Two acceptable worker implementations — pick **one**:

- **APScheduler in a dedicated process.** Simplest. The scheduler runs in `worker.py`, reads/writes the same DB. Same library as today, but isolated from the web tier.
- **Celery + Redis with `celery beat`.** More moving parts, but better for scaling beyond one worker, and gives you free retry semantics, dead-letter queues, and a flower dashboard. Use this if you anticipate > 500 networks or want per-network retries.

Default recommendation: **APScheduler in a separate process**. Upgrade to Celery if/when scale demands.

### 6.3 General requirements

- **PostgreSQL only.** Drop SQLite. Migrations via Alembic.
- **Time correctness.** Store UTC in DB. The day/night cron split for sampling cadence is HST-aware. All user-facing rendering is HST.
- **Configuration via environment.** Required: `EERO_API_TOKEN`, `DATABASE_URL`, `SECRET_KEY`. Optional: `EERO_API_BASE_URL` (default `https://api-user.e2ro.com/2.2/networks/`), `PUSHOVER_APP_TOKEN`, `PUSHOVER_USER_KEY`, `ALLOWED_ORIGINS`. Use `pydantic-settings` for typed config.
- **Secrets never reach the browser.** All eero calls happen server-side. The frontend talks only to the FastAPI API.
- **Resilience.** Each network's check is isolated (try/except around it). One bad response can't crash the polling loop. Use `httpx`'s connection pool with a sane `limits=httpx.Limits(max_connections=20, max_keepalive_connections=10)`.
- **Observability.** Structured JSON logs to stdout (use `structlog`). `/health` endpoint returns `{db: ok, eero: ok, last_poll: timestamp}`. Optional: Prometheus metrics at `/metrics`.
- **Migrations.** Schema names match the current Django model table names so an existing `pg_dump` is portable. Alembic handles forward migrations.
- **Tests.**
  - Unit: online-status determination ladder (§5.2), chronic/throttle state machines, the `record_device_counts` writer (one total + N per-SSID), `get_affected_properties()` for maintenance impact resolution, per-property access filter.
  - Integration: a fake eero server (httpx-mock) feeding the worker; verify DB state after a tick.
  - E2E: Playwright against a Next.js dev server with seeded data; click through dashboard, property page, SSID filter, report generation.

---

## 7. Backend API surface

OpenAPI auto-generated from FastAPI routes. Group as `/api/v1/...`. All endpoints require auth except the login pair.

### Auth
- `POST /api/v1/auth/login` `{username, password}` → sets session cookie.
- `POST /api/v1/auth/logout`
- `GET /api/v1/auth/me` → current user + accessible property IDs.

### Read endpoints (filtered by user's accessible properties)
- `GET /api/v1/dashboard?island=<optional>` → properties summary, network health donut data, recent outages, last-outage card, scheduled-maintenance list.
- `GET /api/v1/dashboard/stream` → SSE stream of dashboard updates.
- `GET /api/v1/properties` → list.
- `GET /api/v1/properties/{id}` → detail (stats, eero device aggregations, common-areas list with latest device counts).
- `GET /api/v1/properties/{id}/device-counts?days=1|7|30&ssid=<optional>` → time-series payload for Chart A and Chart B. **Rock-solid.** Returns `{timestamps: [...], series: [{network_id, network_name, color, data: [...]}]}` ready for stacked-bar render.
- `GET /api/v1/properties/{id}/ssids` → distinct SSIDs available for the property in the current window.
- `POST /api/v1/properties/{id}/report` `{ssids: [...]}` → streams PDF.
- `GET /api/v1/areas/{id}` → common-area detail incl. eero units, status history, live device count.
- `POST /api/v1/areas/{id}/check?force=true|false` → run a status check, return result. Force requires staff.

### Admin endpoints (staff only)
- Full CRUD for `Property`, `CommonArea`, `OltClli`, `SevenFiftyClli`, `ScheduledMaintenance`, `UserPropertyAccess`. (`EeroDevice` is read-only — populated by polling.)
- `POST /api/v1/admin/areas/preview` `{network_id}` → live eero validation; returns network_name, ssid, eero count.
- `POST /api/v1/admin/import` `multipart YAML` → idempotent bulk import (preview mode + apply mode).

### eero proxy contract (server-side only — never expose `EERO_API_TOKEN` to the browser)
- `GET https://api-user.e2ro.com/2.2/networks/{network_id}` — status, metadata.
- `GET .../{network_id}/eeros` — per-unit info.
- `GET .../{network_id}/devices` — per-client-device list. Filter `connected: true`, bucket by `ssid`.

All requests use header `X-User-Token: {EERO_API_TOKEN}` and `User-Agent: WiFi-Monitor/1.0`. 10-second timeout.

---

## 8. Frontend Design Requirements (Next.js)

The current frontend is dark, dense, GitHub/SolarWinds-inspired, server-rendered HTML with inline styles and Chart.js. It works but: feels dated; hard-coded colors; tiny clickable areas; no responsive design beyond one breakpoint; modal styling is inconsistent (white modals on a dark page); no loading/skeleton states; charts re-render on every nav.

### 8.1 Tech and structure

- **Next.js 15+ (App Router)** with TypeScript.
- **State/data**: TanStack Query (React Query) for the FastAPI calls. Optimistic updates on admin mutations.
- **Component library**: shadcn/ui (Radix primitives + Tailwind) is the default recommendation — gives you a coherent system without locking into a heavy framework. Mantine is also acceptable.
- **Styling**: Tailwind CSS. Design tokens for color, space, radius, type defined in `tailwind.config.ts`.
- **Charts**: **Recharts** (simpler) or **ECharts** (richer interactivity) — pick one and use it everywhere. Both support stacked bar, line, donut, custom tooltips.
- **Auth**: session cookie set by FastAPI is read by Next.js middleware to gate routes. Use `next-auth` only if the team wants its UI helpers; not required.
- **Forms**: `react-hook-form` + `zod` validators that mirror the Pydantic schemas.

### 8.2 Visual design

- Pick **one** coherent aesthetic and apply everywhere. Suggested direction: a calm, modern operations console — light + dark mode both supported, **dark default** (operators run night shifts).
- Status colors must remain semantically obvious (green = up, red = down, amber = warning, gray = unknown). Don't get cute; check WCAG AA contrast.
- Typography: one display family, one body family, one mono for codes/IDs/IPs. Always mono for `network_id`, `wan_ip`, MAC-like serials, firmware strings.
- Density: today's dashboard is dense. Provide a "compact / comfortable" density toggle, default to comfortable.
- Color-blind-safe palette for chart series (don't just use red+green for stacks).

### 8.3 UX must-haves

- **Loading states**: every async section gets a skeleton. No "blank-then-pop".
- **Empty states**: when a property has no networks, when an SSID has no data, etc., show explicit guidance with a CTA.
- **Error states**: when the eero API errors, surface it (retry button, last-known-good timestamp).
- **Realtime feel**: SSE-driven updates with a "Last updated · in N seconds" indicator. No full-page reloads.
- **Routing**: deep-linkable URLs for everything (property, area, time window, SSID filter). Filters reflected in the URL so an operator can paste a link in Slack.
- **Keyboard navigation**: tables and lists fully keyboard-accessible. `/` focuses search. `g d` jumps to dashboard, `g a` to admin. Operator audience.
- **Global search**: across properties + common areas + network IDs.
- **Mobile**: every page must be usable on a phone. Property managers check the app in the field.
- **Accessibility**: WCAG AA contrast on all colored text. ARIA labels on icon buttons. `prefers-reduced-motion` respected on chart animation.
- **External links** (eero Insight, etc.) clearly marked with a standard external-link icon and `rel="noopener noreferrer"`.

### 8.4 Page-by-page redesign notes

- **Login**: minimal centered card; show org logo; "Forgot password?" link if supported.
- **Dashboard**: keep three-zone information layout but redesign as a responsive card grid, not a fixed three-column shell. Filter chips for island and "show only with issues". Global search bar in the header. The HST clock is a small badge in the header — not a card.
- **Property detail**: lead with property name + at-a-glance health score; then the two big charts ⭐; then the eero models / firmware breakdown; then the list of common areas. Allow time ranges 24h / 7d / 30d. Pin "Generate Report" in a sticky header.
- **Area detail**: lead with status + WAN IP card; then eero units table; then connected-devices counter; then status-history line chart.
- **Admin**: §6.1's onboarding UI, plus user-access management (autocomplete users + properties), CLLI library editor, scheduled-maintenance editor.

### 8.5 What to drop

- The reflexive 600s `<meta http-equiv="refresh">` whole-page reload — replace with SSE/targeted re-fetch.
- Inline CSS and inline `<script>` embedded in templates.
- White modals on dark pages (the report modal today is white-on-dark — rewrite).
- Per-page CDN downloads of `chart.umd.min.js`.

---

## 9. Non-functional requirements

- **Auth/perm**: §5.1 rules ported faithfully. Document that superuser → all, no-grants → none.
- **Scheduling**: cadences and time-of-day boundaries from §5.2 are defaults; expose them as config.
- **Performance targets**:
  - Dashboard initial paint < 1s with 50 properties / 500 common areas / 7 days of samples (~50,000 `connected_device_count` rows). Cache the dashboard payload server-side for 30s.
  - Chart render < 500ms after data is loaded.
  - eero API calls in the worker concurrent (httpx pool); a full `record_device_counts` cycle for 500 networks should complete in under 60s.
- **Retention**: 7 days of sample data by default. `network_status` rows are not currently capped — add a config knob (e.g., 90 days) and document it.
- **Backups**: PostgreSQL `pg_dump` daily. Code lives in version control.
- **Deployment**: Dockerfile per service (`web`, `worker`). Compose for single-host; Helm chart for k8s.
- **Logging**: structured JSON to stdout. Log eero API 4xx/5xx separately from app errors.

---

## 10. Migration plan

1. Stand up the new schema (Postgres). Table names match current Django models so `pg_dump` is portable.
2. Data import:
   - `pg_dump` from the live system, then transform-and-load. The biggest table is `connected_device_count` — keep last 7 days only.
   - `auth_user` + `user_property_access` migrate as-is (with password hashes — both Django and FastAPI can use `passlib`/`bcrypt`).
3. Run the new worker in **shadow mode** alongside the existing Django app for ~24h. Confirm sample counts and online/offline determinations match across both systems.
4. Cut over auth (sessions invalidated; users re-login).
5. Switch DNS / reverse proxy to the new web tier.
6. Decommission the Django service.

---

## 11. Concrete checklist for the new team

The handoff is done when **all** of the following are true:

### Stack & structure
- [ ] FastAPI web service running with OpenAPI docs at `/api/v1/docs`.
- [ ] Separate worker process running APScheduler (or Celery) — never in-web-process.
- [ ] Next.js frontend talking to the FastAPI API, no Django templates anywhere.
- [ ] Single PostgreSQL DB shared by web + worker, schema managed by Alembic.
- [ ] Docker Compose brings up `web`, `worker`, `db`, `frontend`.

### Data & polling
- [ ] All entities in §4 exist with the listed fields, constraints, and indexes.
- [ ] `record_device_counts` writes one ssid="" "total" row plus N per-SSID rows per network per tick. **(The killer feature depends on this.)**
- [ ] 7-day retention GC runs and is tested.
- [ ] Day (06–22 HST) / night (22–06 HST) cadence split is in effect.
- [ ] Network online/offline determination ladder (§5.2) has unit tests covering each branch with sample eero responses.
- [ ] Chronic-state and notification-throttle state machines have unit tests for both networks (1h chronic) and devices (24h chronic, 1/day notification).

### API
- [ ] All endpoints in §7 exist, are authenticated, and enforce per-property access via a shared FastAPI dependency.
- [ ] The two device-count endpoints (with and without `ssid`) return the exact data shape the chart needs.
- [ ] No endpoint leaks the eero API token to the browser.
- [ ] OpenAPI schemas are typed end-to-end (Pydantic on the server, generated TS client on the frontend).

### Frontend
- [ ] All pages from §5.4–5.6 exist, redesigned per §8.
- [ ] **Connected Devices Over Time** stacked bar (totals) works with 1d / 7d / 30d toggles.
- [ ] **Connected Devices by SSID** stacked bar works with the SSID dropdown filter.
- [ ] PDF report generates correctly and reuses the per-SSID chart logic.
- [ ] Mobile + dark + light + reduced-motion all work.
- [ ] No `<meta refresh>` page reloads — SSE + targeted fetch only.

### Onboarding (the backend pain-point goal)
- [ ] Admin UI lets a non-engineer add a Property + N CommonAreas in < 60 seconds, with live eero `network_id` validation via `/api/v1/admin/areas/preview`.
- [ ] Bulk import (CSV or YAML) works.
- [ ] `wifimon` CLI exists with property/area/access/import commands.
- [ ] Idempotent YAML seed exists with documentation.
- [ ] Day-1 docs explain the workflow with screenshots.

### Operations
- [ ] `/health` endpoint, structured JSON logs, optional Prometheus `/metrics`.
- [ ] Notifications are pluggable; Pushover is the default.
- [ ] Background worker runs in a separate process from the web tier.
- [ ] Backups documented (DB only).
- [ ] Migration plan from existing Postgres dump completed and verified against a 24h shadow run.

---

## Appendix A — recommended dependency baseline

**Backend (`pyproject.toml`)**
```
fastapi >= 0.115
uvicorn[standard] >= 0.32
sqlalchemy >= 2.0
alembic >= 1.13
asyncpg >= 0.29
psycopg2-binary >= 2.9       # for sync admin scripts
pydantic >= 2.9
pydantic-settings >= 2.5
httpx >= 0.27                # eero API client
apscheduler >= 3.10          # or celery >= 5.4 if going that route
structlog >= 24.4
slowapi >= 0.1.9             # rate limiting
passlib[bcrypt] >= 1.7
reportlab >= 4.0             # PDF (kept from current app)
matplotlib >= 3.8            # chart images for PDF (kept)
pytz >= 2024.1
typer >= 0.12                # CLI (`wifimon`)
```

**Frontend (`package.json`)**
```
next ^15
react ^19
typescript ^5
tailwindcss ^3
@radix-ui/* + shadcn/ui
@tanstack/react-query ^5
recharts ^2  (or echarts-for-react ^3)
react-hook-form ^7 + zod ^3
date-fns-tz ^3
```

## Appendix B — eero API quick reference

Base URL: `https://api-user.e2ro.com/2.2/networks/`
Auth header: `X-User-Token: <token>`

| Endpoint | Returns |
|---|---|
| `GET /{network_id}` | Network metadata + health (used for online/offline detection). |
| `GET /{network_id}/eeros` | Array of eero units with serial, model, firmware, location, status. |
| `GET /{network_id}/devices` | Array of all client devices ever associated; filter `connected:true` for currently online; each has `ssid` and `source.serial_number` (the eero unit it's connected through). |

Response envelopes vary: data may be at the root or nested under `data`. Always handle both.

## Appendix C — Hawaii-specific notes

- Time zone: `Pacific/Honolulu` (HST, UTC−10, no DST).
- Islands enum: Kauai, Oahu, Molokai, Lanai, Maui, Hawaii.
- Operators are HST-resident; everything user-facing is HST. Don't show UTC anywhere except in raw API logs.
