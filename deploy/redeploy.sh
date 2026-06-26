#!/usr/bin/env bash
# Rebuild + restart the WiFi Common Area Monitor after a code change.
#
# Use this instead of a bare `npm run build`. The Next.js standalone output
# does NOT include `.next/static`/`public`; they must be copied into the
# standalone tree every build or the frontend serves a blank white page
# (all JS chunks 404). This script does build → stage → restart atomically
# so a partial rebuild can't strand the running services on a broken bundle.
#
# Run as the `jahama` user (owns the repo). The restart step uses sudo and
# will prompt for a password.
#
#   ./deploy/redeploy.sh

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
FRONTEND="$ROOT/frontend"

# ── Frontend build + standalone staging ───────────────────────────────────────
echo "▸ Frontend build"
cd "$FRONTEND"
npm run build

echo "▸ Staging standalone bundle (.next/static + public)"
rm -rf .next/standalone/.next/static .next/standalone/public 2>/dev/null || true
cp -r .next/static .next/standalone/.next/static
if [[ -d public ]]; then
    cp -r public .next/standalone/public
fi

# Fail loudly if staging didn't land — this is the exact bug that caused the
# white page, so guard against shipping it again.
test -f .next/standalone/.next/static/BUILD_ID 2>/dev/null || \
test -d .next/standalone/.next/static/chunks || {
    echo "✗ standalone static staging missing — aborting before restart" >&2
    exit 1
}
echo "  staged OK"

# ── Restart services ──────────────────────────────────────────────────────────
# Backend runs from source (no build), so a restart picks up backend changes
# too. Frontend must restart so it re-registers the static handler against the
# freshly staged bundle.
echo "▸ Restarting services (sudo)"
sudo systemctl restart wifimon-web wifimon-frontend

echo
echo "✅ Redeploy done. Verify:"
echo "   curl -s -o /dev/null -w '%{http_code}\\n' https://commonplace.kokocraterlabs.com/"
