#!/usr/bin/env python3
"""One-shot legacy → new DB migrator.

Reads the Django `wifi_monitor_db.networks_*` + `auth_user` tables and
copies them into the new `wifimon` schema. Preserves IDs so the new
`/properties/123` URLs match what operators were using on the old site.

Idempotent in the sense of "TRUNCATE + repopulate" — running it twice
gives you the same result. NOT incremental; not safe to run while the
legacy app is actively writing (it isn't, in cutover mode).

Usage:
  ./deploy/migrate_from_legacy.py
    --legacy-url postgresql://wifi_monitor_user:PWD@localhost/wifi_monitor_db
    --new-url    postgresql://wifimon:PWD@localhost/wifimon
    [--dry-run]    # show counts, don't write
    [--yes]        # skip the "this will TRUNCATE the destination" prompt

If both URLs are omitted, they're auto-discovered:
  • Legacy: parsed from /home/jahama/servers-prod/common_area_looking_glass/.env
  • New:    parsed from .env (DATABASE_URL)
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras

REPO_ROOT = Path(__file__).resolve().parent.parent
LEGACY_ENV = Path("/home/jahama/servers-prod/common_area_looking_glass/.env")
NEW_ENV = REPO_ROOT / ".env"


# ──────────────────────────────────────────────────────────────────────────────
# Enum normalization. Legacy stores lowercase; new schema's Postgres ENUMs
# use uppercase member names (matching Python enum.Enum.member.name).
# ──────────────────────────────────────────────────────────────────────────────


ISLAND_FIX = {
    "kauai": "KAUAI",
    "oahu": "OAHU",
    "molokai": "MOLOKAI",
    "lanai": "LANAI",
    "maui": "MAUI",
    "hawaii": "HAWAII",
    "big-island": "HAWAII",  # legacy never used this but keep the alias
    "all": "ALL",            # for ScheduledMaintenance
}
LOCATION_TYPE_FIX = {"indoor": "INDOOR", "outdoor": "OUTDOOR"}


def _coerce_island(s: str | None) -> str | None:
    if s is None:
        return None
    return ISLAND_FIX.get(s.lower(), s.upper())


def _coerce_location_type(s: str | None) -> str | None:
    if s is None:
        return None
    return LOCATION_TYPE_FIX.get(s.lower(), s.upper())


# ──────────────────────────────────────────────────────────────────────────────
# Connection-string discovery
# ──────────────────────────────────────────────────────────────────────────────


def _read_envfile(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip("'").strip('"')
        out[k.strip()] = v
    return out


def discover_legacy_url() -> str | None:
    env = _read_envfile(LEGACY_ENV)
    name = env.get("DATABASE_NAME") or "wifi_monitor_db"
    user = env.get("DATABASE_USER") or "wifi_monitor_user"
    pw = env.get("DATABASE_PASSWORD")
    host = env.get("DATABASE_HOST") or "localhost"
    port = env.get("DATABASE_PORT") or "5432"
    if not pw:
        return None
    return f"postgresql://{user}:{pw}@{host}:{port}/{name}"


def discover_new_url() -> str | None:
    env = _read_envfile(NEW_ENV)
    url = env.get("DATABASE_URL")
    if not url:
        return None
    # Our app uses the asyncpg driver; psycopg2 wants a plain postgresql:// URL.
    return url.replace("postgresql+asyncpg://", "postgresql://", 1)


# ──────────────────────────────────────────────────────────────────────────────
# Per-table copies. Order matters because of FKs; do parents first.
# ──────────────────────────────────────────────────────────────────────────────


# Order matters: child tables must be truncated BEFORE their parents because
# we use RESTART IDENTITY (which TRUNCATE CASCADE does only if specified).
DEST_TABLES_TRUNCATE_ORDER = (
    "user_property_accesses",
    "connected_device_counts",
    "network_statuses",
    "eero_devices",
    "common_areas",
    "maintenance_olt_clli",
    "maintenance_seven_fifty_clli",
    "scheduled_maintenances",
    "property_olt_clli",
    "property_seven_fifty_clli",
    "olt_cllis",
    "seven_fifty_cllis",
    "properties",
    "users",
)

DEST_TABLES_WITH_SEQUENCES = (
    "users",
    "properties",
    "common_areas",
    "eero_devices",
    "network_statuses",
    "connected_device_counts",
    "olt_cllis",
    "seven_fifty_cllis",
    "scheduled_maintenances",
    "user_property_accesses",
)


def truncate_destination(dst: psycopg2.extensions.connection) -> None:
    with dst.cursor() as w:
        # CASCADE so M:N tables clean up too. RESTART IDENTITY is harmless
        # for the M:N tables (no sequences) and resets sequences for the
        # rest — but we override later via setval anyway since we're
        # preserving legacy IDs.
        joined = ", ".join(DEST_TABLES_TRUNCATE_ORDER)
        w.execute(f"TRUNCATE TABLE {joined} RESTART IDENTITY CASCADE")
    dst.commit()


def copy_users(src: psycopg2.extensions.connection, dst: psycopg2.extensions.connection) -> int:
    """auth_user → users. Keeps the Django pbkdf2_sha256 hashes verbatim;
    `app.services.auth.verify_password` knows how to verify both formats."""
    with src.cursor() as r:
        r.execute(
            "SELECT id, username, password, COALESCE(email, '') AS email, "
            "is_active, is_staff, is_superuser, date_joined, last_login "
            "FROM auth_user ORDER BY id"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO users (id, username, password_hash, email, is_active, "
            "is_staff, is_superuser, created_at, last_login) "
            "VALUES (%s, %s, %s, NULLIF(%s, ''), %s, %s, %s, %s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_properties(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT id, name, address, created_at, updated_at "
            "FROM networks_property ORDER BY id"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO properties (id, name, address, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_olt_cllis(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT id, clli_code, description, created_at, updated_at "
            "FROM networks_oltclli ORDER BY id"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO olt_cllis (id, clli_code, description, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_seven_fifty_cllis(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT id, clli_code, description, created_at, updated_at "
            "FROM networks_sevenfiftyclli ORDER BY id"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO seven_fifty_cllis (id, clli_code, description, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_property_olt_links(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT property_id, oltclli_id FROM networks_property_olt_cllis"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO property_olt_clli (property_id, olt_clli_id) VALUES (%s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_property_seven_fifty_links(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT property_id, sevenfiftyclli_id FROM networks_property_seven_fifty_cllis"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO property_seven_fifty_clli (property_id, seven_fifty_clli_id) "
            "VALUES (%s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_common_areas(src, dst) -> int:
    """Renames `property_obj_id` → `property_id`, lowercase enum values →
    uppercase ENUM members, and casts inet→text for `wan_ip`."""
    with src.cursor() as r:
        r.execute(
            "SELECT id, property_obj_id, location_name, network_id, description, "
            "api_endpoint, network_name, ssid, wan_ip::text, island, location_type, "
            "is_online, last_checked, offline_since, is_chronic, created_at, updated_at "
            "FROM networks_commonarea ORDER BY id"
        )
        rows = r.fetchall()
    transformed = [
        (
            id_, property_id, location_name, network_id, description, api_endpoint,
            network_name, ssid, wan_ip,
            _coerce_island(island),
            _coerce_location_type(location_type) or "INDOOR",
            is_online, last_checked, offline_since, is_chronic, created_at, updated_at,
        )
        for (
            id_, property_id, location_name, network_id, description, api_endpoint,
            network_name, ssid, wan_ip, island, location_type,
            is_online, last_checked, offline_since, is_chronic, created_at, updated_at,
        ) in rows
    ]
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO common_areas (id, property_id, location_name, network_id, "
            "description, api_endpoint, network_name, ssid, wan_ip, island, location_type, "
            "is_online, last_checked, offline_since, is_chronic, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s::island, %s::location_type, "
            "%s, %s, %s, %s, %s, %s)",
            transformed,
        )
    dst.commit()
    return len(transformed)


def copy_eero_devices(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT id, common_area_id, serial, location, location_type, model, "
            "firmware_version, is_online, offline_since, is_chronic, "
            "last_notification_sent, created_at, last_updated "
            "FROM networks_eerodevice ORDER BY id"
        )
        rows = r.fetchall()
    transformed = [
        (
            id_, common_area_id, serial, location,
            _coerce_location_type(location_type) or "INDOOR",
            model, firmware_version, is_online, offline_since, is_chronic,
            last_notification_sent, created_at, last_updated,
        )
        for (
            id_, common_area_id, serial, location, location_type, model,
            firmware_version, is_online, offline_since, is_chronic,
            last_notification_sent, created_at, last_updated,
        ) in rows
    ]
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO eero_devices (id, common_area_id, serial, location, location_type, "
            "model, firmware_version, is_online, offline_since, is_chronic, "
            "last_notification_sent, created_at, last_updated) "
            "VALUES (%s, %s, %s, %s, %s::location_type, %s, %s, %s, %s, %s, %s, %s, %s)",
            transformed,
        )
    dst.commit()
    return len(transformed)


def copy_network_statuses(src, dst) -> int:
    """45K+ rows. Use a server-side cursor + batched inserts to keep memory bounded."""
    BATCH = 1000
    total = 0
    with src.cursor(name="ns_cursor") as r:
        r.itersize = BATCH
        r.execute(
            "SELECT id, common_area_id, is_online, checked_at, response_time_ms, "
            "COALESCE(error_message, '') AS error_message, raw_response "
            "FROM networks_networkstatus ORDER BY id"
        )
        with dst.cursor() as w:
            while True:
                batch = r.fetchmany(BATCH)
                if not batch:
                    break
                # raw_response is JSONB on both sides — psycopg2 returns it
                # as a dict, but won't auto-adapt dicts on INSERT. Wrap in
                # Json() so it's serialized to a jsonb literal.
                wrapped = [
                    (id_, ca_id, online, checked, rt_ms, err,
                     psycopg2.extras.Json(raw) if raw is not None else None)
                    for (id_, ca_id, online, checked, rt_ms, err, raw) in batch
                ]
                psycopg2.extras.execute_batch(
                    w,
                    "INSERT INTO network_statuses (id, common_area_id, is_online, "
                    "checked_at, response_time_ms, error_message, raw_response) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                    wrapped,
                )
                total += len(batch)
                print(f"\r    network_statuses: {total}", end="", flush=True)
            print()
    dst.commit()
    return total


def copy_connected_device_counts(src, dst) -> int:
    """39K+ rows."""
    BATCH = 2000
    total = 0
    with src.cursor(name="cdc_cursor") as r:
        r.itersize = BATCH
        r.execute(
            "SELECT id, common_area_id, count, COALESCE(ssid, '') AS ssid, timestamp "
            "FROM networks_connecteddevicecount ORDER BY id"
        )
        with dst.cursor() as w:
            while True:
                batch = r.fetchmany(BATCH)
                if not batch:
                    break
                psycopg2.extras.execute_batch(
                    w,
                    "INSERT INTO connected_device_counts (id, common_area_id, count, ssid, timestamp) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    batch,
                )
                total += len(batch)
                print(f"\r    connected_device_counts: {total}", end="", flush=True)
            print()
    dst.commit()
    return total


def copy_scheduled_maintenances(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT id, island, scheduled, is_active, created_at, updated_at "
            "FROM networks_scheduledmaintenance ORDER BY id"
        )
        rows = r.fetchall()
    transformed = [
        (id_, _coerce_island(island), scheduled, is_active, created_at, updated_at)
        for id_, island, scheduled, is_active, created_at, updated_at in rows
    ]
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO scheduled_maintenances (id, island, scheduled, is_active, "
            "created_at, updated_at) "
            "VALUES (%s, %s::maintenance_island, %s, %s, %s, %s)",
            transformed,
        )
    dst.commit()
    return len(transformed)


def copy_maintenance_olt_links(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT scheduledmaintenance_id, oltclli_id "
            "FROM networks_scheduledmaintenance_olt_cllis"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO maintenance_olt_clli (maintenance_id, olt_clli_id) VALUES (%s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_maintenance_seven_fifty_links(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT scheduledmaintenance_id, sevenfiftyclli_id "
            "FROM networks_scheduledmaintenance_seven_fifty_cllis"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO maintenance_seven_fifty_clli (maintenance_id, seven_fifty_clli_id) "
            "VALUES (%s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def copy_user_property_accesses(src, dst) -> int:
    with src.cursor() as r:
        r.execute(
            "SELECT id, user_id, property_id, created_at, created_by_id "
            "FROM networks_userpropertyaccess ORDER BY id"
        )
        rows = r.fetchall()
    with dst.cursor() as w:
        psycopg2.extras.execute_batch(
            w,
            "INSERT INTO user_property_accesses (id, user_id, property_id, created_at, created_by_id) "
            "VALUES (%s, %s, %s, %s, %s)",
            rows,
        )
    dst.commit()
    return len(rows)


def reset_sequences(dst) -> None:
    """After preserving legacy IDs, push each sequence forward so future
    INSERTs don't collide with existing rows."""
    with dst.cursor() as w:
        for table in DEST_TABLES_WITH_SEQUENCES:
            w.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), "
                f"COALESCE((SELECT MAX(id) FROM {table}), 1), "
                f"(SELECT MAX(id) IS NOT NULL FROM {table}))"
            )
    dst.commit()


# ──────────────────────────────────────────────────────────────────────────────
# Driver
# ──────────────────────────────────────────────────────────────────────────────


COPIES: tuple[tuple[str, callable], ...] = (
    ("users", copy_users),
    ("properties", copy_properties),
    ("olt_cllis", copy_olt_cllis),
    ("seven_fifty_cllis", copy_seven_fifty_cllis),
    ("property_olt_clli", copy_property_olt_links),
    ("property_seven_fifty_clli", copy_property_seven_fifty_links),
    ("common_areas", copy_common_areas),
    ("eero_devices", copy_eero_devices),
    ("network_statuses", copy_network_statuses),
    ("connected_device_counts", copy_connected_device_counts),
    ("scheduled_maintenances", copy_scheduled_maintenances),
    ("maintenance_olt_clli", copy_maintenance_olt_links),
    ("maintenance_seven_fifty_clli", copy_maintenance_seven_fifty_links),
    ("user_property_accesses", copy_user_property_accesses),
)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--legacy-url", help="psycopg2-style URL for the legacy DB")
    p.add_argument("--new-url", help="psycopg2-style URL for the new wifimon DB")
    p.add_argument("--dry-run", action="store_true", help="connect + count, don't write")
    p.add_argument("--yes", action="store_true", help="skip the TRUNCATE confirmation")
    args = p.parse_args()

    legacy_url = args.legacy_url or discover_legacy_url()
    new_url = args.new_url or discover_new_url()
    if not legacy_url:
        print("ERR: legacy URL not provided and not auto-discoverable from", LEGACY_ENV, file=sys.stderr)
        return 2
    if not new_url:
        print("ERR: new URL not provided and not auto-discoverable from", NEW_ENV, file=sys.stderr)
        return 2

    print("▸ Connecting to legacy…")
    legacy = psycopg2.connect(legacy_url)
    legacy.set_session(readonly=True)

    if args.dry_run:
        print("▸ Dry run — counting source rows only (skipping destination connect)")
        with legacy.cursor() as r:
            for src_table in (
                "auth_user", "networks_property", "networks_oltclli", "networks_sevenfiftyclli",
                "networks_property_olt_cllis", "networks_property_seven_fifty_cllis",
                "networks_commonarea", "networks_eerodevice", "networks_networkstatus",
                "networks_connecteddevicecount", "networks_scheduledmaintenance",
                "networks_scheduledmaintenance_olt_cllis",
                "networks_scheduledmaintenance_seven_fifty_cllis", "networks_userpropertyaccess",
            ):
                r.execute(f"SELECT COUNT(*) FROM {src_table}")
                (n,) = r.fetchone()
                print(f"  {src_table:55s} {n}")
        return 0

    print("▸ Connecting to destination…")
    new = psycopg2.connect(new_url)

    if not args.yes:
        print()
        print("▸ About to TRUNCATE every destination table and repopulate from legacy.")
        print("  Destination DB:", _redact_url(new_url))
        ans = input("  Proceed? (yes/NO) ").strip().lower()
        if ans not in ("yes", "y"):
            print("  Aborted.")
            return 1

    print("▸ Truncating destination…")
    truncate_destination(new)

    print("▸ Copying tables…")
    for name, fn in COPIES:
        n = fn(legacy, new)
        print(f"  {name:30s} {n} rows")

    print("▸ Resetting sequences…")
    reset_sequences(new)

    print("✅ Migration complete.")
    return 0


def _redact_url(url: str) -> str:
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:***@", url)


if __name__ == "__main__":
    sys.exit(main())
