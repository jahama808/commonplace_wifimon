-- Postgres bootstrap for wifimon. Run once when you flip from mock mode
-- to real eero polling. NOT needed for the initial mock-mode bring-up.
--
-- Usage (host has Postgres already running on :5432):
--
--   sudo -u postgres psql -f /home/jahama/servers-prod/common-area-looking-glass-conversion/deploy/sql/init.sql
--
-- Then update DATABASE_URL in /home/jahama/servers-prod/common-area-looking-glass-conversion/.env
-- with the password you choose (replace CHANGE_ME on the corresponding line).
--
-- After running this, apply the schema and start the worker:
--
--   cd /home/jahama/servers-prod/common-area-looking-glass-conversion/backend
--   PYTHONPATH=. .venv/bin/alembic upgrade head
--   sudo systemctl enable --now wifimon-worker

\set wifimon_password 'CHANGE_ME'   -- replace with the actual password before running

CREATE ROLE wifimon LOGIN PASSWORD :'wifimon_password';
CREATE DATABASE wifimon OWNER wifimon;

-- The application doesn't need superuser, but it does need to create
-- ENUM types in the wifimon DB. Database ownership is enough for that.
GRANT ALL PRIVILEGES ON DATABASE wifimon TO wifimon;
