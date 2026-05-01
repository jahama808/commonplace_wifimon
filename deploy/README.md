# Native deployment (no Docker)

This directory contains everything needed to deploy the rebuild as native
systemd services on the host, alongside the existing
`common_area_looking_glass.service` (the legacy app at
`commonwatch.kokocraterlabs.com`). The new app lands at
`commonplace.kokocraterlabs.com`.

## Files

| File | What it does |
|---|---|
| `bootstrap.sh` | Idempotent. Creates the Python venv, installs backend deps, runs `npm install && npm run build`, stages the Next.js standalone bundle, generates `.env` on first run. |
| `systemd/wifimon-web.service` | uvicorn on `127.0.0.1:8765` with 2 workers, `--proxy-headers` for Caddy. |
| `systemd/wifimon-frontend.service` | `node server.js` from the Next.js standalone bundle on `127.0.0.1:3030`. |
| `systemd/wifimon-worker.service` | `python -m app.worker`. **Don't enable in mock mode** — it tries to grab a Postgres advisory lock and exits if the DB isn't reachable. Enable on real-mode cutover. |
| `caddy/commonplace.caddy` | Site block for `commonplace.kokocraterlabs.com` to import into `/etc/caddy/Caddyfile`. |
| `sql/init.sql` | Postgres role + DB. **Don't run in mock mode** — only needed for real-mode cutover. |

## First-time bring-up (mock mode)

Mock mode lets you click around the dashboard without eero credentials or
a Postgres role. Worker is intentionally not started.

### 1. As `jahama` (no sudo needed):

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion
./deploy/bootstrap.sh
```

Re-runnable — only does work that hasn't been done.

### 2. Add the systemd units (sudo):

```bash
sudo cp /home/jahama/servers-prod/common-area-looking-glass-conversion/deploy/systemd/wifimon-web.service /etc/systemd/system/
sudo cp /home/jahama/servers-prod/common-area-looking-glass-conversion/deploy/systemd/wifimon-frontend.service /etc/systemd/system/
sudo cp /home/jahama/servers-prod/common-area-looking-glass-conversion/deploy/systemd/wifimon-worker.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now wifimon-web wifimon-frontend
# Don't enable wifimon-worker yet — wait for real-mode cutover.

# Sanity check
sudo systemctl status wifimon-web wifimon-frontend --no-pager
curl -fsS http://127.0.0.1:8765/health   # → {"db":"skipped",...}
curl -sI http://127.0.0.1:3030/ | head -1 # → HTTP/1.1 200 OK
```

### 3. Wire Caddy (sudo):

Append to `/etc/caddy/Caddyfile`:

```caddyfile
import /home/jahama/servers-prod/common-area-looking-glass-conversion/deploy/caddy/commonplace.caddy
```

(or paste the contents of `commonplace.caddy` directly — same effect).
Then:

```bash
sudo caddy validate --config /etc/caddy/Caddyfile          # syntax check
sudo systemctl reload caddy
```

Caddy auto-provisions a Let's Encrypt cert for `commonplace.kokocraterlabs.com`
the first time someone hits the host. DNS is already pointed at this server
(72.253.253.165).

### 4. Verify

```bash
curl -fsS https://commonplace.kokocraterlabs.com/health
# → {"db":"skipped","eero":"missing","last_poll":null,"now":"..."}
```

Open https://commonplace.kokocraterlabs.com/ — Atrium dashboard should load
with mock fixtures. Click around, verify the drawer / search / theme toggle.

## Updating the app

This directory is not currently a git repo, so updates are whatever-changed-in-place
plus a rebuild. After editing files (or replacing the directory):

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion
./deploy/bootstrap.sh                       # rebuilds frontend + reinstalls deps
sudo systemctl restart wifimon-web wifimon-frontend
# Worker (only if running): sudo systemctl restart wifimon-worker
```

If you want a proper `git pull` workflow later, run `git init` here and push to
a remote — `bootstrap.sh` doesn't care either way.

## Cutover from mock to real eero

Once you've validated the UI in mock mode and you're ready to point the
new app at the real eero data:

### 1. Provision Postgres (sudo, one-time):

Edit `deploy/sql/init.sql` — change the `CHANGE_ME` password to something real, then:

```bash
sudo -u postgres psql -f /home/jahama/servers-prod/common-area-looking-glass-conversion/deploy/sql/init.sql
```

### 2. Update `/home/jahama/servers-prod/common-area-looking-glass-conversion/.env`:

```
USE_MOCK_DATA=false
DATABASE_URL=postgresql+asyncpg://wifimon:THE_REAL_PASSWORD@127.0.0.1:5432/wifimon
EERO_API_TOKEN=...                 # paste from your eero credentials
PUSHOVER_APP_TOKEN=...              # optional
PUSHOVER_USER_KEY=...               # optional
```

### 3. Apply the schema (as `jahama`):

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion/backend
PYTHONPATH=. .venv/bin/alembic upgrade head
```

### 4. Restart web + start the worker (sudo):

```bash
sudo systemctl restart wifimon-web
sudo systemctl enable --now wifimon-worker
sudo systemctl status wifimon-worker --no-pager
```

The worker grabs the advisory lock and starts polling on the next 15-minute
boundary. Use `wifimon` CLI (via `backend/.venv/bin/python -m app.cli.main ...`)
to seed properties + common areas, OR use the `/admin` page.

### 5. Final shutdown of legacy app

Once the new app's data is whole and validated:

```bash
sudo systemctl stop common_area_looking_glass.service
sudo systemctl disable common_area_looking_glass.service
# And remove `commonwatch.kokocraterlabs.com` block from /etc/caddy/Caddyfile.
sudo systemctl reload caddy
```

## Troubleshooting

```bash
# Live tail
sudo journalctl -fu wifimon-web
sudo journalctl -fu wifimon-frontend
sudo journalctl -fu wifimon-worker

# Restart a stuck service
sudo systemctl restart wifimon-web

# What ports are bound?
ss -ltn | grep -E ':(8765|3030)\s'

# Caddy syntax check before reload
sudo caddy validate --config /etc/caddy/Caddyfile
```
