"""Tests for Nintendo MCP device tools."""

import json
from datetime import time
from unittest.mock import AsyncMock, MagicMock

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


# --- nintendo_get_monthly_summary ---


@pytest.mark.asyncio
async def test_get_monthly_summary_default(mock_device):
    """Should return most-recent monthly summary in markdown when no year/month given."""
    from nintendo_mcp.devices import nintendo_get_monthly_summary
    from nintendo_mcp.models import MonthlySummaryInput

    ctx = MagicMock()
    result = await nintendo_get_monthly_summary(MonthlySummaryInput(device_id="device-001"), ctx)

    mock_device.get_monthly_summary.assert_called_once_with(search_date=None)
    assert "April 2026" in result
    assert "20h" in result  # 1200 minutes


@pytest.mark.asyncio
async def test_get_monthly_summary_specific_month(mock_device):
    """Should pass a datetime to get_monthly_summary when year and month are provided."""
    from datetime import datetime

    from nintendo_mcp.devices import nintendo_get_monthly_summary
    from nintendo_mcp.models import MonthlySummaryInput

    ctx = MagicMock()
    await nintendo_get_monthly_summary(
        MonthlySummaryInput(device_id="device-001", year=2025, month=3), ctx
    )

    mock_device.get_monthly_summary.assert_called_once_with(search_date=datetime(2025, 3, 1))


@pytest.mark.asyncio
async def test_get_monthly_summary_none(mock_device):
    """Should return 'no summary' message when API returns None."""
    mock_device.get_monthly_summary = AsyncMock(return_value=None)

    from nintendo_mcp.devices import nintendo_get_monthly_summary
    from nintendo_mcp.models import MonthlySummaryInput

    ctx = MagicMock()
    result = await nintendo_get_monthly_summary(MonthlySummaryInput(device_id="device-001"), ctx)

    assert "No monthly summary available" in result


@pytest.mark.asyncio
async def test_get_monthly_summary_json(mock_device):
    """Should return JSON output when response_format is json."""
    from nintendo_mcp.devices import nintendo_get_monthly_summary
    from nintendo_mcp.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    result = await nintendo_get_monthly_summary(
        MonthlySummaryInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx
    )
    data = json.loads(result)

    assert data["device_name"] == "My Switch"
    assert data["summary"]["month"] == "April 2026"


# --- nintendo_set_timer_mode ---


@pytest.mark.asyncio
async def test_set_timer_mode_daily(mock_device):
    """Should call set_timer_mode with DAILY enum and return confirmation."""
    from pynintendoparental.enum import DeviceTimerMode

    from nintendo_mcp.devices import nintendo_set_timer_mode
    from nintendo_mcp.models import SetTimerModeInput

    ctx = MagicMock()
    result = await nintendo_set_timer_mode(
        SetTimerModeInput(device_id="device-001", mode="DAILY"), ctx
    )

    mock_device.set_timer_mode.assert_called_once_with(DeviceTimerMode.DAILY)
    assert "DAILY" in result
    assert "My Switch" in result


@pytest.mark.asyncio
async def test_set_timer_mode_each_day(mock_device):
    """Should call set_timer_mode with EACH_DAY_OF_THE_WEEK enum."""
    from pynintendoparental.enum import DeviceTimerMode

    from nintendo_mcp.devices import nintendo_set_timer_mode
    from nintendo_mcp.models import SetTimerModeInput

    ctx = MagicMock()
    result = await nintendo_set_timer_mode(
        SetTimerModeInput(device_id="device-001", mode="EACH_DAY_OF_THE_WEEK"), ctx
    )

    mock_device.set_timer_mode.assert_called_once_with(DeviceTimerMode.EACH_DAY_OF_THE_WEEK)
    assert "EACH_DAY_OF_THE_WEEK" in result


# --- nintendo_set_day_restrictions ---


@pytest.mark.asyncio
async def test_set_day_restrictions_playtime_only(mock_device):
    """Should call set_daily_restrictions with playtime enabled, no bedtime."""
    from nintendo_mcp.devices import nintendo_set_day_restrictions
    from nintendo_mcp.models import SetDayRestrictionsInput

    ctx = MagicMock()
    result = await nintendo_set_day_restrictions(
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=True,
            max_playtime_minutes=120,
            bedtime_enabled=False,
        ),
        ctx,
    )

    mock_device.set_daily_restrictions.assert_called_once_with(
        enabled=True,
        bedtime_enabled=False,
        day_of_week="MONDAY",
        bedtime_start=None,
        bedtime_end=None,
        max_daily_playtime=120,
    )
    assert "MONDAY" in result
    assert "2h" in result
    assert "Bedtime: disabled" in result


@pytest.mark.asyncio
async def test_set_day_restrictions_bedtime_only(mock_device):
    """Should call set_daily_restrictions with bedtime enabled, no playtime."""
    from nintendo_mcp.devices import nintendo_set_day_restrictions
    from nintendo_mcp.models import SetDayRestrictionsInput

    ctx = MagicMock()
    result = await nintendo_set_day_restrictions(
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="FRIDAY",
            playtime_enabled=False,
            bedtime_enabled=True,
            bedtime_alarm_hour=21,
            bedtime_alarm_minute=30,
            bedtime_end_hour=7,
            bedtime_end_minute=0,
        ),
        ctx,
    )

    mock_device.set_daily_restrictions.assert_called_once_with(
        enabled=False,
        bedtime_enabled=True,
        day_of_week="FRIDAY",
        bedtime_start=time(21, 30),
        bedtime_end=time(7, 0),
        max_daily_playtime=None,
    )
    assert "21:30" in result
    assert "07:00" in result
    assert "Playtime limit: disabled" in result


@pytest.mark.asyncio
async def test_set_day_restrictions_missing_bedtime_hour():
    """Should return error when bedtime_enabled but bedtime hours are missing."""
    from nintendo_mcp.devices import nintendo_set_day_restrictions
    from nintendo_mcp.models import SetDayRestrictionsInput

    ctx = MagicMock()
    result = await nintendo_set_day_restrictions(
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            bedtime_enabled=True,
        ),
        ctx,
    )

    assert "Error" in result
    assert "bedtime_alarm_hour" in result


def test_set_day_restrictions_playtime_disabled_with_minutes_rejected():
    """Model should reject max_playtime_minutes when playtime_enabled is false."""
    from pydantic import ValidationError

    from nintendo_mcp.models import SetDayRestrictionsInput

    with pytest.raises(ValidationError):
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            max_playtime_minutes=60,
            bedtime_enabled=False,
        )


def test_set_day_restrictions_bedtime_disabled_with_hours_rejected():
    """Model should reject bedtime hours when bedtime_enabled is false."""
    from pydantic import ValidationError

    from nintendo_mcp.models import SetDayRestrictionsInput

    with pytest.raises(ValidationError):
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            bedtime_enabled=False,
            bedtime_alarm_hour=21,
        )


# --- nintendo_set_bedtime_end_time ---


@pytest.mark.asyncio
async def test_set_bedtime_end_time(mock_device):
    """Should call set_bedtime_end_time with the specified time."""
    from nintendo_mcp.devices import nintendo_set_bedtime_end_time
    from nintendo_mcp.models import SetBedtimeEndInput

    ctx = MagicMock()
    result = await nintendo_set_bedtime_end_time(
        SetBedtimeEndInput(device_id="device-001", hour=7, minute=30), ctx
    )

    mock_device.set_bedtime_end_time.assert_called_once_with(time(7, 30))
    assert "07:30" in result
    assert "My Switch" in result


@pytest.mark.asyncio
async def test_set_bedtime_end_time_disable(mock_device):
    """Should return 'disabled' confirmation when hour=0 and minute=0."""
    from nintendo_mcp.devices import nintendo_set_bedtime_end_time
    from nintendo_mcp.models import SetBedtimeEndInput

    ctx = MagicMock()
    result = await nintendo_set_bedtime_end_time(
        SetBedtimeEndInput(device_id="device-001", hour=0, minute=0), ctx
    )

    mock_device.set_bedtime_end_time.assert_called_once_with(time(0, 0))
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
