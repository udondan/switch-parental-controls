"""Integration tests for Nintendo MCP tools and CLI using real Nintendo API credentials.

These tests call the actual Nintendo Parental Controls API. They require
SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN to be set in a .env file or environment. All tests are
read-only — they do not modify any parental control settings.

Run:
    pytest -m integration tests/test_integration.py -v
"""

import json
import os
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from click.testing import CliRunner

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def real_client():
    """Create a real Nintendo Parental Controls client, pre-fetched with a single update()."""
    from dotenv import load_dotenv

    load_dotenv()
    token = os.environ.get("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN")
    if not token:
        pytest.skip("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN not set")

    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    timezone = os.environ.get("SWITCH_PARENTAL_CONTROLS_TIMEZONE") or "Europe/London"
    lang = os.environ.get("SWITCH_PARENTAL_CONTROLS_LANG") or "en-GB"

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


async def test_get_playtime(first_device_id):
    """Daily breakdown for the current month should be returned without an auth error."""
    from switch_parental_controls.devices import switch_get_playtime
    from switch_parental_controls.models import PlaytimeInput

    result = await switch_get_playtime(PlaytimeInput(device_id=first_device_id), MagicMock())
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
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "stub-token")

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


def test_cli_playtime(cli_runner, first_device_id):
    """CLI playtime should exit 0 and return current-month data without an auth error."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["playtime", first_device_id])
    assert result.exit_code == 0, result.output
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


# ---------------------------------------------------------------------------
# Cache integration tests — MCP
# ---------------------------------------------------------------------------

_PAST_YEAR = 2026
_PAST_MONTH = 4


async def test_get_monthly_summary_past_month_creates_cache(
    first_device_id, tmp_path, monkeypatch, real_client
):
    """Fetching a past month writes a cache file."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from switch_parental_controls.data_cache import _cache_path
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    params = MonthlySummaryInput(device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH)
    result = await switch_get_monthly_summary(params, MagicMock())
    assert "Error: Not authenticated" not in result
    assert _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()


async def test_get_monthly_summary_past_month_cache_hit(
    first_device_id, tmp_path, monkeypatch, real_client
):
    """Second call for the same past month is served from cache — API not called."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from switch_parental_controls.data_cache import save_data_cache
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    minimal = {"overall": {"dailyStats": [{"date": f"{_PAST_YEAR}-{_PAST_MONTH:02d}-01", "totalTime": 60}]}, "players": []}  # noqa: E501
    save_data_cache(first_device_id, _PAST_YEAR, _PAST_MONTH, minimal)

    params = MonthlySummaryInput(device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH)
    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(side_effect=AssertionError("API called on cache hit"))

    result = await switch_get_monthly_summary(params, MagicMock())
    assert "Error" not in result


async def test_get_monthly_summary_skip_cache(first_device_id, tmp_path, monkeypatch, real_client):
    """skip_cache=True always hits the API even when a cache file exists."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from switch_parental_controls.data_cache import save_data_cache
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    save_data_cache(first_device_id, _PAST_YEAR, _PAST_MONTH, {"sentinel": True})

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    params = MonthlySummaryInput(device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH, skip_cache=True)
    result = await switch_get_monthly_summary(params, MagicMock())
    assert "Error: Not authenticated" not in result
    assert "sentinel" not in result


async def test_get_playtime_past_month_creates_cache(
    first_device_id, tmp_path, monkeypatch, real_client
):
    """playtime for a past month writes a cache file."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from switch_parental_controls.data_cache import _cache_path
    from switch_parental_controls.devices import switch_get_playtime
    from switch_parental_controls.models import PlaytimeInput

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    params = PlaytimeInput(device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH)
    result = await switch_get_playtime(params, MagicMock())
    assert "Error: Not authenticated" not in result
    assert _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()


async def test_get_playtime_past_month_cache_hit(
    first_device_id, tmp_path, monkeypatch, real_client
):
    """Second playtime call for a past month uses the cache."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from switch_parental_controls.data_cache import save_data_cache
    from switch_parental_controls.devices import switch_get_playtime
    from switch_parental_controls.models import PlaytimeInput

    minimal = {"overall": {"dailyStats": [{"date": f"{_PAST_YEAR}-{_PAST_MONTH:02d}-01", "totalTime": 60}]}, "players": []}  # noqa: E501
    save_data_cache(first_device_id, _PAST_YEAR, _PAST_MONTH, minimal)

    params = PlaytimeInput(device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH)
    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(side_effect=AssertionError("API called on cache hit"))

    result = await switch_get_playtime(params, MagicMock())
    assert "Error" not in result


async def test_switch_clear_cache(first_device_id, tmp_path, monkeypatch):
    """switch_clear_cache removes the cache files it is asked to delete."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))

    from switch_parental_controls.data_cache import _cache_path, save_data_cache
    from switch_parental_controls.devices import switch_clear_cache
    from switch_parental_controls.models import ClearCacheInput

    save_data_cache(first_device_id, _PAST_YEAR, _PAST_MONTH, {"x": 1})
    assert _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()

    result = await switch_clear_cache(
        ClearCacheInput(device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH), MagicMock()
    )
    assert "1" in result
    assert not _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()


# ---------------------------------------------------------------------------
# Cache integration tests — CLI
# ---------------------------------------------------------------------------


def test_cli_monthly_summary_past_month_creates_cache(cli_runner, first_device_id, real_client):
    """CLI monthly-summary with --year/--month creates a cache file when the API returns data."""
    from switch_parental_controls.cli import cli
    from switch_parental_controls.data_cache import _cache_path

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    result = cli_runner.invoke(
        cli, ["monthly-summary", first_device_id, "--year", str(_PAST_YEAR), "--month", str(_PAST_MONTH)]
    )
    assert "Error: Not authenticated" not in result.output
    assert _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()


def test_cli_monthly_summary_no_cache(cli_runner, first_device_id, real_client):
    """CLI monthly-summary --no-cache completes without auth error."""
    from switch_parental_controls.cli import cli

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    result = cli_runner.invoke(
        cli,
        ["monthly-summary", first_device_id, "--year", str(_PAST_YEAR), "--month", str(_PAST_MONTH), "--no-cache"],
    )
    assert "Error: Not authenticated" not in result.output


def test_cli_playtime_past_month_creates_cache(cli_runner, first_device_id, real_client):
    """CLI playtime with --year/--month creates a cache file when the API returns data."""
    from switch_parental_controls.cli import cli
    from switch_parental_controls.data_cache import _cache_path

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    result = cli_runner.invoke(
        cli, ["playtime", first_device_id, "--year", str(_PAST_YEAR), "--month", str(_PAST_MONTH)]
    )
    assert "Error: Not authenticated" not in result.output
    assert _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()


def test_cli_playtime_no_cache(cli_runner, first_device_id, real_client):
    """CLI playtime --no-cache completes without auth error."""
    from switch_parental_controls.cli import cli

    device = real_client.devices[first_device_id]
    device.get_monthly_summary = AsyncMock(return_value=device.last_month_summary)

    result = cli_runner.invoke(
        cli,
        ["playtime", first_device_id, "--year", str(_PAST_YEAR), "--month", str(_PAST_MONTH), "--no-cache"],
    )
    assert "Error: Not authenticated" not in result.output


def test_cli_clear_cache(cli_runner, first_device_id, tmp_path):
    """CLI clear-cache removes a specific cached month and reports the count."""
    from switch_parental_controls.cli import cli
    from switch_parental_controls.data_cache import _cache_path, save_data_cache

    save_data_cache(first_device_id, _PAST_YEAR, _PAST_MONTH, {"x": 1})
    assert _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()

    result = cli_runner.invoke(
        cli,
        ["clear-cache", "--device", first_device_id, "--year", str(_PAST_YEAR), "--month", str(_PAST_MONTH)],
    )
    assert result.exit_code == 0, result.output
    assert "1" in result.output
    assert not _cache_path(first_device_id, _PAST_YEAR, _PAST_MONTH).exists()


def test_cli_clear_cache_no_files(cli_runner):
    """CLI clear-cache with no cached files prints the zero-match message."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["clear-cache", "--year", "2000", "--month", "1"])
    assert result.exit_code == 0, result.output
    assert "No cached files" in result.output


# ---------------------------------------------------------------------------
# Player filter integration tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
async def first_player_id(real_client, first_device_id):
    """Return the ID of the first player on the first device, or skip if none."""
    device = real_client.devices[first_device_id]
    await device.update()
    if not device.players:
        pytest.skip("No players found on this device")
    return next(iter(device.players))


async def test_playtime_player_filter_current_month(first_device_id, first_player_id):
    """Daily breakdown filtered by player should return that player's data without error."""
    from switch_parental_controls.devices import switch_get_playtime
    from switch_parental_controls.models import PlaytimeInput

    params = PlaytimeInput(device_id=first_device_id, player_id=first_player_id)
    result = await switch_get_playtime(params, MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result
    assert "Error: Player" not in result


async def test_playtime_player_filter_past_month(first_device_id, first_player_id):
    """Daily breakdown for a past month filtered by player should return per-player daily stats."""
    from switch_parental_controls.devices import switch_get_playtime
    from switch_parental_controls.models import PlaytimeInput

    params = PlaytimeInput(
        device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH, player_id=first_player_id
    )
    result = await switch_get_playtime(params, MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_monthly_summary_player_filter(first_device_id, first_player_id):
    """Monthly summary filtered by player should return that player's total and breakdown."""
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    params = MonthlySummaryInput(
        device_id=first_device_id, year=_PAST_YEAR, month=_PAST_MONTH, player_id=first_player_id
    )
    result = await switch_get_monthly_summary(params, MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result
    assert "Error: Player" not in result


def test_cli_playtime_player_flag(cli_runner, first_device_id, first_player_id):
    """CLI playtime --player exits 0 with player-filtered data for the current month."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(cli, ["playtime", first_device_id, "--player", first_player_id])
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output


def test_cli_monthly_summary_player_flag(cli_runner, first_device_id, first_player_id):
    """CLI monthly-summary --player exits 0 with player-filtered data for a past month."""
    from switch_parental_controls.cli import cli

    result = cli_runner.invoke(
        cli,
        [
            "monthly-summary", first_device_id,
            "--year", str(_PAST_YEAR), "--month", str(_PAST_MONTH),
            "--player", first_player_id,
        ],
    )
    assert result.exit_code == 0, result.output
    assert "Error" not in result.output
