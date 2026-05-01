"""Tests for the admin service + CLI surface.

DB-touching paths aren't covered (no Postgres in this repo). The eero
preview is testable with a fake EeroClient, and the CLI's typer wiring is
testable via CliRunner without ever opening a session.
"""
from __future__ import annotations

import pytest
from typer.testing import CliRunner

from app.cli.main import app as cli_app
from app.eero.client import EeroResponse
from app.schemas.admin import AreaPreviewRequest
from app.services.admin import preview_common_area

runner = CliRunner()


class _FakeEeroClient:
    """Implements just enough of `EeroClient` for the preview path."""

    def __init__(self, network_payload, eeros_payload, network_ok=True, eeros_ok=True):
        self._network = network_payload
        self._eeros = eeros_payload
        self._network_ok = network_ok
        self._eeros_ok = eeros_ok

    async def get_network(self, target):
        return EeroResponse(
            payload=self._network,
            status_code=200 if self._network_ok else 503,
            response_time_ms=10,
            error_message="" if self._network_ok else "HTTP 503",
        )

    async def get_eeros(self, target):
        return EeroResponse(
            payload=self._eeros,
            status_code=200 if self._eeros_ok else 503,
            response_time_ms=10,
            error_message="" if self._eeros_ok else "HTTP 503",
        )


class TestPreviewCommonArea:
    @pytest.mark.asyncio
    async def test_happy_path(self):
        client = _FakeEeroClient(
            network_payload={
                "name": "Lobby",
                "ssid": "Guest",
                "wan_ip": "1.2.3.4",
                "health": {"internet": {"status": "connected"}},
            },
            eeros_payload=[
                {"serial": "AA1"}, {"serial": "AA2"}, {"serial": "AA3"},
            ],
        )
        out = await preview_common_area(
            AreaPreviewRequest(network_id="6422927"), client=client
        )
        assert out.network_id == "6422927"
        assert out.network_name == "Lobby"
        assert out.ssid == "Guest"
        assert out.wan_ip == "1.2.3.4"
        assert out.eero_count == 3
        assert out.is_online is True
        assert out.error is None

    @pytest.mark.asyncio
    async def test_through_data_envelope(self):
        client = _FakeEeroClient(
            network_payload={"data": {"name": "Lobby", "status": "green"}},
            eeros_payload={"data": [{"serial": "X"}]},
        )
        out = await preview_common_area(
            AreaPreviewRequest(network_id="x"), client=client
        )
        assert out.network_name == "Lobby"
        assert out.eero_count == 1
        assert out.is_online is True

    @pytest.mark.asyncio
    async def test_network_failure_surfaces_error(self):
        client = _FakeEeroClient(
            network_payload=None, eeros_payload=None, network_ok=False
        )
        out = await preview_common_area(
            AreaPreviewRequest(network_id="missing"), client=client
        )
        assert out.network_id == "missing"
        assert out.error == "HTTP 503"
        assert out.eero_count == 0  # never queried

    @pytest.mark.asyncio
    async def test_eero_list_failure_doesnt_kill_preview(self):
        # Network call succeeds but /eeros fails — we should still return
        # the metadata we have, with eero_count=0.
        client = _FakeEeroClient(
            network_payload={"name": "Lobby", "status": "green"},
            eeros_payload=None,
            eeros_ok=False,
        )
        out = await preview_common_area(
            AreaPreviewRequest(network_id="x"), client=client
        )
        assert out.network_name == "Lobby"
        assert out.eero_count == 0
        assert out.is_online is True
        assert out.error is None  # the network check itself succeeded

    @pytest.mark.asyncio
    async def test_offline_network(self):
        client = _FakeEeroClient(
            network_payload={"name": "Lobby", "status": "red"},
            eeros_payload=[],
        )
        out = await preview_common_area(
            AreaPreviewRequest(network_id="x"), client=client
        )
        assert out.is_online is False
        assert out.network_name == "Lobby"


class TestCli:
    """Typer wiring: every subcommand renders --help cleanly. We don't
    invoke commands that touch the DB here (no Postgres in this repo)."""

    def test_top_level_help(self):
        r = runner.invoke(cli_app, ["--help"])
        assert r.exit_code == 0
        assert "property" in r.stdout
        assert "area" in r.stdout
        assert "access" in r.stdout
        assert "check" in r.stdout

    def test_property_subcommands(self):
        r = runner.invoke(cli_app, ["property", "--help"])
        assert r.exit_code == 0
        assert "add" in r.stdout
        assert "list" in r.stdout

    def test_area_subcommands(self):
        r = runner.invoke(cli_app, ["area", "--help"])
        assert r.exit_code == 0
        assert "add" in r.stdout
        assert "preview" in r.stdout

    def test_access_subcommands(self):
        r = runner.invoke(cli_app, ["access", "--help"])
        assert r.exit_code == 0
        assert "grant" in r.stdout
        assert "revoke" in r.stdout

    def test_property_add_requires_name(self):
        r = runner.invoke(cli_app, ["property", "add"])
        assert r.exit_code != 0
        assert "name" in r.stdout.lower() or "name" in (r.stderr or "").lower()

    def test_area_add_requires_property(self):
        r = runner.invoke(cli_app, ["area", "add"])
        assert r.exit_code != 0
