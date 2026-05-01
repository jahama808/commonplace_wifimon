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

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion
git pull                                    # repo is on github.com/jahama808/commonplace_wifimon
./deploy/bootstrap.sh                       # rebuilds frontend + reinstalls deps
sudo systemctl restart wifimon-web wifimon-frontend
# Worker (only if running): sudo systemctl restart wifimon-worker
```

## Cutover from mock to real eero (with legacy data migration)

The legacy `common_area_looking_glass` Django app's schema maps 1:1 to the
new SPEC §4 entities, so we can copy the existing rows directly instead of
rebuilding from scratch. Old + new run side-by-side at different domains
until you've validated the new dashboard against the old one.

### 1. Sanity-check what the migrator sees (no writes):

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion
backend/.venv/bin/python deploy/migrate_from_legacy.py --dry-run
```

You should see ~7 users, 10 properties, 29 common areas, ~45K network
status rows, ~39K device-count rows, etc. If any of those numbers are
zero it's a config issue — fix before continuing.

### 2. Provision the new Postgres role + database (sudo, one-time):

Pick a strong password, then:

```bash
WIFIMON_PW='$(openssl rand -hex 24)'   # or pick your own
sudo -u postgres psql <<EOF
CREATE ROLE wifimon LOGIN PASSWORD '$WIFIMON_PW';
CREATE DATABASE wifimon OWNER wifimon;
GRANT ALL PRIVILEGES ON DATABASE wifimon TO wifimon;
EOF
echo "Save this password: $WIFIMON_PW"
```

(`deploy/sql/init.sql` is the same thing with placeholders if you'd
rather edit-then-run.)

### 3. Edit three existing keys in `/home/jahama/servers-prod/common-area-looking-glass-conversion/.env`:

The file already exists (bootstrap.sh wrote it). You're CHANGING values
in place, not adding new lines.

| Key | New value |
|---|---|
| `USE_MOCK_DATA` | `false` |
| `DATABASE_URL` | `postgresql+asyncpg://wifimon:THE_PASSWORD_FROM_STEP_2@127.0.0.1:5432/wifimon` |
| `EERO_API_TOKEN` | (copy verbatim from the legacy app's `.env`) |

Quick way to grab the legacy values without typing them:

```bash
grep ^EERO_API_TOKEN /home/jahama/servers-prod/common_area_looking_glass/.env
grep ^PUSHOVER     /home/jahama/servers-prod/common_area_looking_glass/.env  # optional
```

`PUSHOVER_APP_TOKEN` + `PUSHOVER_USER_KEY` are optional — only set them
if you want push notifications on outages. Everything else
(`SECRET_KEY`, `DOMAIN`, `SESSION_COOKIE_SECURE`, `LOG_FORMAT`, etc.)
stays as bootstrap left it.

### 4. Create the empty schema:

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion/backend
PYTHONPATH=. .venv/bin/alembic upgrade head
```

### 5. Migrate the legacy data:

```bash
cd /home/jahama/servers-prod/common-area-looking-glass-conversion
backend/.venv/bin/python deploy/migrate_from_legacy.py
# Confirm the TRUNCATE prompt with `yes`
```

The migrator preserves IDs (so `/properties/3` in the new app is the same
property as in the old app) and resets sequences afterward. Migrated
users keep their Django pbkdf2 password hashes — `verify_password` knows
how to read both pbkdf2 and bcrypt, so existing logins still work.

### 6. Restart web + start the worker (sudo):

```bash
sudo systemctl restart wifimon-web
sudo systemctl enable --now wifimon-worker
sudo systemctl status wifimon-worker --no-pager
```

The worker grabs the Postgres advisory lock and starts polling on the
next 15-minute boundary. Within 15 min the new app should have brand-new
`network_status` + `connected_device_count` rows alongside the migrated
history.

### 7. Validate side-by-side

Both apps are now live:

- Legacy: `https://commonwatch.kokocraterlabs.com/`
- New:    `https://commonplace.kokocraterlabs.com/`

Spot-check that property names, common area device counts, and recent
outage history line up between the two. Use the new app's `/properties/{id}`
and `/areas/{network_id}` pages to drill into specific networks and
compare against the legacy property-detail page.

### 8. Final shutdown of legacy app

Once the new dashboard agrees with the old one and you're confident:

```bash
sudo systemctl stop common_area_looking_glass.service
sudo systemctl disable common_area_looking_glass.service
# Also remove the `commonwatch.kokocraterlabs.com` block from
# /etc/caddy/Caddyfile, then:
sudo systemctl reload caddy
```

The legacy DB stays put (untouched by the migration; it was a read-only
copy). Keep it as a backup until you've collected ~7 days of fresh
polling data on the new app.

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
