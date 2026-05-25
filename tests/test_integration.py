"""Integration tests for Nintendo MCP tools and CLI using real Nintendo API credentials.

These tests call the actual Nintendo Parental Controls API. They require a
SWITCH_PARENTAL_CONTROL_SESSION_TOKEN set in a .env file or environment. All tests are
read-only — they do not modify any parental control settings.

Run:
    pytest -m integration tests/test_integration.py -v
"""

import json
import os
from unittest.mock import MagicMock

import aiohttp
import pytest
from click.testing import CliRunner

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def real_client():
    """Create a real Nintendo Parental Controls client, pre-fetched with a single update()."""
    from dotenv import load_dotenv

    load_dotenv()
    token = os.environ.get("SWITCH_PARENTAL_CONTROL_SESSION_TOKEN")
    if not token:
        pytest.skip("SWITCH_PARENTAL_CONTROL_SESSION_TOKEN not set")

    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    timezone = os.environ.get("SWITCH_PARENTAL_CONTROL_TIMEZONE") or "Europe/London"
    lang = os.environ.get("SWITCH_PARENTAL_CONTROL_LANG") or "en-GB"

    session = aiohttp.ClientSession()
    try:
        auth = Authenticator(session_token=token, client_session=session)
        await auth.async_complete_login(use_session_token=True)
        client = await NintendoParental.create(auth, timezone=timezone, lang=lang)
        await client.update()
        yield client
    finally:
        await session.close()


@pytest.fixture(autouse=True)
async def inject_client(real_client, monkeypatch):
    """Inject the real client into server state.

    The module fixture already called update() once. Stub out subsequent update()
    calls so tests don't hammer the Nintendo API — fresh data is already loaded.
    """
    from unittest.mock import AsyncMock

    from switch_parental_controls import server

    monkeypatch.setattr(real_client, "update", AsyncMock())
    for device in real_client.devices.values():
        monkeypatch.setattr(device, "update", AsyncMock())

    server._state["client"] = real_client
    yield
    server._state["client"] = None


@pytest.fixture(scope="module")
async def first_device_id(real_client):
    """Return the ID of the first device on the account (client already updated)."""
    if not real_client.devices:
        pytest.skip("No Nintendo Switch devices found on this account")
    return next(iter(real_client.devices))


async def test_list_devices():
    """Real device list should be returned as a non-empty string without error."""
    from switch_parental_controls.devices import switch_list_devices
    from switch_parental_controls.models import ListDevicesInput

    result = await switch_list_devices(ListDevicesInput(), MagicMock())
    assert "Error" not in result
    assert len(result) > 0


async def test_get_device(first_device_id):
    """Real device details should be returned without error."""
    from switch_parental_controls.devices import switch_get_device
    from switch_parental_controls.models import DeviceInput

    result = await switch_get_device(DeviceInput(device_id=first_device_id), MagicMock())
    assert "Error" not in result
    assert first_device_id in result


async def test_get_today_summary(first_device_id):
    """Today's summary should be returned without an auth error."""
    from switch_parental_controls.devices import switch_get_today_summary
    from switch_parental_controls.models import DeviceInput

    result = await switch_get_today_summary(DeviceInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_get_monthly_summary(first_device_id):
    """Monthly summary should be returned without an auth error."""
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    result = await switch_get_monthly_summary(MonthlySummaryInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_list_players(first_device_id):
    """Player list should be returned without an auth error."""
    from switch_parental_controls.models import DeviceInput
    from switch_parental_controls.players import switch_list_players

    result = await switch_list_players(DeviceInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_list_applications(first_device_id):
    """Application list should be returned without an auth error."""
    from switch_parental_controls.applications import switch_list_applications
    from switch_parental_controls.models import DeviceInput

    result = await switch_list_applications(DeviceInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


# ---------------------------------------------------------------------------
# CLI integration tests
# ---------------------------------------------------------------------------


@pytest.fixture()
def cli_runner(tmp_path, monkeypatch, real_client):
    """CliRunner that reuses the module-scoped real client to avoid extra API calls.

    Patches switch_client to yield the already-initialized real_client so CLI
    tests don't create a new Nintendo client (and call update()) for each test.
    """
    from contextlib import asynccontextmanager

    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROL_SESSION_TOKEN", "stub-token")

    @asynccontextmanager
    async def _stub_client(timezone, lang, token):
        yield real_client, None

    monkeypatch.setattr("switch_parental_controls.cli.switch_client", _stub_client)
    return CliRunner()


def test_cli_list_devices(cli_runner):
    """CLI list-devices should exit 0 and print device names."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["list-devices"])
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output
    assert len(result.output.strip()) > 0


def test_cli_list_devices_json(cli_runner):
    """CLI list-devices --format json should return parseable JSON with a 'devices' key."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["list-devices", "--format", "json"])
    assert result.exit_code == 0, result.output
    data = json.loads(result.output)
    assert "devices" in data


def test_cli_get_device(cli_runner, first_device_id):
    """CLI get-device should exit 0 and include the device ID in output."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["get-device", first_device_id])
    assert result.exit_code == 0, result.output
    assert first_device_id in result.output


def test_cli_today_summary(cli_runner, first_device_id):
    """CLI today-summary should exit 0 without an auth error."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["today-summary", first_device_id])
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output


def test_cli_monthly_summary(cli_runner, first_device_id):
    """CLI monthly-summary should complete without an auth error.

    Exit code is not asserted because Nintendo's monthly summary API can time
    out independently of authentication — the same leniency applied to the
    equivalent MCP integration test.
    """
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["monthly-summary", first_device_id])
    assert "Error: Not authenticated" not in result.output


def test_cli_list_players(cli_runner, first_device_id):
    """CLI list-players should exit 0 without an auth error."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["list-players", first_device_id])
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output


def test_cli_list_applications(cli_runner, first_device_id):
    """CLI list-applications should exit 0 without an auth error."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["list-applications", first_device_id])
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output


def test_cli_auto_select_single_device(cli_runner):
    """today-summary with no DEVICE arg auto-selects when only one device is on the account."""
    from switch_parental_controls.cli import cli

    # Populate the cache first so auto-select works without an extra API call.
    list_result = cli_runner.invoke(cli, ["list-devices"])
    assert list_result.exit_code == 0, list_result.output

    result = cli_runner.invoke(cli, ["today-summary"])
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output
