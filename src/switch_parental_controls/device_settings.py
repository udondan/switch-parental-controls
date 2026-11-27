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
from switch_parental_controls.tools import get_device, model_tool, tool_annotations
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


@model_tool(
    "switch_set_daily_playtime_limit",
    SetPlaytimeLimitInput,
    tool_annotations("Set Daily Playtime Limit", read_only=False),
)
async def switch_set_daily_playtime_limit(params: SetPlaytimeLimitInput, ctx: Context) -> str:
    """Set the daily playtime limit of a device, or remove it with minutes=-1.

    Use it to change the limit that applies to every day while the timer mode
    is DAILY. For different limits per weekday use switch_set_day_restrictions
    (with timer mode EACH_DAY_OF_THE_WEEK), for more time today only
    switch_add_extra_time. Returns a confirmation with the new limit.


    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    return await _apply_setting(
        params.device_id,
        lambda device: device.update_max_daily_playtime(params.minutes),
        lambda device: _playtime_limit_message(params.minutes, device),
    )


@model_tool(
    "switch_add_extra_time",
    AddExtraTimeInput,
    tool_annotations("Add Extra Playtime", read_only=False, idempotent=False),
)
async def switch_add_extra_time(params: AddExtraTimeInput, ctx: Context) -> str:
    """Give a device extra playtime for today only, on top of its limit.

    Use it for a one-off "30 more minutes today"; the limit of other days stays
    as it is. Every call adds to the extra time already given. To change the
    limit itself use switch_set_daily_playtime_limit. Returns a confirmation.


    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    return await _apply_setting(
        params.device_id,
        lambda device: device.add_extra_time(params.minutes),
        lambda device: f"✓ Added {format_minutes(params.minutes)} of extra playtime for '{device.name}' today.",
    )


@model_tool("switch_set_timer_mode", SetTimerModeInput, tool_annotations("Set Timer Mode", read_only=False))
async def switch_set_timer_mode(params: SetTimerModeInput, ctx: Context) -> str:
    """Choose between one limit for every day (DAILY) and one per weekday (EACH_DAY_OF_THE_WEEK).

    Use it before switch_set_day_restrictions, which only takes effect in
    EACH_DAY_OF_THE_WEEK mode; in DAILY mode switch_set_daily_playtime_limit
    sets the limit. switch_get_device shows the current mode. Returns a
    confirmation.


    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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


@model_tool(
    "switch_set_day_restrictions",
    SetDayRestrictionsInput,
    tool_annotations("Set Per-Day Restrictions", read_only=False),
)
async def switch_set_day_restrictions(params: SetDayRestrictionsInput, ctx: Context) -> str:
    """Set the playtime limit and bedtime of one weekday.

    Use it to give e.g. weekends other rules than school days. Each call sets
    both settings of that day: playtime_enabled with max_playtime_minutes, and
    bedtime_enabled with the alarm and end time. It only takes effect while the
    timer mode is EACH_DAY_OF_THE_WEEK (switch_set_timer_mode). For the same
    bedtime on every day use switch_set_bedtime_alarm and
    switch_set_bedtime_end_time. Returns a confirmation with the day's rules.

    Invalid combinations, like playtime_enabled=true without
    max_playtime_minutes, are rejected with the reason.
    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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


@model_tool(
    "switch_set_restriction_mode", SetRestrictionModeInput, tool_annotations("Set Restriction Mode", read_only=False)
)
async def switch_set_restriction_mode(params: SetRestrictionModeInput, ctx: Context) -> str:
    """Choose what happens when the playtime limit is reached: suspend the game or only show an alarm.

    FORCED_TERMINATION suspends the software at the limit, ALARM only shows a
    notice on the screen. This applies to the daily and the per-day limits.
    switch_get_device shows the current mode. Returns a confirmation.


    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    description = _RESTRICTION_MODE_DESCRIPTIONS.get(params.mode, _RESTRICTION_MODE_DESCRIPTIONS["ALARM"])
    return await _apply_setting(
        params.device_id,
        lambda device: device.set_restriction_mode(RestrictionMode[params.mode]),
        lambda device: f"✓ Restriction mode set to '{params.mode}' for '{device.name}' ({description}).",
    )


@model_tool(
    "switch_set_content_restriction_level",
    SetContentRestrictionInput,
    tool_annotations("Set Content Restriction Level", read_only=False),
)
async def switch_set_content_restriction_level(params: SetContentRestrictionInput, ctx: Context) -> str:
    """Set which games may start, by age rating, for all apps of a device.

    Use it to change the age rating filter: NONE, CHILDREN, YOUNG_TEENS,
    OLDER_TEENS or CUSTOM. To allow one blocked app use
    switch_set_app_allow_list instead. Returns a confirmation.


    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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


@model_tool("switch_set_bedtime_alarm", SetBedtimeAlarmInput, tool_annotations("Set Bedtime Alarm", read_only=False))
async def switch_set_bedtime_alarm(params: SetBedtimeAlarmInput, ctx: Context) -> str:
    """Set the time from which a device shows the bedtime alarm, for every day.

    Use it for the evening part of bedtime (16:00 to 23:00), or hour=0 and
    minute=0 to turn the alarm off. The morning end is set with
    switch_set_bedtime_end_time, a bedtime for single weekdays with
    switch_set_day_restrictions. Returns a confirmation.

    Times outside 16:00 to 23:00 are rejected with the reason.
    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    return await _set_bedtime_time(params, "set_bedtime_alarm", "Bedtime alarm")


@model_tool(
    "switch_set_bedtime_end_time", SetBedtimeEndInput, tool_annotations("Set Bedtime End Time", read_only=False)
)
async def switch_set_bedtime_end_time(params: SetBedtimeEndInput, ctx: Context) -> str:
    """Set the time in the morning from which a device can be used again, for every day.

    Use it for the end of bedtime (05:00 to 09:00), or hour=0 and minute=0 to
    turn it off. The evening alarm is set with switch_set_bedtime_alarm, a
    bedtime for single weekdays with switch_set_day_restrictions. Returns a
    confirmation.

    Times outside 05:00 to 09:00 are rejected with the reason.
    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    return await _set_bedtime_time(params, "set_bedtime_end_time", "Bedtime end time")


@model_tool(
    "switch_clear_cache",
    ClearCacheInput,
    tool_annotations("Clear Historic Data Cache", read_only=False, open_world=False),
)
async def switch_clear_cache(params: ClearCacheInput, ctx: Context) -> str:
    """Delete the local copies of past monthly summaries, so they are fetched again.

    Use it when switch_get_monthly_summary or switch_get_playtime show old or
    unexpected numbers for a past month; for a single call, skip_cache=true on
    those tools does the same without deleting anything. Without arguments it
    clears everything, or only one device, year or month. It does not contact
    Nintendo and changes nothing on the console.

    Returns "✓ Cleared <n> cached file(s)." or "No cached files found matching
    the given filters."
    """
    try:
        return cleared_message(clear_data_cache(device_id=params.device_id, year=params.year, month=params.month))
    except Exception as e:
        return handle_error(e)
