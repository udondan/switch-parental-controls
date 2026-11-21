"""Device setting tools for the Nintendo MCP server.

Provides tools to change the parental control settings of a Nintendo Switch
device, and to clear the local cache of historic play data.
"""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import time

from mcp.server.mcpserver import Context
from pynintendoparental.enum import DeviceTimerMode, FunctionalRestrictionLevel, RestrictionMode

from switch_parental_controls.data_cache import clear_data_cache, cleared_message
from switch_parental_controls.models import (
    AddExtraTimeInput,
    ClearCacheInput,
    SetBedtimeAlarmInput,
    SetBedtimeEndInput,
    SetContentRestrictionInput,
    SetDayRestrictionsInput,
    SetPlaytimeLimitInput,
    SetRestrictionModeInput,
    SetTimerModeInput,
)
from switch_parental_controls.server import mcp
from switch_parental_controls.tools import get_device, tool_annotations
from switch_parental_controls.utils import format_minutes, handle_error


async def _apply_setting(
    device_id: str,
    apply: Callable[..., Awaitable],
    message: Callable[..., str],
) -> str:
    """Apply a setting to the device and return the confirmation message, or an error message."""
    try:
        device = get_device(device_id)
        await apply(device)
        return message(device)
    except Exception as e:
        return handle_error(e)


@dataclass(frozen=True)
class _Choice:
    """A setting that takes one value of an enum."""

    setter: str
    enum_type: type
    label: str


_TIMER_MODE = _Choice("set_timer_mode", DeviceTimerMode, "Timer mode")
_CONTENT_LEVEL = _Choice("set_functional_restriction_level", FunctionalRestrictionLevel, "Content restriction level")


async def _set_choice(choice: _Choice, device_id: str, value: str) -> str:
    return await _apply_setting(
        device_id,
        lambda device: getattr(device, choice.setter)(choice.enum_type(value)),
        lambda device: f"✓ {choice.label} set to '{value}' for '{device.name}'.",
    )


def _playtime_limit_message(minutes: int, device) -> str:
    if minutes == -1:
        return f"✓ Daily playtime limit removed for '{device.name}'."
    return f"✓ Daily playtime limit set to {format_minutes(minutes)} for '{device.name}'."


@mcp.tool(
    name="switch_set_daily_playtime_limit",
    annotations=tool_annotations("Set Daily Playtime Limit", read_only=False),
)
async def switch_set_daily_playtime_limit(params: SetPlaytimeLimitInput, ctx: Context) -> str:
    """Set the daily playtime limit for a Nintendo Switch device.

    Sets the maximum number of minutes the device can be used per day.
    Use -1 to remove the limit entirely.

    Args:
        params (SetPlaytimeLimitInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - minutes (int): Daily limit in minutes (0-360), or -1 to remove the limit.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the value is out of range or the API call fails.
    """
    return await _apply_setting(
        params.device_id,
        lambda device: device.update_max_daily_playtime(params.minutes),
        lambda device: _playtime_limit_message(params.minutes, device),
    )


@mcp.tool(
    name="switch_add_extra_time",
    annotations=tool_annotations("Add Extra Playtime", read_only=False, idempotent=False),
)
async def switch_add_extra_time(params: AddExtraTimeInput, ctx: Context) -> str:
    """Add extra playtime for the current day on a Nintendo Switch device.

    Grants additional playing time beyond the configured daily limit for today only.
    The extra time does not carry over to other days.

    Args:
        params (AddExtraTimeInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - minutes (int): Number of extra minutes to add (1-360).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the API call fails.
    """
    return await _apply_setting(
        params.device_id,
        lambda device: device.add_extra_time(params.minutes),
        lambda device: f"✓ Added {format_minutes(params.minutes)} of extra playtime for '{device.name}' today.",
    )


@mcp.tool(name="switch_set_timer_mode", annotations=tool_annotations("Set Timer Mode", read_only=False))
async def switch_set_timer_mode(params: SetTimerModeInput, ctx: Context) -> str:
    """Set the timer mode for a Nintendo Switch device.

    Controls whether a single daily limit applies to all days, or whether
    different limits can be set for each day of the week.

    Args:
        params (SetTimerModeInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - mode (str): 'DAILY' for a single limit, or 'EACH_DAY_OF_THE_WEEK' for per-day limits.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the mode is invalid or the API call fails.
    """
    return await _set_choice(_TIMER_MODE, params.device_id, params.mode)


def _hh_mm(hour: int | None, minute: int | None) -> str:
    return f"{hour:02d}:{minute or 0:02d}"


def _describe_restrictions(params: SetDayRestrictionsInput, device) -> str:
    """Confirmation message of switch_set_day_restrictions."""
    if params.playtime_enabled and params.max_playtime_minutes is not None:
        playtime = format_minutes(params.max_playtime_minutes)
    else:
        playtime = "disabled"
    if params.bedtime_enabled:
        bedtime = (
            f"{_hh_mm(params.bedtime_alarm_hour, params.bedtime_alarm_minute)} → "
            f"{_hh_mm(params.bedtime_end_hour, params.bedtime_end_minute)}"
        )
    else:
        bedtime = "disabled"
    return "\n".join(
        [
            f"✓ Restrictions updated for {params.day_of_week.value} on '{device.name}'.",
            f"  Playtime limit: {playtime}",
            f"  Bedtime: {bedtime}",
        ]
    )


async def _set_day_restrictions(device, params: SetDayRestrictionsInput) -> None:
    bedtime_start = None
    bedtime_end = None
    if params.bedtime_enabled:
        bedtime_start = time(params.bedtime_alarm_hour, params.bedtime_alarm_minute or 0)
        bedtime_end = time(params.bedtime_end_hour, params.bedtime_end_minute or 0)

    await device.set_daily_restrictions(
        enabled=params.playtime_enabled,
        bedtime_enabled=params.bedtime_enabled,
        day_of_week=params.day_of_week.value,
        bedtime_start=bedtime_start,
        bedtime_end=bedtime_end,
        max_daily_playtime=params.max_playtime_minutes if params.playtime_enabled else None,
    )


@mcp.tool(
    name="switch_set_day_restrictions",
    annotations=tool_annotations("Set Per-Day Restrictions", read_only=False),
)
async def switch_set_day_restrictions(params: SetDayRestrictionsInput, ctx: Context) -> str:
    """Set playtime and bedtime restrictions for a specific day of the week.

    For per-day restrictions to take effect, the device's timer mode should be
    EACH_DAY_OF_THE_WEEK. Use switch_set_timer_mode first if needed.

    Args:
        params (SetDayRestrictionsInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - day_of_week (str): Day to configure (e.g. 'MONDAY').
            - playtime_enabled (bool): Whether to enable a playtime limit for this day.
            - max_playtime_minutes (Optional[int]): Limit in minutes (0-360). Required if playtime_enabled.
            - bedtime_enabled (bool): Whether to enable bedtime restrictions.
            - bedtime_alarm_hour (Optional[int]): Bedtime alarm hour (16-23). Required if bedtime_enabled.
            - bedtime_alarm_minute (Optional[int]): Bedtime alarm minute (0-59).
            - bedtime_end_hour (Optional[int]): Hour when bedtime ends (5-9). Required if bedtime_enabled.
            - bedtime_end_minute (Optional[int]): Minute when bedtime ends (0-59).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: ..." if bedtime values are out of range.
    """
    return await _apply_setting(
        params.device_id,
        lambda device: _set_day_restrictions(device, params),
        lambda device: _describe_restrictions(params, device),
    )


_RESTRICTION_MODE_DESCRIPTIONS = {
    "FORCED_TERMINATION": "software will be suspended when the limit is reached",
    "ALARM": "an alarm will be shown but software will not be suspended",
}


@mcp.tool(name="switch_set_restriction_mode", annotations=tool_annotations("Set Restriction Mode", read_only=False))
async def switch_set_restriction_mode(params: SetRestrictionModeInput, ctx: Context) -> str:
    """Set the restriction mode for a Nintendo Switch device.

    Controls what happens when the daily playtime limit is reached:
    either the software is suspended (FORCED_TERMINATION) or only an alarm
    is shown (ALARM).

    Args:
        params (SetRestrictionModeInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - mode (str): 'FORCED_TERMINATION' or 'ALARM'.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the API call fails.
    """
    description = _RESTRICTION_MODE_DESCRIPTIONS.get(params.mode, _RESTRICTION_MODE_DESCRIPTIONS["ALARM"])
    return await _apply_setting(
        params.device_id,
        lambda device: device.set_restriction_mode(RestrictionMode[params.mode]),
        lambda device: f"✓ Restriction mode set to '{params.mode}' for '{device.name}' ({description}).",
    )


@mcp.tool(
    name="switch_set_content_restriction_level",
    annotations=tool_annotations("Set Content Restriction Level", read_only=False),
)
async def switch_set_content_restriction_level(params: SetContentRestrictionInput, ctx: Context) -> str:
    """Set the content restriction level for a Nintendo Switch device.

    Controls which games and applications can be launched based on their age rating.

    Args:
        params (SetContentRestrictionInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - level (str): One of: 'NONE', 'CHILDREN', 'YOUNG_TEENS', 'OLDER_TEENS', 'CUSTOM'.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the level is invalid or the API call fails.
    """
    return await _set_choice(_CONTENT_LEVEL, params.device_id, params.level)


async def _set_bedtime_time(params: SetBedtimeAlarmInput | SetBedtimeEndInput, setter: str, label: str) -> str:
    """Set the bedtime alarm or end time. 00:00 disables it."""

    def message(device) -> str:
        if params.hour == 0 and params.minute == 0:
            return f"✓ {label} disabled for '{device.name}'."
        return f"✓ {label} set to {params.hour:02d}:{params.minute:02d} for '{device.name}'."

    return await _apply_setting(
        params.device_id,
        lambda device: getattr(device, setter)(time(params.hour, params.minute)),
        message,
    )


@mcp.tool(name="switch_set_bedtime_alarm", annotations=tool_annotations("Set Bedtime Alarm", read_only=False))
async def switch_set_bedtime_alarm(params: SetBedtimeAlarmInput, ctx: Context) -> str:
    """Set the bedtime alarm time for a Nintendo Switch device.

    The bedtime alarm notifies that bedtime has arrived. Must be between 16:00 and 23:00.
    Use hour=0, minute=0 to disable the alarm.

    Args:
        params (SetBedtimeAlarmInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - hour (int): Alarm hour (16-23, or 0 to disable).
            - minute (int): Alarm minute (0-59).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: ..." if the time is outside the valid range (16:00-23:00).
        - Returns "Error: Not authenticated..." if no session token is configured.
    """
    return await _set_bedtime_time(params, "set_bedtime_alarm", "Bedtime alarm")


@mcp.tool(name="switch_set_bedtime_end_time", annotations=tool_annotations("Set Bedtime End Time", read_only=False))
async def switch_set_bedtime_end_time(params: SetBedtimeEndInput, ctx: Context) -> str:
    """Set the time when bedtime restrictions end on a Nintendo Switch device.

    This is when the device can be used again after bedtime. Must be between 05:00 and 09:00.
    Use hour=0, minute=0 to disable bedtime restrictions.

    Args:
        params (SetBedtimeEndInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - hour (int): End hour (5-9, or 0 to disable).
            - minute (int): End minute (0-59).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: ..." if the time is outside the valid range (05:00-09:00).
        - Returns "Error: Not authenticated..." if no session token is configured.
    """
    return await _set_bedtime_time(params, "set_bedtime_end_time", "Bedtime end time")


@mcp.tool(
    name="switch_clear_cache",
    annotations=tool_annotations("Clear Historic Data Cache", read_only=False, open_world=False),
)
async def switch_clear_cache(params: ClearCacheInput, ctx: Context) -> str:
    """Clear cached historic monthly play data.

    Removes locally cached API responses so the next request fetches fresh data
    from the Nintendo API. Useful when cached data looks stale or unexpected.

    Filters can be combined: clear a specific month, all months for a device,
    or all cached data at once.

    Args:
        params (ClearCacheInput): Validated input containing:
            - device_id (Optional[str]): Limit to this device. Omit for all devices.
            - year (Optional[int]): Limit to this year. Omit for all years.
            - month (Optional[int]): Limit to this month (1-12). Requires year.

    Returns:
        str: Confirmation message with count of files deleted.
    """
    try:
        return cleared_message(clear_data_cache(device_id=params.device_id, year=params.year, month=params.month))
    except Exception as e:
        return handle_error(e)
