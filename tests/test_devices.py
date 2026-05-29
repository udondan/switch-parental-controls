"""Tests for Nintendo MCP device tools."""

import json
from datetime import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from switch_parental_controls import server
from tests.conftest import make_mock_client, make_mock_device


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


@pytest.fixture
def mock_device():
    return make_mock_device()


@pytest.fixture
def mock_client(mock_device):
    return make_mock_client(devices={mock_device.device_id: mock_device})


@pytest.fixture(autouse=True)
def set_client(mock_client):
    server._state["client"] = mock_client


# --- switch_list_devices ---


@pytest.mark.asyncio
async def test_list_devices_no_client():
    """Should return auth error when client is not set."""
    server._state["client"] = None
    from switch_parental_controls.devices import switch_list_devices
    from switch_parental_controls.models import ListDevicesInput

    ctx = MagicMock()
    result = await switch_list_devices(ListDevicesInput(), ctx)
    assert "Error" in result
    assert "SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN" in result


@pytest.mark.asyncio
async def test_list_devices_markdown(mock_device, mock_client):
    """Should return markdown list of devices."""
    from switch_parental_controls.devices import switch_list_devices
    from switch_parental_controls.models import ListDevicesInput

    ctx = MagicMock()
    result = await switch_list_devices(ListDevicesInput(), ctx)

    assert "My Switch" in result
    assert "device-001" in result
    assert "45" in result  # today_playing_time


@pytest.mark.asyncio
async def test_list_devices_json(mock_device, mock_client):
    """Should return JSON list of devices."""
    from switch_parental_controls.devices import switch_list_devices
    from switch_parental_controls.models import ListDevicesInput, ResponseFormat

    ctx = MagicMock()
    result = await switch_list_devices(ListDevicesInput(response_format=ResponseFormat.JSON), ctx)
    data = json.loads(result)

    assert data["count"] == 1
    assert data["devices"][0]["device_id"] == "device-001"
    assert data["devices"][0]["name"] == "My Switch"


@pytest.mark.asyncio
async def test_list_devices_empty(mock_client):
    """Should return 'no devices' message when account has no devices."""
    mock_client.devices = {}
    from switch_parental_controls.devices import switch_list_devices
    from switch_parental_controls.models import ListDevicesInput

    ctx = MagicMock()
    result = await switch_list_devices(ListDevicesInput(), ctx)
    assert "No Nintendo Switch devices found" in result


# --- switch_get_device ---


@pytest.mark.asyncio
async def test_get_device_markdown(mock_device):
    """Should return detailed device info in markdown."""
    from switch_parental_controls.devices import switch_get_device
    from switch_parental_controls.models import DeviceInput

    ctx = MagicMock()
    result = await switch_get_device(DeviceInput(device_id="device-001"), ctx)

    assert "My Switch" in result
    assert "device-001" in result
    assert "DAILY" in result


@pytest.mark.asyncio
async def test_get_device_not_found():
    """Should return error for unknown device ID."""
    from switch_parental_controls.devices import switch_get_device
    from switch_parental_controls.models import DeviceInput

    ctx = MagicMock()
    result = await switch_get_device(DeviceInput(device_id="nonexistent"), ctx)
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_get_device_json(mock_device):
    """Should return JSON device info."""
    from switch_parental_controls.devices import switch_get_device
    from switch_parental_controls.models import DeviceInput, ResponseFormat

    ctx = MagicMock()
    result = await switch_get_device(DeviceInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx)
    data = json.loads(result)

    assert data["device_id"] == "device-001"
    assert data["name"] == "My Switch"
    assert data["limit_time_minutes"] == 120


# --- switch_get_today_summary ---


@pytest.mark.asyncio
async def test_get_today_summary(mock_device):
    """Should return today's usage summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_today_summary
    from switch_parental_controls.models import DeviceInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 4, 7, 12, 0)
        result = await switch_get_today_summary(DeviceInput(device_id="device-001"), ctx)

    assert "2026-04-07" in result
    assert "45" in result


# --- switch_set_daily_playtime_limit ---


@pytest.mark.asyncio
async def test_set_daily_playtime_limit(mock_device):
    """Should call update_max_daily_playtime and return confirmation."""
    from switch_parental_controls.devices import switch_set_daily_playtime_limit
    from switch_parental_controls.models import SetPlaytimeLimitInput

    ctx = MagicMock()
    result = await switch_set_daily_playtime_limit(SetPlaytimeLimitInput(device_id="device-001", minutes=180), ctx)

    mock_device.update_max_daily_playtime.assert_called_once_with(180)
    assert "3h" in result
    assert "My Switch" in result


@pytest.mark.asyncio
async def test_set_daily_playtime_limit_remove(mock_device):
    """Should remove the limit when minutes=-1."""
    from switch_parental_controls.devices import switch_set_daily_playtime_limit
    from switch_parental_controls.models import SetPlaytimeLimitInput

    ctx = MagicMock()
    result = await switch_set_daily_playtime_limit(SetPlaytimeLimitInput(device_id="device-001", minutes=-1), ctx)

    mock_device.update_max_daily_playtime.assert_called_once_with(-1)
    assert "removed" in result


# --- switch_add_extra_time ---


@pytest.mark.asyncio
async def test_add_extra_time(mock_device):
    """Should call add_extra_time and return confirmation."""
    from switch_parental_controls.devices import switch_add_extra_time
    from switch_parental_controls.models import AddExtraTimeInput

    ctx = MagicMock()
    result = await switch_add_extra_time(AddExtraTimeInput(device_id="device-001", minutes=30), ctx)

    mock_device.add_extra_time.assert_called_once_with(30)
    assert "30m" in result
    assert "My Switch" in result


# --- switch_set_restriction_mode ---


@pytest.mark.asyncio
async def test_set_restriction_mode_forced(mock_device):
    """Should set FORCED_TERMINATION mode."""
    from pynintendoparental.enum import RestrictionMode

    from switch_parental_controls.devices import switch_set_restriction_mode
    from switch_parental_controls.models import SetRestrictionModeInput

    ctx = MagicMock()
    result = await switch_set_restriction_mode(
        SetRestrictionModeInput(device_id="device-001", mode="FORCED_TERMINATION"), ctx
    )

    mock_device.set_restriction_mode.assert_called_once_with(RestrictionMode.FORCED_TERMINATION)
    assert "FORCED_TERMINATION" in result


@pytest.mark.asyncio
async def test_set_restriction_mode_alarm(mock_device):
    """Should set ALARM mode."""
    from pynintendoparental.enum import RestrictionMode

    from switch_parental_controls.devices import switch_set_restriction_mode
    from switch_parental_controls.models import SetRestrictionModeInput

    ctx = MagicMock()
    result = await switch_set_restriction_mode(SetRestrictionModeInput(device_id="device-001", mode="ALARM"), ctx)

    mock_device.set_restriction_mode.assert_called_once_with(RestrictionMode.ALARM)
    assert "ALARM" in result


# --- switch_set_bedtime_alarm ---


@pytest.mark.asyncio
async def test_set_bedtime_alarm(mock_device):
    """Should set bedtime alarm and return confirmation."""
    from switch_parental_controls.devices import switch_set_bedtime_alarm
    from switch_parental_controls.models import SetBedtimeAlarmInput

    ctx = MagicMock()
    result = await switch_set_bedtime_alarm(SetBedtimeAlarmInput(device_id="device-001", hour=21, minute=30), ctx)

    mock_device.set_bedtime_alarm.assert_called_once_with(time(21, 30))
    assert "21:30" in result


@pytest.mark.asyncio
async def test_set_bedtime_alarm_disable(mock_device):
    """Should disable bedtime alarm when hour=0, minute=0."""
    from switch_parental_controls.devices import switch_set_bedtime_alarm
    from switch_parental_controls.models import SetBedtimeAlarmInput

    ctx = MagicMock()
    result = await switch_set_bedtime_alarm(SetBedtimeAlarmInput(device_id="device-001", hour=0, minute=0), ctx)

    mock_device.set_bedtime_alarm.assert_called_once_with(time(0, 0))
    assert "disabled" in result


# --- switch_get_monthly_summary ---


@pytest.mark.asyncio
async def test_get_monthly_summary_default(mock_device):
    """Should return most-recent monthly summary in markdown when no year/month given."""
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    result = await switch_get_monthly_summary(MonthlySummaryInput(device_id="device-001"), ctx)

    mock_device.get_monthly_summary.assert_called_once_with(search_date=None)
    assert "April 2026" in result
    assert "20h" in result  # 1200 minutes total (600 + 600)


@pytest.mark.asyncio
async def test_get_monthly_summary_specific_month(mock_device):
    """Should pass a datetime to get_monthly_summary when year and month are provided."""
    from datetime import datetime

    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    await switch_get_monthly_summary(MonthlySummaryInput(device_id="device-001", year=2025, month=3), ctx)

    mock_device.get_monthly_summary.assert_called_once_with(search_date=datetime(2025, 3, 1))


@pytest.mark.asyncio
async def test_get_monthly_summary_none(mock_device):
    """Should return 'no summary' message when API returns None."""
    mock_device.get_monthly_summary = AsyncMock(return_value=None)

    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    result = await switch_get_monthly_summary(MonthlySummaryInput(device_id="device-001"), ctx)

    assert "No monthly summary available" in result


@pytest.mark.asyncio
async def test_get_monthly_summary_json(mock_device):
    """Should return JSON output when response_format is json."""
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    result = await switch_get_monthly_summary(
        MonthlySummaryInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx
    )
    data = json.loads(result)

    assert data["device_name"] == "My Switch"
    assert "overall" in data["summary"]
    assert data["summary"]["overall"]["dailyStats"][0]["date"] == "2026-04-01"


def test_get_monthly_summary_month_without_year_rejected():
    """Should reject month provided without year at model validation time."""
    import pytest
    from pydantic import ValidationError

    from switch_parental_controls.models import MonthlySummaryInput

    with pytest.raises(ValidationError, match="year is required when month is provided"):
        MonthlySummaryInput(device_id="device-001", month=5)


# --- switch_set_timer_mode ---


@pytest.mark.asyncio
async def test_set_timer_mode_daily(mock_device):
    """Should call set_timer_mode with DAILY enum and return confirmation."""
    from pynintendoparental.enum import DeviceTimerMode

    from switch_parental_controls.devices import switch_set_timer_mode
    from switch_parental_controls.models import SetTimerModeInput

    ctx = MagicMock()
    result = await switch_set_timer_mode(SetTimerModeInput(device_id="device-001", mode="DAILY"), ctx)

    mock_device.set_timer_mode.assert_called_once_with(DeviceTimerMode.DAILY)
    assert "DAILY" in result
    assert "My Switch" in result


@pytest.mark.asyncio
async def test_set_timer_mode_each_day(mock_device):
    """Should call set_timer_mode with EACH_DAY_OF_THE_WEEK enum."""
    from pynintendoparental.enum import DeviceTimerMode

    from switch_parental_controls.devices import switch_set_timer_mode
    from switch_parental_controls.models import SetTimerModeInput

    ctx = MagicMock()
    result = await switch_set_timer_mode(SetTimerModeInput(device_id="device-001", mode="EACH_DAY_OF_THE_WEEK"), ctx)

    mock_device.set_timer_mode.assert_called_once_with(DeviceTimerMode.EACH_DAY_OF_THE_WEEK)
    assert "EACH_DAY_OF_THE_WEEK" in result


# --- switch_set_day_restrictions ---


@pytest.mark.asyncio
async def test_set_day_restrictions_playtime_only(mock_device):
    """Should call set_daily_restrictions with playtime enabled, no bedtime."""
    from switch_parental_controls.devices import switch_set_day_restrictions
    from switch_parental_controls.models import SetDayRestrictionsInput

    ctx = MagicMock()
    result = await switch_set_day_restrictions(
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
    from switch_parental_controls.devices import switch_set_day_restrictions
    from switch_parental_controls.models import SetDayRestrictionsInput

    ctx = MagicMock()
    result = await switch_set_day_restrictions(
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


def test_set_day_restrictions_bedtime_enabled_without_alarm_hour_rejected():
    """Model should reject bedtime_enabled=True when bedtime_alarm_hour is missing."""
    from pydantic import ValidationError

    from switch_parental_controls.models import SetDayRestrictionsInput

    with pytest.raises(ValidationError, match="bedtime_alarm_hour"):
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            bedtime_enabled=True,
            bedtime_end_hour=7,
        )


def test_set_day_restrictions_playtime_disabled_with_minutes_rejected():
    """Model should reject max_playtime_minutes when playtime_enabled is false."""
    from pydantic import ValidationError

    from switch_parental_controls.models import SetDayRestrictionsInput

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

    from switch_parental_controls.models import SetDayRestrictionsInput

    with pytest.raises(ValidationError):
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            bedtime_enabled=False,
            bedtime_alarm_hour=21,
        )


def test_set_day_restrictions_bedtime_disabled_with_minutes_rejected():
    """Model should reject non-zero bedtime minutes when bedtime_enabled is false."""
    from pydantic import ValidationError

    from switch_parental_controls.models import SetDayRestrictionsInput

    with pytest.raises(ValidationError):
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            bedtime_enabled=False,
            bedtime_alarm_minute=30,
        )


def test_set_day_restrictions_bedtime_enabled_without_hours_rejected():
    """Model should reject bedtime_enabled=True when required hours are missing."""
    from pydantic import ValidationError

    from switch_parental_controls.models import SetDayRestrictionsInput

    with pytest.raises(ValidationError):
        SetDayRestrictionsInput(
            device_id="device-001",
            day_of_week="MONDAY",
            playtime_enabled=False,
            bedtime_enabled=True,
        )


# --- switch_set_bedtime_end_time ---


@pytest.mark.asyncio
async def test_set_bedtime_end_time(mock_device):
    """Should call set_bedtime_end_time with the specified time."""
    from switch_parental_controls.devices import switch_set_bedtime_end_time
    from switch_parental_controls.models import SetBedtimeEndInput

    ctx = MagicMock()
    result = await switch_set_bedtime_end_time(SetBedtimeEndInput(device_id="device-001", hour=7, minute=30), ctx)

    mock_device.set_bedtime_end_time.assert_called_once_with(time(7, 30))
    assert "07:30" in result
    assert "My Switch" in result


@pytest.mark.asyncio
async def test_set_bedtime_end_time_disable(mock_device):
    """Should return 'disabled' confirmation when hour=0 and minute=0."""
    from switch_parental_controls.devices import switch_set_bedtime_end_time
    from switch_parental_controls.models import SetBedtimeEndInput

    ctx = MagicMock()
    result = await switch_set_bedtime_end_time(SetBedtimeEndInput(device_id="device-001", hour=0, minute=0), ctx)

    mock_device.set_bedtime_end_time.assert_called_once_with(time(0, 0))
    assert "disabled" in result


# --- switch_set_content_restriction_level ---


@pytest.mark.asyncio
async def test_set_content_restriction_level(mock_device):
    """Should set content restriction level."""
    from pynintendoparental.enum import FunctionalRestrictionLevel

    from switch_parental_controls.devices import switch_set_content_restriction_level
    from switch_parental_controls.models import SetContentRestrictionInput

    ctx = MagicMock()
    result = await switch_set_content_restriction_level(
        SetContentRestrictionInput(device_id="device-001", level="CHILDREN"), ctx
    )

    mock_device.set_functional_restriction_level.assert_called_once_with(FunctionalRestrictionLevel.YOUNG_CHILD)
    assert "CHILDREN" in result


# --- switch_get_daily_breakdown ---


@pytest.mark.asyncio
async def test_daily_breakdown_no_client():
    """Should return auth error when client is not set."""
    server._state["client"] = None
    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    result = await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001"), ctx)
    assert "Error" in result
    assert "SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN" in result


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_markdown(mock_device):
    """Should return per-day markdown for the current month using daily_summaries."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001"), ctx)

    assert "May 2026" in result
    assert "(current)" in result
    assert "2026-05-01" in result
    assert "2026-05-02" in result
    assert "exceeded" in result
    assert "disabled" in result
    assert "2026-04-07" not in result


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_total(mock_device):
    """Should compute correct total for current month."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001"), ctx)

    # 60 + 90 = 150 minutes = 2h 30m
    assert "2h 30m" in result


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_json(mock_device):
    """Should return JSON with days array for current month."""
    import datetime
    import json
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx
        )

    data = json.loads(result)
    assert data["current"] is True
    assert data["year"] == 2026
    assert data["month"] == 5
    assert len(data["days"]) == 2
    assert data["days"][0]["date"] == "2026-05-01"
    assert data["days"][0]["playingTime"] == 60


@pytest.mark.asyncio
async def test_daily_breakdown_historical_month_markdown(mock_device):
    """Should return per-day markdown for a historical month using get_monthly_summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001", year=2026, month=4), ctx)

    assert "April 2026" in result
    assert "(current)" not in result
    assert "2026-04-01" in result
    assert "2026-04-02" in result


@pytest.mark.asyncio
async def test_daily_breakdown_historical_month_json(mock_device):
    """Should return JSON with days array for a historical month."""
    import datetime
    import json
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, response_format=ResponseFormat.JSON), ctx
        )

    data = json.loads(result)
    assert data["current"] is False
    assert data["year"] == 2026
    assert data["month"] == 4
    assert len(data["days"]) == 2
    assert data["days"][0]["date"] == "2026-04-01"
    assert data["days"][0]["totalTime"] == 600


@pytest.mark.asyncio
async def test_daily_breakdown_no_data(mock_device):
    """Should return 'no data' message when daily_summaries has no entries for the month."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    mock_device.daily_summaries = []
    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001"), ctx)

    assert "No daily data" in result
    assert "2026-05" in result


@pytest.mark.asyncio
async def test_daily_breakdown_unknown_device(mock_client):
    """Should return error for unknown device ID."""
    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    result = await switch_get_daily_breakdown(MonthlySummaryInput(device_id="no-such-device"), ctx)
    assert "Error" in result
    assert "no-such-device" in result


# --- cache behaviour for switch_get_monthly_summary ---


@pytest.mark.asyncio
async def test_monthly_summary_cache_miss_saves(mock_device):
    """Cache miss → API called → result saved to cache."""
    import datetime

    from switch_parental_controls.data_cache import load_data_cache
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        with patch("switch_parental_controls.data_cache.datetime") as mock_dc_dt:
            mock_dc_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
            await switch_get_monthly_summary(MonthlySummaryInput(device_id="device-001", year=2026, month=4), ctx)

    mock_device.get_monthly_summary.assert_called_once()
    assert load_data_cache("device-001", 2026, 4) is not None


@pytest.mark.asyncio
async def test_monthly_summary_cache_hit_skips_api(mock_device):
    """Cache hit → API not called → same data returned."""
    import datetime

    from switch_parental_controls.data_cache import save_data_cache
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    cached_summary = {
        "overall": {
            "dailyStats": [{"date": "2026-04-01", "totalTime": 300}],
        },
        "players": [],
    }
    save_data_cache("device-001", 2026, 4, cached_summary)

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        with patch("switch_parental_controls.data_cache.datetime") as mock_dc_dt:
            mock_dc_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
            params = MonthlySummaryInput(device_id="device-001", year=2026, month=4)
            result = await switch_get_monthly_summary(params, ctx)

    mock_device.get_monthly_summary.assert_not_called()
    assert "April 2026" in result
    assert "5h" in result  # 300 minutes


@pytest.mark.asyncio
async def test_monthly_summary_skip_cache_bypasses_hit(mock_device):
    """skip_cache=True → API called even when cache has data; cache not updated."""
    import datetime

    from switch_parental_controls.data_cache import load_data_cache, save_data_cache
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    old_data = {"overall": {"dailyStats": [{"date": "2026-04-01", "totalTime": 1}]}, "players": []}
    save_data_cache("device-001", 2026, 4, old_data)

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        with patch("switch_parental_controls.data_cache.datetime") as mock_dc_dt:
            mock_dc_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
            await switch_get_monthly_summary(
                MonthlySummaryInput(device_id="device-001", year=2026, month=4, skip_cache=True), ctx
            )

    mock_device.get_monthly_summary.assert_called_once()
    # Cache should still hold the old data (not overwritten)
    assert load_data_cache("device-001", 2026, 4) == old_data


@pytest.mark.asyncio
async def test_monthly_summary_current_month_not_cached(mock_device):
    """Current month → no cache read or write."""
    import datetime

    from switch_parental_controls.data_cache import load_data_cache
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        with patch("switch_parental_controls.data_cache.datetime") as mock_dc_dt:
            mock_dc_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
            await switch_get_monthly_summary(MonthlySummaryInput(device_id="device-001", year=2026, month=5), ctx)

    mock_device.get_monthly_summary.assert_called_once()
    assert load_data_cache("device-001", 2026, 5) is None


@pytest.mark.asyncio
async def test_monthly_summary_no_year_not_cached(mock_device):
    """No year/month → API always called, no cache interaction."""
    import datetime

    from switch_parental_controls.data_cache import _cache_dir
    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        await switch_get_monthly_summary(MonthlySummaryInput(device_id="device-001"), ctx)

    mock_device.get_monthly_summary.assert_called_once()
    # No cache files written (year/month unknown)

    cache_root = _cache_dir()
    assert not cache_root.exists() or not any(cache_root.rglob("*.json"))


# --- cache behaviour for switch_get_daily_breakdown ---


@pytest.mark.asyncio
async def test_daily_breakdown_past_month_cache_miss_saves(mock_device):
    """Cache miss for a past month → API called → result saved to cache."""
    import datetime

    from switch_parental_controls.data_cache import load_data_cache
    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        with patch("switch_parental_controls.data_cache.datetime") as mock_dc_dt:
            mock_dc_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
            await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001", year=2026, month=4), ctx)

    mock_device.get_monthly_summary.assert_called_once()
    assert load_data_cache("device-001", 2026, 4) is not None


@pytest.mark.asyncio
async def test_daily_breakdown_past_month_cache_hit_skips_api(mock_device):
    """Cache hit for a past month → API not called."""
    import datetime

    from switch_parental_controls.data_cache import save_data_cache
    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    save_data_cache(
        "device-001",
        2026,
        4,
        {"overall": {"dailyStats": [{"date": "2026-04-01", "totalTime": 120}]}, "players": []},
    )

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        with patch("switch_parental_controls.data_cache.datetime") as mock_dc_dt:
            mock_dc_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
            params = MonthlySummaryInput(device_id="device-001", year=2026, month=4)
            result = await switch_get_daily_breakdown(params, ctx)

    mock_device.get_monthly_summary.assert_not_called()
    assert "2026-04-01" in result


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_not_cached(mock_device):
    """Current month path uses daily_summaries; no cache file written."""
    import datetime

    from switch_parental_controls.data_cache import load_data_cache
    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        await switch_get_daily_breakdown(MonthlySummaryInput(device_id="device-001"), ctx)

    assert load_data_cache("device-001", 2026, 5) is None
    mock_device.get_monthly_summary.assert_not_called()


# --- switch_get_daily_breakdown day filter ---


def test_daily_breakdown_day_requires_year_month():
    """day without year/month should raise a validation error."""
    from switch_parental_controls.models import MonthlySummaryInput

    with pytest.raises(Exception, match="year and month are required"):
        MonthlySummaryInput(device_id="device-001", day=1)


@pytest.mark.asyncio
async def test_daily_breakdown_day_filter_current_month(mock_device):
    """day filter on current month returns a single-day summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=5, day=1), ctx
        )

    assert "Day Summary" in result
    assert "2026-05-01" in result
    assert "2026-05-02" not in result
    assert "Total" not in result


@pytest.mark.asyncio
async def test_daily_breakdown_day_filter_historical_month(mock_device):
    """day filter on a historical month returns a single-day summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, day=1), ctx
        )

    assert "Day Summary" in result
    assert "2026-04-01" in result
    assert "2026-04-02" not in result
    assert "Total" not in result


@pytest.mark.asyncio
async def test_daily_breakdown_day_filter_no_data(mock_device):
    """day filter with no matching date returns a 'No data' message."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, day=15), ctx
        )

    assert "No data available for 2026-04-15" in result


@pytest.mark.asyncio
async def test_daily_breakdown_day_filter_with_player(mock_device):
    """day filter combined with player_id returns a single-day summary for that player."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=5, day=1, player_id="player-001"), ctx
        )

    assert "Day Summary" in result
    assert "TestKid" in result
    assert "2026-05-01" in result
    assert "2026-05-02" not in result
    assert "Total" not in result


# --- switch_clear_cache ---


@pytest.mark.asyncio
async def test_clear_cache_tool_all(tmp_path, monkeypatch):
    """switch_clear_cache with no filters should clear all cache files."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from switch_parental_controls.data_cache import save_data_cache
    from switch_parental_controls.devices import switch_clear_cache
    from switch_parental_controls.models import ClearCacheInput

    save_data_cache("device-001", 2026, 3, {"dummy": True})
    save_data_cache("device-001", 2026, 4, {"dummy": True})

    ctx = MagicMock()
    result = await switch_clear_cache(ClearCacheInput(), ctx)
    assert "2" in result


@pytest.mark.asyncio
async def test_clear_cache_tool_no_files():
    """switch_clear_cache with empty cache returns 'no files found' message."""
    from switch_parental_controls.devices import switch_clear_cache
    from switch_parental_controls.models import ClearCacheInput

    ctx = MagicMock()
    result = await switch_clear_cache(ClearCacheInput(), ctx)
    assert "No cached files found" in result


@pytest.mark.asyncio
async def test_clear_cache_tool_specific_month(tmp_path, monkeypatch):
    """switch_clear_cache with year+month should delete only matching files."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    from switch_parental_controls.data_cache import load_data_cache, save_data_cache
    from switch_parental_controls.devices import switch_clear_cache
    from switch_parental_controls.models import ClearCacheInput

    save_data_cache("device-001", 2026, 3, {"dummy": True})
    save_data_cache("device-001", 2026, 4, {"dummy": True})

    ctx = MagicMock()
    await switch_clear_cache(ClearCacheInput(device_id="device-001", year=2026, month=3), ctx)

    assert load_data_cache("device-001", 2026, 3) is None
    assert load_data_cache("device-001", 2026, 4) is not None


# --- player filtering for switch_get_daily_breakdown ---


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_player_filter_markdown(mock_device):
    """Player filter on current month extracts per-player daily data from daily_summaries."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", player_id="player-001"), ctx
        )

    assert "TestKid" in result
    assert "May 2026" in result
    assert "(current)" in result
    assert "2026-05-01" in result
    assert "2026-05-02" in result
    # 45 + 75 = 120 minutes = 2h
    assert "2h" in result


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_player_filter_json(mock_device):
    """Player filter on current month returns JSON with player_id and per-player days."""
    import datetime
    import json
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", player_id="player-001", response_format=ResponseFormat.JSON),
            ctx,
        )

    data = json.loads(result)
    assert data["player_id"] == "player-001"
    assert data["player_nickname"] == "TestKid"
    assert data["current"] is True
    assert len(data["days"]) == 2
    assert data["days"][0]["date"] == "2026-05-01"
    assert data["days"][0]["playingTime"] == 45


@pytest.mark.asyncio
async def test_daily_breakdown_current_month_player_not_found(mock_device):
    """Player filter on current month returns error when player ID is not in daily_summaries."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", player_id="unknown-player"), ctx
        )

    assert "Error" in result
    assert "unknown-player" in result


@pytest.mark.asyncio
async def test_daily_breakdown_past_month_player_filter_markdown(mock_device):
    """Player filter on a past month returns that player's dailyStats from monthly summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, player_id="player-001"), ctx
        )

    assert "TestKid" in result
    assert "April 2026" in result
    assert "(current)" not in result
    assert "2026-04-01" in result
    assert "2026-04-02" in result
    # 600 + 600 = 1200 minutes = 20h
    assert "20h" in result


@pytest.mark.asyncio
async def test_daily_breakdown_past_month_player_filter_json(mock_device):
    """Player filter on a past month returns JSON with player_id and totalTime per day."""
    import datetime
    import json
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(
                device_id="device-001", year=2026, month=4, player_id="player-001",
                response_format=ResponseFormat.JSON
            ),
            ctx,
        )

    data = json.loads(result)
    assert data["player_id"] == "player-001"
    assert data["player_nickname"] == "TestKid"
    assert data["current"] is False
    assert len(data["days"]) == 2
    assert data["days"][0]["date"] == "2026-04-01"
    assert data["days"][0]["totalTime"] == 600


@pytest.mark.asyncio
async def test_daily_breakdown_past_month_player_not_found(mock_device):
    """Player filter on a past month returns error when player ID is absent from monthly summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_daily_breakdown
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_daily_breakdown(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, player_id="unknown-player"), ctx
        )

    assert "Error" in result
    assert "unknown-player" in result


# --- player filtering for switch_get_monthly_summary ---


@pytest.mark.asyncio
async def test_monthly_summary_player_filter_markdown(mock_device):
    """Player filter returns that player's total and per-day breakdown."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_monthly_summary(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, player_id="player-001"), ctx
        )

    assert "TestKid" in result
    assert "April 2026" in result
    assert "Daily Breakdown" in result
    assert "2026-04-01" in result
    assert "2026-04-02" in result
    # 600 + 600 = 1200 minutes = 20h
    assert "20h" in result


@pytest.mark.asyncio
async def test_monthly_summary_player_filter_json(mock_device):
    """Player filter in JSON mode returns only that player's entry."""
    import datetime
    import json
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_monthly_summary(
            MonthlySummaryInput(
                device_id="device-001", year=2026, month=4, player_id="player-001",
                response_format=ResponseFormat.JSON
            ),
            ctx,
        )

    data = json.loads(result)
    assert "player" in data
    assert data["player"]["profile"]["playerId"] == "player-001"
    assert data["player"]["profile"]["nickname"] == "TestKid"


@pytest.mark.asyncio
async def test_monthly_summary_player_not_found(mock_device):
    """Player filter returns error when player ID is not in the monthly summary."""
    import datetime
    from unittest.mock import patch

    from switch_parental_controls.devices import switch_get_monthly_summary
    from switch_parental_controls.models import MonthlySummaryInput

    ctx = MagicMock()
    with patch("switch_parental_controls.devices.datetime") as mock_dt:
        mock_dt.now.return_value = datetime.datetime(2026, 5, 15, 12, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime.datetime(*a, **kw)
        result = await switch_get_monthly_summary(
            MonthlySummaryInput(device_id="device-001", year=2026, month=4, player_id="unknown-player"), ctx
        )

    assert "Error" in result
    assert "unknown-player" in result
