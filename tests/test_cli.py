"""Tests for the switch-parental-controls CLI.

Strategy: Each command test mocks `switch_parental_controls.cli.switch_client` to return a
pre-configured (mock_client, mock_session) pair, then patches the MCP tool function
to return a known string. This verifies argument parsing, _state population, and
output/exit-code behaviour without real network calls.

`resolve_device_id` is patched globally via the `auto_resolve` fixture so tests
don't touch the filesystem cache and "device-001" is always returned as-is.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from click.testing import CliRunner

from switch_parental_controls.cli import cli
from tests.conftest import make_mock_client, make_mock_device


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def mock_session():
    session = MagicMock()
    session.closed = False
    session.close = AsyncMock()
    return session


@pytest.fixture()
def mock_client_with_device():
    device = make_mock_device()
    return make_mock_client(devices={"device-001": device})


def _make_client_ctx(mock_client, mock_session):
    """Return a context manager mock that yields (mock_client, mock_session)."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=(mock_client, mock_session))
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.fixture(autouse=True)
def auto_resolve():
    """Patch resolve_device_id to return the passed value (or 'device-001' when None)."""
    with patch(
        "switch_parental_controls.cli.resolve_device_id",
        side_effect=lambda client, d: d if d is not None else "device-001",
    ):
        yield


@pytest.fixture(autouse=True)
def auto_save_cache():
    """Patch save_cache / devices_from_client so tests never write to disk."""
    with (
        patch("switch_parental_controls.cli.save_cache"),
        patch("switch_parental_controls.cli.devices_from_client", return_value={"device-001": "My Switch"}),
    ):
        yield


# ---------------------------------------------------------------------------
# Global: version
# ---------------------------------------------------------------------------


def test_version(runner):
    from importlib.metadata import version

    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert version("switch-parental-controls") in result.output


# ---------------------------------------------------------------------------
# Global: token guard
# ---------------------------------------------------------------------------


def test_list_devices_no_token(runner, monkeypatch):
    monkeypatch.delenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", raising=False)
    with patch("switch_parental_controls.credentials.load_token", return_value=None):
        result = runner.invoke(cli, ["list-devices"])
    assert result.exit_code == 1
    assert "login" in result.output


def test_get_device_no_token(runner, monkeypatch):
    monkeypatch.delenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", raising=False)
    with patch("switch_parental_controls.credentials.load_token", return_value=None):
        result = runner.invoke(cli, ["get-device", "device-001"])
    assert result.exit_code == 1


def test_invalid_token_shows_relogin_message(runner, monkeypatch):
    """When the saved token is rejected by Nintendo, the user sees a clear re-login prompt."""
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "expired-token")

    class FakeInvalidSessionTokenException(Exception):
        pass

    FakeInvalidSessionTokenException.__name__ = "InvalidSessionTokenException"

    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(side_effect=FakeInvalidSessionTokenException("invalid_grant"))
    ctx.__aexit__ = AsyncMock(return_value=False)

    with patch("switch_parental_controls.cli.switch_client", return_value=ctx):
        result = runner.invoke(cli, ["list-devices"])

    assert result.exit_code == 1
    assert "login" in result.output


def test_require_token_reads_credentials_file(runner, monkeypatch, mock_client_with_device, mock_session):
    """_require_token falls back to credentials file when env var is absent."""
    monkeypatch.delenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", raising=False)
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.credentials.load_token", return_value="token-from-file"),
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_list_devices",
            new=AsyncMock(return_value="# Devices"),
        ),
    ):
        result = runner.invoke(cli, ["list-devices"])

    assert result.exit_code == 0


# ---------------------------------------------------------------------------
# mcp subcommand
# ---------------------------------------------------------------------------


def test_mcp_subcommand_calls_server_main(runner):
    with patch("switch_parental_controls.server.main") as mock_main:
        runner.invoke(cli, ["mcp"])
    mock_main.assert_called_once()


# ---------------------------------------------------------------------------
# login command
# ---------------------------------------------------------------------------


def test_login_interactive_flow(runner, monkeypatch):
    monkeypatch.delenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", raising=False)

    mock_auth = MagicMock()
    mock_auth.login_url = "https://accounts.nintendo.com/login?state=abc"
    mock_auth.session_token = "test-session-token"
    mock_auth.async_complete_login = AsyncMock()

    mock_client = MagicMock()
    mock_client.update = AsyncMock()

    mock_http_session = MagicMock()
    mock_http_session.close = AsyncMock()

    with (
        patch("aiohttp.ClientSession", return_value=mock_http_session),
        patch("pynintendoparental.authenticator.Authenticator", return_value=mock_auth),
        patch("pynintendoparental.NintendoParental.create", new=AsyncMock(return_value=mock_client)),
        patch("switch_parental_controls.credentials.save_token", return_value="/home/user/.config/creds"),
    ):
        result = runner.invoke(cli, ["login"], input="npf71b963c1b7b6d119://auth?code=xyz\n")

    assert result.exit_code == 0
    assert "accounts.nintendo.com" in result.output
    assert "test-session-token" in result.output
    assert "SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN" in result.output
    mock_http_session.close.assert_awaited_once()


def test_login_saves_token(runner, monkeypatch):
    """Login saves the session token to the credentials file."""
    monkeypatch.delenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", raising=False)

    mock_auth = MagicMock()
    mock_auth.login_url = "https://accounts.nintendo.com/login?state=abc"
    mock_auth.session_token = "saved-token"
    mock_auth.async_complete_login = AsyncMock()

    mock_client = MagicMock()
    mock_client.update = AsyncMock()

    mock_http_session = MagicMock()
    mock_http_session.close = AsyncMock()

    with (
        patch("aiohttp.ClientSession", return_value=mock_http_session),
        patch("pynintendoparental.authenticator.Authenticator", return_value=mock_auth),
        patch("pynintendoparental.NintendoParental.create", new=AsyncMock(return_value=mock_client)),
        patch("switch_parental_controls.credentials.save_token", return_value="/home/user/.config/creds") as mock_save,
    ):
        result = runner.invoke(cli, ["login"], input="npf71b963c1b7b6d119://auth?code=xyz\n")

    assert result.exit_code == 0
    mock_save.assert_called_once_with("saved-token")


# ---------------------------------------------------------------------------
# logout
# ---------------------------------------------------------------------------


def test_logout_removes_credentials(runner):
    with patch("switch_parental_controls.credentials.delete_token", return_value=True):
        result = runner.invoke(cli, ["logout"])
    assert result.exit_code == 0
    assert "Logged out" in result.output


def test_logout_no_credentials(runner):
    with patch("switch_parental_controls.credentials.delete_token", return_value=False):
        result = runner.invoke(cli, ["logout"])
    assert result.exit_code == 0
    assert "Nothing to do" in result.output


# ---------------------------------------------------------------------------
# list-devices
# ---------------------------------------------------------------------------


def test_list_devices_markdown(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_list_devices",
            new=AsyncMock(return_value="# Devices\n- My Switch"),
        ),
    ):
        result = runner.invoke(cli, ["list-devices"])

    assert result.exit_code == 0
    assert "Devices" in result.output


def test_list_devices_json(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_list_devices",
            new=AsyncMock(return_value='{"count": 1}'),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["list-devices", "--format", "json"])

    assert result.exit_code == 0
    mock_tool.assert_awaited_once()
    # Verify response_format was JSON
    call_params = mock_tool.call_args[0][0]
    assert call_params.response_format == "json"


def test_list_devices_error_exits_1(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_list_devices",
            new=AsyncMock(return_value="Error: Not authenticated."),
        ),
    ):
        result = runner.invoke(cli, ["list-devices"])

    assert result.exit_code == 1


# ---------------------------------------------------------------------------
# get-device
# ---------------------------------------------------------------------------


def test_get_device(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_device",
            new=AsyncMock(return_value="# My Switch"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["get-device", "device-001"])

    assert result.exit_code == 0
    call_params = mock_tool.call_args[0][0]
    assert call_params.device_id == "device-001"


# ---------------------------------------------------------------------------
# today-summary
# ---------------------------------------------------------------------------


def test_today_summary(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_today_summary",
            new=AsyncMock(return_value="# Today's Summary"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["today-summary", "device-001"])

    assert result.exit_code == 0
    call_params = mock_tool.call_args[0][0]
    assert call_params.device_id == "device-001"


# ---------------------------------------------------------------------------
# monthly-summary
# ---------------------------------------------------------------------------


def test_monthly_summary_no_args(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_monthly_summary",
            new=AsyncMock(return_value="# Monthly Summary"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["monthly-summary", "device-001"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.year is None
    assert params.month is None


def test_monthly_summary_with_year_month(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_monthly_summary",
            new=AsyncMock(return_value="# Monthly Summary"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["monthly-summary", "device-001", "--year", "2024", "--month", "3"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.year == 2024
    assert params.month == 3


def test_monthly_summary_year_without_month_fails(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with patch("switch_parental_controls.cli.switch_client", return_value=ctx):
        result = runner.invoke(cli, ["monthly-summary", "device-001", "--year", "2024"])

    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# set-playtime-limit
# ---------------------------------------------------------------------------


def test_set_playtime_limit(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_daily_playtime_limit",
            new=AsyncMock(return_value="✓ Daily playtime limit set to 2h for 'My Switch'."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-playtime-limit", "device-001", "--minutes", "120"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.minutes == 120


def test_set_playtime_limit_remove(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_daily_playtime_limit",
            new=AsyncMock(return_value="✓ Daily playtime limit removed."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-playtime-limit", "device-001", "--no-limit"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.minutes == -1


def test_set_playtime_limit_invalid(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with patch("switch_parental_controls.cli.switch_client", return_value=ctx):
        result = runner.invoke(cli, ["set-playtime-limit", "device-001", "--minutes", "999"])

    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# add-extra-time
# ---------------------------------------------------------------------------


def test_add_extra_time(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_add_extra_time",
            new=AsyncMock(return_value="✓ Added 30m of extra playtime."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["add-extra-time", "device-001", "30"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.minutes == 30


# ---------------------------------------------------------------------------
# set-timer-mode
# ---------------------------------------------------------------------------


def test_set_timer_mode_daily(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_timer_mode",
            new=AsyncMock(return_value="✓ Timer mode set to 'DAILY'."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-timer-mode", "device-001", "DAILY"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.mode == "DAILY"


def test_set_timer_mode_invalid(runner, monkeypatch):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    result = runner.invoke(cli, ["set-timer-mode", "device-001", "INVALID_MODE"])
    assert result.exit_code != 0


# ---------------------------------------------------------------------------
# set-day-restrictions
# ---------------------------------------------------------------------------


def test_set_day_restrictions_playtime_only(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_day_restrictions",
            new=AsyncMock(return_value="✓ Restrictions updated for MONDAY."),
        ) as mock_tool,
    ):
        result = runner.invoke(
            cli,
            [
                "set-day-restrictions",
                "device-001",
                "MONDAY",
                "--playtime-enabled",
                "--max-playtime-minutes",
                "90",
                "--bedtime-disabled",
            ],
        )

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.day_of_week == "MONDAY"
    assert params.playtime_enabled is True
    assert params.max_playtime_minutes == 90
    assert params.bedtime_enabled is False


def test_set_day_restrictions_with_bedtime(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_day_restrictions",
            new=AsyncMock(return_value="✓ Restrictions updated for FRIDAY."),
        ) as mock_tool,
    ):
        result = runner.invoke(
            cli,
            [
                "set-day-restrictions",
                "device-001",
                "FRIDAY",
                "--playtime-enabled",
                "--max-playtime-minutes",
                "60",
                "--bedtime-enabled",
                "--bedtime-alarm-hour",
                "21",
                "--bedtime-alarm-minute",
                "30",
                "--bedtime-end-hour",
                "7",
                "--bedtime-end-minute",
                "0",
            ],
        )

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.bedtime_enabled is True
    assert params.bedtime_alarm_hour == 21


def test_set_day_restrictions_playtime_enabled_without_minutes_fails(
    runner, monkeypatch, mock_client_with_device, mock_session
):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with patch("switch_parental_controls.cli.switch_client", return_value=ctx):
        result = runner.invoke(
            cli,
            ["set-day-restrictions", "device-001", "MONDAY", "--playtime-enabled", "--bedtime-disabled"],
        )

    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# set-restriction-mode
# ---------------------------------------------------------------------------


def test_set_restriction_mode(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_restriction_mode",
            new=AsyncMock(return_value="✓ Restriction mode set."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-restriction-mode", "device-001", "ALARM"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.mode == "ALARM"


# ---------------------------------------------------------------------------
# set-content-restriction
# ---------------------------------------------------------------------------


def test_set_content_restriction(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_content_restriction_level",
            new=AsyncMock(return_value="✓ Content restriction level set."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-content-restriction", "device-001", "CHILDREN"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.level == "CHILDREN"


# ---------------------------------------------------------------------------
# set-bedtime-alarm
# ---------------------------------------------------------------------------


def test_set_bedtime_alarm(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_bedtime_alarm",
            new=AsyncMock(return_value="✓ Bedtime alarm set to 21:00."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-bedtime-alarm", "device-001", "21", "0"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.hour == 21
    assert params.minute == 0


def test_set_bedtime_alarm_invalid_hour(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with patch("switch_parental_controls.cli.switch_client", return_value=ctx):
        result = runner.invoke(cli, ["set-bedtime-alarm", "device-001", "14", "0"])

    assert result.exit_code == 1
    assert "Error" in result.output


# ---------------------------------------------------------------------------
# set-bedtime-end
# ---------------------------------------------------------------------------


def test_set_bedtime_end(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_set_bedtime_end_time",
            new=AsyncMock(return_value="✓ Bedtime end set to 07:00."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-bedtime-end", "device-001", "7", "0"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.hour == 7


# ---------------------------------------------------------------------------
# list-players
# ---------------------------------------------------------------------------


def test_list_players(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.players.switch_list_players",
            new=AsyncMock(return_value="# Players"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["list-players", "device-001"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.device_id == "device-001"


# ---------------------------------------------------------------------------
# get-player
# ---------------------------------------------------------------------------


def test_get_player(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.players.switch_get_player",
            new=AsyncMock(return_value="# Player: TestKid"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["get-player", "device-001", "player-001"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.device_id == "device-001"
    assert params.player_id == "player-001"


# ---------------------------------------------------------------------------
# list-applications
# ---------------------------------------------------------------------------


def test_list_applications(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.applications.switch_list_applications",
            new=AsyncMock(return_value="# Applications"),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["list-applications", "device-001"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.device_id == "device-001"


# ---------------------------------------------------------------------------
# set-app-allow-list
# ---------------------------------------------------------------------------


def test_set_app_allow_list_allow(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.applications.switch_set_app_allow_list",
            new=AsyncMock(return_value="✓ App added to allow list."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-app-allow-list", "device-001", "app-001", "--allow"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.allow is True
    assert params.application_id == "app-001"


def test_set_app_allow_list_deny(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.applications.switch_set_app_allow_list",
            new=AsyncMock(return_value="✓ App removed from allow list."),
        ) as mock_tool,
    ):
        result = runner.invoke(cli, ["set-app-allow-list", "device-001", "app-001", "--no-allow"])

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.allow is False


# ---------------------------------------------------------------------------
# Global options: --timezone / --lang
# ---------------------------------------------------------------------------


def test_global_timezone_option(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx) as mock_nc,
        patch(
            "switch_parental_controls.devices.switch_list_devices",
            new=AsyncMock(return_value="# Devices"),
        ),
    ):
        runner.invoke(cli, ["--timezone", "America/New_York", "list-devices"])

    mock_nc.assert_called_once_with("America/New_York", "en-GB", "fake-token")


def test_global_lang_option(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx) as mock_nc,
        patch(
            "switch_parental_controls.devices.switch_list_devices",
            new=AsyncMock(return_value="# Devices"),
        ),
    ):
        runner.invoke(cli, ["--lang", "de-DE", "list-devices"])

    mock_nc.assert_called_once_with("Europe/London", "de-DE", "fake-token")


# ---------------------------------------------------------------------------
# --player flag on monthly-summary and playtime
# ---------------------------------------------------------------------------


def test_monthly_summary_player_flag(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_monthly_summary",
            new=AsyncMock(return_value="# Monthly Summary"),
        ) as mock_tool,
    ):
        result = runner.invoke(
            cli, ["monthly-summary", "device-001", "--year", "2026", "--month", "4", "--player", "player-001"]
        )

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.player_id == "player-001"
    assert params.year == 2026
    assert params.month == 4


def test_playtime_player_flag(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_playtime",
            new=AsyncMock(return_value="# Daily Breakdown"),
        ) as mock_tool,
    ):
        result = runner.invoke(
            cli, ["playtime", "device-001", "--year", "2026", "--month", "4", "--player", "player-001"]
        )

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.player_id == "player-001"
    assert params.year == 2026
    assert params.month == 4


def test_playtime_day_flag(runner, monkeypatch, mock_client_with_device, mock_session):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "fake-token")
    ctx = _make_client_ctx(mock_client_with_device, mock_session)

    with (
        patch("switch_parental_controls.cli.switch_client", return_value=ctx),
        patch(
            "switch_parental_controls.devices.switch_get_playtime",
            new=AsyncMock(return_value="# Day Summary"),
        ) as mock_tool,
    ):
        result = runner.invoke(
            cli, ["playtime", "device-001", "--year", "2026", "--month", "4", "--day", "1"]
        )

    assert result.exit_code == 0
    params = mock_tool.call_args[0][0]
    assert params.day == 1
    assert params.year == 2026
    assert params.month == 4
