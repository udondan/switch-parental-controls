"""Error branches shared by all MCP tools: no client, unknown device, and API failures."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from switch_parental_controls import applications, devices, players, server
from switch_parental_controls.models import (
    AddExtraTimeInput,
    ClearCacheInput,
    DayOfWeek,
    DeviceInput,
    ListDevicesInput,
    MonthlySummaryInput,
    PlayerInput,
    PlaytimeInput,
    SetAppAllowListInput,
    SetBedtimeAlarmInput,
    SetBedtimeEndInput,
    SetContentRestrictionInput,
    SetDayRestrictionsInput,
    SetPlaytimeLimitInput,
    SetRestrictionModeInput,
    SetTimerModeInput,
)
from tests.conftest import make_mock_client, make_mock_device

DEVICE_ID = "device-001"

# Every tool that takes a device ID, with valid params for it.
DEVICE_TOOLS = [
    (devices.switch_get_device, lambda: DeviceInput(device_id=DEVICE_ID)),
    (devices.switch_get_today_summary, lambda: DeviceInput(device_id=DEVICE_ID)),
    (devices.switch_get_playtime, lambda: PlaytimeInput(device_id=DEVICE_ID)),
    (devices.switch_get_monthly_summary, lambda: MonthlySummaryInput(device_id=DEVICE_ID)),
    (devices.switch_set_daily_playtime_limit, lambda: SetPlaytimeLimitInput(device_id=DEVICE_ID, minutes=60)),
    (devices.switch_add_extra_time, lambda: AddExtraTimeInput(device_id=DEVICE_ID, minutes=15)),
    (devices.switch_set_timer_mode, lambda: SetTimerModeInput(device_id=DEVICE_ID, mode="DAILY")),
    (
        devices.switch_set_day_restrictions,
        lambda: SetDayRestrictionsInput(
            device_id=DEVICE_ID,
            day_of_week=DayOfWeek.MONDAY,
            playtime_enabled=True,
            max_playtime_minutes=60,
            bedtime_enabled=False,
        ),
    ),
    (devices.switch_set_restriction_mode, lambda: SetRestrictionModeInput(device_id=DEVICE_ID, mode="ALARM")),
    (
        devices.switch_set_content_restriction_level,
        lambda: SetContentRestrictionInput(device_id=DEVICE_ID, level="CHILDREN"),
    ),
    (devices.switch_set_bedtime_alarm, lambda: SetBedtimeAlarmInput(device_id=DEVICE_ID, hour=21, minute=0)),
    (devices.switch_set_bedtime_end_time, lambda: SetBedtimeEndInput(device_id=DEVICE_ID, hour=7, minute=0)),
    (players.switch_list_players, lambda: DeviceInput(device_id=DEVICE_ID)),
    (players.switch_get_player, lambda: PlayerInput(device_id=DEVICE_ID, player_id="player-001")),
    (applications.switch_list_applications, lambda: DeviceInput(device_id=DEVICE_ID)),
    (
        applications.switch_set_app_allow_list,
        lambda: SetAppAllowListInput(device_id=DEVICE_ID, application_id="app-001", allow=True),
    ),
]

ALL_TOOLS = [*DEVICE_TOOLS, (devices.switch_list_devices, lambda: ListDevicesInput())]

# Device methods that call the Nintendo API.
DEVICE_API_METHODS = [
    "update",
    "update_max_daily_playtime",
    "add_extra_time",
    "set_timer_mode",
    "set_daily_restrictions",
    "set_restriction_mode",
    "set_functional_restriction_level",
    "set_bedtime_alarm",
    "set_bedtime_end_time",
    "get_monthly_summary",
]


def _ids(tools):
    return [fn.__name__ for fn, _ in tools]


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


@pytest.mark.parametrize(("tool", "make_params"), ALL_TOOLS, ids=_ids(ALL_TOOLS))
async def test_tool_without_client(tool, make_params):
    server._state["client"] = None
    result = await tool(make_params(), MagicMock())
    assert result.startswith("Error: Not authenticated")


@pytest.mark.parametrize(("tool", "make_params"), DEVICE_TOOLS, ids=_ids(DEVICE_TOOLS))
async def test_tool_with_unknown_device(tool, make_params):
    server._state["client"] = make_mock_client(devices={})
    result = await tool(make_params(), MagicMock())
    assert result.startswith(f"Error: Device '{DEVICE_ID}' not found")


@pytest.mark.parametrize(("tool", "make_params"), ALL_TOOLS, ids=_ids(ALL_TOOLS))
async def test_tool_api_failure(tool, make_params):
    device = make_mock_device()
    for method in DEVICE_API_METHODS:
        setattr(device, method, AsyncMock(side_effect=RuntimeError("boom")))
    client = make_mock_client(devices={DEVICE_ID: device})
    client.update = AsyncMock(side_effect=RuntimeError("boom"))
    server._state["client"] = client

    result = await tool(make_params(), MagicMock())
    assert result == "Error: RuntimeError: boom"


async def test_clear_cache_failure():
    with patch("switch_parental_controls.devices.clear_data_cache", side_effect=RuntimeError("boom")):
        result = await devices.switch_clear_cache(ClearCacheInput(), MagicMock())
    assert result == "Error: RuntimeError: boom"
