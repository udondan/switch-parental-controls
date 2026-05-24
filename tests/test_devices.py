"""Tests for Nintendo MCP device tools."""

from datetime import time
from unittest.mock import MagicMock

import pytest

from nintendo_mcp import server
from tests.conftest import make_mock_client, make_mock_device


@pytest.fixture
def mock_device():
    return make_mock_device()


@pytest.fixture
def mock_client(mock_device):
    return make_mock_client(devices={mock_device.device_id: mock_device})


@pytest.fixture(autouse=True)
def set_client(mock_client):
    server._state["client"] = mock_client


# --- nintendo_list_devices ---


@pytest.mark.asyncio
async def test_list_devices_no_client():
    """Should return auth error when client is not set."""
    server._state["client"] = None
    from nintendo_mcp.devices import nintendo_list_devices
    from nintendo_mcp.models import ListDevicesInput

    ctx = MagicMock()
    result = await nintendo_list_devices(ListDevicesInput(), ctx)
    assert "Error" in result
    assert "NINTENDO_SESSION_TOKEN" in result


@pytest.mark.asyncio
async def test_list_devices_markdown(mock_device, mock_client):
    """Should return markdown list of devices."""
    from nintendo_mcp.devices import nintendo_list_devices
    from nintendo_mcp.models import ListDevicesInput

    ctx = MagicMock()
    result = await nintendo_list_devices(ListDevicesInput(), ctx)

    assert "My Switch" in result
    assert "device-001" in result
    assert "45" in result  # today_playing_time


@pytest.mark.asyncio
async def test_list_devices_json(mock_device, mock_client):
    """Should return JSON list of devices."""
    import json

    from nintendo_mcp.devices import nintendo_list_devices
    from nintendo_mcp.models import ListDevicesInput, ResponseFormat

    ctx = MagicMock()
    result = await nintendo_list_devices(ListDevicesInput(response_format=ResponseFormat.JSON), ctx)
    data = json.loads(result)

    assert data["count"] == 1
    assert data["devices"][0]["device_id"] == "device-001"
    assert data["devices"][0]["name"] == "My Switch"


@pytest.mark.asyncio
async def test_list_devices_empty(mock_client):
    """Should return 'no devices' message when account has no devices."""
    mock_client.devices = {}
    from nintendo_mcp.devices import nintendo_list_devices
    from nintendo_mcp.models import ListDevicesInput

    ctx = MagicMock()
    result = await nintendo_list_devices(ListDevicesInput(), ctx)
    assert "No Nintendo Switch devices found" in result


# --- nintendo_get_device ---


@pytest.mark.asyncio
async def test_get_device_markdown(mock_device):
    """Should return detailed device info in markdown."""
    from nintendo_mcp.devices import nintendo_get_device
    from nintendo_mcp.models import DeviceInput

    ctx = MagicMock()
    result = await nintendo_get_device(DeviceInput(device_id="device-001"), ctx)

    assert "My Switch" in result
    assert "device-001" in result
    assert "DAILY" in result


@pytest.mark.asyncio
async def test_get_device_not_found():
    """Should return error for unknown device ID."""
    from nintendo_mcp.devices import nintendo_get_device
    from nintendo_mcp.models import DeviceInput

    ctx = MagicMock()
    result = await nintendo_get_device(DeviceInput(device_id="nonexistent"), ctx)
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_get_device_json(mock_device):
    """Should return JSON device info."""
    import json

    from nintendo_mcp.devices import nintendo_get_device
    from nintendo_mcp.models import DeviceInput, ResponseFormat

    ctx = MagicMock()
    result = await nintendo_get_device(
        DeviceInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx
    )
    data = json.loads(result)

    assert data["device_id"] == "device-001"
    assert data["name"] == "My Switch"
    assert data["limit_time_minutes"] == 120


# --- nintendo_get_today_summary ---


@pytest.mark.asyncio
async def test_get_today_summary(mock_device):
    """Should return today's usage summary."""
    import datetime
    from unittest.mock import patch

    from nintendo_mcp.devices import nintendo_get_today_summary
    from nintendo_mcp.models import DeviceInput

    ctx = MagicMock()
    with patch("nintendo_mcp.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 4, 7, 12, 0)
        result = await nintendo_get_today_summary(DeviceInput(device_id="device-001"), ctx)

    assert "2026-04-07" in result
    assert "45" in result


# --- nintendo_set_daily_playtime_limit ---


@pytest.mark.asyncio
async def test_set_daily_playtime_limit(mock_device):
    """Should call update_max_daily_playtime and return confirmation."""
    from nintendo_mcp.devices import nintendo_set_daily_playtime_limit
    from nintendo_mcp.models import SetPlaytimeLimitInput

    ctx = MagicMock()
    result = await nintendo_set_daily_playtime_limit(
        SetPlaytimeLimitInput(device_id="device-001", minutes=180), ctx
    )

    mock_device.update_max_daily_playtime.assert_called_once_with(180)
    assert "3h" in result
    assert "My Switch" in result


@pytest.mark.asyncio
async def test_set_daily_playtime_limit_remove(mock_device):
    """Should remove the limit when minutes=-1."""
    from nintendo_mcp.devices import nintendo_set_daily_playtime_limit
    from nintendo_mcp.models import SetPlaytimeLimitInput

    ctx = MagicMock()
    result = await nintendo_set_daily_playtime_limit(
        SetPlaytimeLimitInput(device_id="device-001", minutes=-1), ctx
    )

    mock_device.update_max_daily_playtime.assert_called_once_with(-1)
    assert "removed" in result


# --- nintendo_add_extra_time ---


@pytest.mark.asyncio
async def test_add_extra_time(mock_device):
    """Should call add_extra_time and return confirmation."""
    from nintendo_mcp.devices import nintendo_add_extra_time
    from nintendo_mcp.models import AddExtraTimeInput

    ctx = MagicMock()
    result = await nintendo_add_extra_time(
        AddExtraTimeInput(device_id="device-001", minutes=30), ctx
    )

    mock_device.add_extra_time.assert_called_once_with(30)
    assert "30m" in result
    assert "My Switch" in result


# --- nintendo_set_restriction_mode ---


@pytest.mark.asyncio
async def test_set_restriction_mode_forced(mock_device):
    """Should set FORCED_TERMINATION mode."""
    from pynintendoparental.enum import RestrictionMode

    from nintendo_mcp.devices import nintendo_set_restriction_mode
    from nintendo_mcp.models import SetRestrictionModeInput

    ctx = MagicMock()
    result = await nintendo_set_restriction_mode(
        SetRestrictionModeInput(device_id="device-001", mode="FORCED_TERMINATION"), ctx
    )

    mock_device.set_restriction_mode.assert_called_once_with(RestrictionMode.FORCED_TERMINATION)
    assert "FORCED_TERMINATION" in result


@pytest.mark.asyncio
async def test_set_restriction_mode_alarm(mock_device):
    """Should set ALARM mode."""
    from pynintendoparental.enum import RestrictionMode

    from nintendo_mcp.devices import nintendo_set_restriction_mode
    from nintendo_mcp.models import SetRestrictionModeInput

    ctx = MagicMock()
    result = await nintendo_set_restriction_mode(
        SetRestrictionModeInput(device_id="device-001", mode="ALARM"), ctx
    )

    mock_device.set_restriction_mode.assert_called_once_with(RestrictionMode.ALARM)
    assert "ALARM" in result


# --- nintendo_set_bedtime_alarm ---


@pytest.mark.asyncio
async def test_set_bedtime_alarm(mock_device):
    """Should set bedtime alarm and return confirmation."""
    from nintendo_mcp.devices import nintendo_set_bedtime_alarm
    from nintendo_mcp.models import SetBedtimeAlarmInput

    ctx = MagicMock()
    result = await nintendo_set_bedtime_alarm(
        SetBedtimeAlarmInput(device_id="device-001", hour=21, minute=30), ctx
    )

    mock_device.set_bedtime_alarm.assert_called_once_with(time(21, 30))
    assert "21:30" in result


@pytest.mark.asyncio
async def test_set_bedtime_alarm_disable(mock_device):
    """Should disable bedtime alarm when hour=0, minute=0."""
    from nintendo_mcp.devices import nintendo_set_bedtime_alarm
    from nintendo_mcp.models import SetBedtimeAlarmInput

    ctx = MagicMock()
    result = await nintendo_set_bedtime_alarm(
        SetBedtimeAlarmInput(device_id="device-001", hour=0, minute=0), ctx
    )

    mock_device.set_bedtime_alarm.assert_called_once_with(time(0, 0))
    assert "disabled" in result


# --- nintendo_set_content_restriction_level ---


@pytest.mark.asyncio
async def test_set_content_restriction_level(mock_device):
    """Should set content restriction level."""
    from pynintendoparental.enum import FunctionalRestrictionLevel

    from nintendo_mcp.devices import nintendo_set_content_restriction_level
    from nintendo_mcp.models import SetContentRestrictionInput

    ctx = MagicMock()
    result = await nintendo_set_content_restriction_level(
        SetContentRestrictionInput(device_id="device-001", level="CHILDREN"), ctx
    )

    mock_device.set_functional_restriction_level.assert_called_once_with(
        FunctionalRestrictionLevel.YOUNG_CHILD
    )
    assert "CHILDREN" in result
