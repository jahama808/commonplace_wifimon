"""`wifimon` CLI (SPEC §6.1).

Console script wired in `pyproject.toml`. Run:

    PYTHONPATH=. .venv/bin/python -m app.cli.main --help

Or after `pip install -e .`:

    wifimon --help

Each command opens its own session so the CLI can be invoked independently
of the web tier.
"""
from __future__ import annotations

import asyncio
import json
from typing import Optional

import typer
from sqlalchemy.exc import IntegrityError

from app.db.session import dispose_engine, get_engine
from app.eero.client import EeroClient
from app.schemas.admin import (
    AreaPreviewRequest,
    CommonAreaCreate,
    PropertyCreate,
)
from app.services import admin as svc
from app.services import yaml_importer
from app.services.polling import (
    check_all_devices,
    check_all_networks,
    record_device_counts,
)

app = typer.Typer(help="Common Area Monitor admin CLI", no_args_is_help=True)
property_app = typer.Typer(help="Manage properties", no_args_is_help=True)
area_app = typer.Typer(help="Manage common areas", no_args_is_help=True)
access_app = typer.Typer(help="Per-property access grants", no_args_is_help=True)
app.add_typer(property_app, name="property")
app.add_typer(area_app, name="area")
app.add_typer(access_app, name="access")


def _run(coro):
    """Run an async coroutine in a fresh event loop, then dispose the engine."""
    try:
        return asyncio.run(coro)
    finally:
        # New event loop for cleanup so we don't try to reuse a closed one.
        asyncio.run(dispose_engine())


# ──────────────────────────────────────────────────────────────────────────────
# property add / list
# ──────────────────────────────────────────────────────────────────────────────


@property_app.command("add")
def property_add(
    name: str = typer.Option(..., "--name", "-n", help="Unique property name"),
    address: Optional[str] = typer.Option(None, "--address", "-a"),
):
    """Create a new property."""

    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with sm() as s:
            try:
                p = await svc.create_property(s, PropertyCreate(name=name, address=address))
            except IntegrityError as e:
                typer.secho(f"failed: {e.orig}", fg=typer.colors.RED, err=True)
                raise typer.Exit(1)
            typer.echo(f"created property #{p.id}: {p.name}")

    _run(go())


@property_app.command("list")
def property_list(
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table"),
):
    """List all properties."""
    async def go():
        from sqlalchemy import func, select
        from sqlalchemy.ext.asyncio import async_sessionmaker

        from app.models.common_area import CommonArea
        from app.models.property import Property

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with sm() as s:
            rows = (
                await s.execute(
                    select(Property, func.count(CommonArea.id))
                    .outerjoin(CommonArea, CommonArea.property_id == Property.id)
                    .group_by(Property.id)
                    .order_by(Property.name)
                )
            ).all()
        if json_out:
            typer.echo(json.dumps([
                {"id": p.id, "name": p.name, "address": p.address, "areas": int(n)}
                for p, n in rows
            ], indent=2))
            return
        if not rows:
            typer.echo("(no properties)")
            return
        typer.echo(f"{'ID':>4}  {'NAME':<40}  {'AREAS':>5}  ADDRESS")
        for p, n in rows:
            typer.echo(f"{p.id:>4}  {p.name[:40]:<40}  {int(n):>5}  {p.address or ''}")

    _run(go())


# ──────────────────────────────────────────────────────────────────────────────
# area add / preview
# ──────────────────────────────────────────────────────────────────────────────


@area_app.command("preview")
def area_preview(
    network_id: str = typer.Option(..., "--network-id", "-n"),
    api_endpoint: Optional[str] = typer.Option(None, "--api-endpoint"),
):
    """Validate a network_id against the eero API without saving."""
    async def go():
        async with EeroClient() as c:
            preview = await svc.preview_common_area(
                AreaPreviewRequest(network_id=network_id, api_endpoint=api_endpoint),
                client=c,
            )
        typer.echo(json.dumps(preview.model_dump(), indent=2))
        if preview.error:
            raise typer.Exit(2)

    _run(go())


@area_app.command("add")
def area_add(
    property_id: int = typer.Option(..., "--property", "-p", help="Property ID (use `wifimon property list`)"),
    network_id: str = typer.Option(..., "--network-id", "-n"),
    location: str = typer.Option(..., "--location", "-l", help="Friendly location name"),
    location_type: str = typer.Option("indoor", "--type", "-t", help="indoor|outdoor"),
    island: Optional[str] = typer.Option(None, "--island"),
    description: Optional[str] = typer.Option(None, "--desc"),
    api_endpoint: Optional[str] = typer.Option(None, "--api-endpoint"),
    skip_preview: bool = typer.Option(
        False, "--skip-preview", help="Don't hit the eero API to validate first"
    ),
):
    """Add a common area to a property. Validates `network_id` against the
    eero API first unless `--skip-preview` is passed."""
    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)

        if not skip_preview:
            async with EeroClient() as c:
                preview = await svc.preview_common_area(
                    AreaPreviewRequest(network_id=network_id, api_endpoint=api_endpoint),
                    client=c,
                )
            if preview.error:
                typer.secho(
                    f"eero validation failed: {preview.error}", fg=typer.colors.RED, err=True
                )
                raise typer.Exit(2)
            typer.echo(
                f"validated: name={preview.network_name!r} ssid={preview.ssid!r} "
                f"eeros={preview.eero_count} online={preview.is_online}"
            )

        async with sm() as s:
            prop = await svc.get_property(s, property_id)
            if prop is None:
                typer.secho(f"no such property: {property_id}", fg=typer.colors.RED, err=True)
                raise typer.Exit(1)
            try:
                ca = await svc.create_common_area(
                    s,
                    prop,
                    CommonAreaCreate(
                        location_name=location,
                        network_id=network_id,
                        island=island,  # type: ignore[arg-type]
                        location_type=location_type,  # type: ignore[arg-type]
                        description=description,
                        api_endpoint=api_endpoint,
                    ),
                )
            except IntegrityError as e:
                typer.secho(f"failed: {e.orig}", fg=typer.colors.RED, err=True)
                raise typer.Exit(1)
            typer.echo(f"created area #{ca.id}: {ca.location_name} on {prop.name}")

    _run(go())


# ──────────────────────────────────────────────────────────────────────────────
# access grant / revoke
# ──────────────────────────────────────────────────────────────────────────────


@access_app.command("grant")
def access_grant(
    user_id: int = typer.Option(..., "--user", "-u"),
    property_id: int = typer.Option(..., "--property", "-p"),
):
    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with sm() as s:
            grant = await svc.grant_property_access(s, user_id, property_id)
        typer.echo(f"granted: user={grant.user_id} property={grant.property_id}")

    _run(go())


@access_app.command("revoke")
def access_revoke(
    user_id: int = typer.Option(..., "--user", "-u"),
    property_id: int = typer.Option(..., "--property", "-p"),
):
    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with sm() as s:
            ok = await svc.revoke_property_access(s, user_id, property_id)
        if ok:
            typer.echo("revoked")
        else:
            typer.secho("no such grant", fg=typer.colors.YELLOW, err=True)
            raise typer.Exit(2)

    _run(go())


# ──────────────────────────────────────────────────────────────────────────────
# check --force (manual trigger of polling)
# ──────────────────────────────────────────────────────────────────────────────


@app.command("import")
def import_yaml(
    file: str = typer.Option(..., "--file", "-f", help="Path to YAML seed file"),
    apply: bool = typer.Option(False, "--apply", help="Actually apply changes (default: dry-run, just print the diff)"),
    allow_deletes: bool = typer.Option(
        False,
        "--allow-deletes",
        help="Allow deleting properties / common areas not present in the YAML (default: upsert only)",
    ),
):
    """Idempotent YAML seed import (SPEC §6.1).

    Default is dry-run — prints what would happen. Add `--apply` to commit.
    Re-running an unchanged file converges to a zero-op plan.
    """
    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        try:
            doc = yaml_importer.load_yaml(file)
        except Exception as e:  # noqa: BLE001
            typer.secho(f"failed to parse YAML: {e}", fg=typer.colors.RED, err=True)
            raise typer.Exit(2)

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with sm() as s:
            plan = await yaml_importer.plan(s, doc, allow_deletes=allow_deletes)

        # Render the diff
        summary = plan.summary()
        for prop_op in plan.properties:
            tag = {
                "create": ("CREATE", typer.colors.GREEN),
                "update": ("UPDATE", typer.colors.YELLOW),
                "delete": ("DELETE", typer.colors.RED),
                "noop": ("noop  ", typer.colors.WHITE),
            }[prop_op.op]
            typer.secho(f"  property  {tag[0]}  {prop_op.name}", fg=tag[1])
            for k, (old, new) in prop_op.diff.items():
                typer.echo(f"           {k}: {old!r} → {new!r}")
        for area_op in plan.areas:
            tag = {
                "create": ("CREATE", typer.colors.GREEN),
                "update": ("UPDATE", typer.colors.YELLOW),
                "delete": ("DELETE", typer.colors.RED),
                "noop": ("noop  ", typer.colors.WHITE),
            }[area_op.op]
            typer.secho(
                f"  area      {tag[0]}  {area_op.network_id}  ({area_op.property_name})",
                fg=tag[1],
            )
            for k, (old, new) in area_op.diff.items():
                typer.echo(f"           {k}: {old!r} → {new!r}")

        typer.echo("")
        typer.echo(
            f"  summary  prop +{summary['properties_create']} ~{summary['properties_update']} -{summary['properties_delete']} ={summary['properties_noop']}"
            f"   area +{summary['areas_create']} ~{summary['areas_update']} -{summary['areas_delete']} ={summary['areas_noop']}"
        )

        if not plan.has_changes:
            typer.echo("  no changes — already in sync")
            return

        if not apply:
            typer.echo("\n  (dry run — pass --apply to commit)")
            return

        async with sm() as s:
            counts = await yaml_importer.apply(s, plan)
        typer.secho(
            f"  applied: {counts['properties_changed']} property change(s), "
            f"{counts['areas_changed']} area change(s), {counts['deleted']} deletion(s)",
            fg=typer.colors.GREEN,
        )

    _run(go())


@app.command("check")
def check(
    force: bool = typer.Option(False, "--force", help="Bypass per-network 1h rate limit"),
    devices: bool = typer.Option(True, "--devices/--no-devices"),
    counts: bool = typer.Option(True, "--counts/--no-counts"),
):
    """Run one tick of the polling jobs against every common area."""
    async def go():
        from sqlalchemy.ext.asyncio import async_sessionmaker

        sm = async_sessionmaker(get_engine(), expire_on_commit=False)
        async with EeroClient() as c, sm() as s:
            n = await check_all_networks(s, client=c, force=force)
            typer.echo(f"check_all_networks: {n} checked")
            if devices:
                n = await check_all_devices(s, client=c)
                typer.echo(f"check_all_devices: {n} checked")
            if counts:
                n = await record_device_counts(s, client=c)
                typer.echo(f"record_device_counts: {n} rows written")

    _run(go())


@app.command("test-notify")
def test_notify(
    skip: list[str] = typer.Option(
        [], "--skip", help="Skip a notification kind: network_offline / network_recovered / device_offline / device_recovered"
    ),
):
    """Smoke-test the notifier (SPEC §5.3).

    Fires one of each of the four notification kinds against the configured
    notifier (Pushover if `PUSHOVER_*` env is set, else NullNotifier which
    just logs). Doesn't touch the database. Exit 0 on success.
    """
    from app.models.common_area import CommonArea, Island, LocationType
    from app.models.eero_device import EeroDevice
    from app.models.property import Property
    from app.services.notifier import get_notifier

    async def go():
        notifier = get_notifier()
        typer.echo(f"using notifier: {type(notifier).__name__}")

        # Synthetic ORM objects — never persisted, just used for message
        # formatting in `_network_message()` / `_device_message()`.
        prop = Property()
        prop.id = 0
        prop.name = "wifimon test-notify"
        area = CommonArea()
        area.id = 0
        area.property = prop
        area.location_name = "Test Location"
        area.location_type = LocationType.INDOOR
        area.island = Island.OAHU
        area.network_id = "TEST"
        area.is_online = True

        device = EeroDevice()
        device.id = 0
        device.serial = "TEST-SERIAL"
        device.location = "Test Spot"
        device.location_type = LocationType.INDOOR
        device.model = "eero Test 1"

        kinds = [
            ("network_offline", lambda: notifier.send_network_offline(area)),
            ("network_recovered", lambda: notifier.send_network_recovered(area)),
            ("device_offline", lambda: notifier.send_device_offline(device, area)),
            ("device_recovered", lambda: notifier.send_device_recovered(device, area)),
        ]
        sent = 0
        for name, send in kinds:
            if name in skip:
                typer.echo(f"  skip   {name}")
                continue
            payload = await send()
            typer.echo(f"  sent   {name}: {payload.title} · {payload.message}")
            sent += 1
        typer.secho(f"done: {sent} notification(s)", fg=typer.colors.GREEN)

    _run(go())


def main() -> None:
    app()


if __name__ == "__main__":
    main()
