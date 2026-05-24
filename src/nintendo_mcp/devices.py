"""Device tools for the Nintendo MCP server.

Provides tools to read device status and control parental control settings
on Nintendo Switch devices.
"""

from datetime import datetime, time

from mcp.server.fastmcp import Context
from pynintendoparental.enum import DeviceTimerMode, FunctionalRestrictionLevel, RestrictionMode

from nintendo_mcp.models import (
    AddExtraTimeInput,
    DeviceInput,
    ListDevicesInput,
    MonthlySummaryInput,
    ResponseFormat,
    SetBedtimeAlarmInput,
    SetBedtimeEndInput,
    SetContentRestrictionInput,
    SetDayRestrictionsInput,
    SetPlaytimeLimitInput,
    SetRestrictionModeInput,
    SetTimerModeInput,
)
from nintendo_mcp.server import _state, mcp
from nintendo_mcp.utils import (
    format_minutes,
    format_time,
    format_timestamp,
    handle_error,
    require_client,
    to_json,
)


def _device_to_dict(device) -> dict:
    """Convert a Device object to a serializable dictionary."""
    return {
        "device_id": device.device_id,
        "name": device.name,
        "model": device.model,
        "timer_mode": str(device.timer_mode) if device.timer_mode else None,
        "limit_time_minutes": device.limit_time,
        "today_playing_time_minutes": device.today_playing_time,
        "today_time_remaining_minutes": device.today_time_remaining,
        "bedtime_alarm": format_time(device.bedtime_alarm),
        "bedtime_end": format_time(device.bedtime_end),
        "forced_termination_mode": device.forced_termination_mode,
        "alarms_enabled": device.alarms_enabled,
        "last_sync": format_timestamp(device.last_sync),
    }


@mcp.tool(
    name="nintendo_list_devices",
    annotations={
        "title": "List Nintendo Switch Devices",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_list_devices(params: ListDevicesInput, ctx: Context) -> str:
    """List all Nintendo Switch devices linked to the authenticated account.

    Returns a list of all Nintendo Switch consoles associated with the account,
    including their IDs, names, models, and current playtime status.

    Args:
        params (ListDevicesInput): Validated input containing:
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: List of devices with their status, or an error message.

        Success response (JSON):
        {
            "count": int,
            "devices": [
                {
                    "device_id": str,
                    "name": str,
                    "model": str,
                    "timer_mode": str | null,
                    "limit_time_minutes": int,
                    "today_playing_time_minutes": int,
                    "today_time_remaining_minutes": int,
                    "bedtime_alarm": str,
                    "bedtime_end": str,
                    "forced_termination_mode": bool,
                    "alarms_enabled": bool,
                    "last_sync": str
                }
            ]
        }

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: No Nintendo Switch devices found..." if account has no devices.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        await client.update()
        devices = list(client.devices.values())

        if not devices:
            return "No Nintendo Switch devices found on this account."

        if params.response_format == ResponseFormat.JSON:
            return to_json(
                {
                    "count": len(devices),
                    "devices": [_device_to_dict(d) for d in devices],
                }
            )

        lines = ["# Nintendo Switch Devices", ""]
        for device in devices:
            lines.append(f"## {device.name} ({device.model})")
            lines.append(f"- **Device ID**: `{device.device_id}`")
            lines.append(f"- **Today's playtime**: {format_minutes(device.today_playing_time)}")
            lines.append(f"- **Daily limit**: {format_minutes(device.limit_time)}")
            lines.append(f"- **Time remaining**: {format_minutes(device.today_time_remaining)}")
            lines.append(f"- **Last sync**: {format_timestamp(device.last_sync)}")
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_get_device",
    annotations={
        "title": "Get Nintendo Switch Device Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_get_device(params: DeviceInput, ctx: Context) -> str:
    """Get detailed status and settings for a specific Nintendo Switch device.

    Returns comprehensive information about a device including playtime limits,
    bedtime settings, restriction mode, and current usage.

    Args:
        params (DeviceInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Detailed device information, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: Resource not found..." if device_id is invalid.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        await device.update()

        if params.response_format == ResponseFormat.JSON:
            return to_json(_device_to_dict(device))

        restriction_mode = "Forced termination" if device.forced_termination_mode else "Alarm only"
        lines = [
            f"# {device.name} ({device.model})",
            "",
            f"**Device ID**: `{device.device_id}`",
            f"**Last sync**: {format_timestamp(device.last_sync)}",
            "",
            "## Playtime",
            f"- **Timer mode**: {device.timer_mode}",
            f"- **Daily limit**: {format_minutes(device.limit_time)}",
            f"- **Today's playtime**: {format_minutes(device.today_playing_time)}",
            f"- **Time remaining**: {format_minutes(device.today_time_remaining)}",
            "",
            "## Restrictions",
            f"- **Restriction mode**: {restriction_mode}",
            f"- **Alarms enabled**: {'Yes' if device.alarms_enabled else 'No'}",
            f"- **Bedtime alarm**: {format_time(device.bedtime_alarm)}",
            f"- **Bedtime ends**: {format_time(device.bedtime_end)}",
            "",
            f"**Players**: {len(device.players)}",
            f"**Applications tracked**: {len(device.applications)}",
        ]
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_get_today_summary",
    annotations={
        "title": "Get Today's Usage Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_get_today_summary(params: DeviceInput, ctx: Context) -> str:
    """Get today's usage summary for a Nintendo Switch device.

    Returns the daily summary including total playtime, disabled time,
    and exceeded time for the current day.

    Args:
        params (DeviceInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Today's usage summary, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "No summary available for today." if no data exists yet.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        await device.update()
        from zoneinfo import ZoneInfo

        tz = ZoneInfo(_state.get("timezone") or "Europe/London")
        today_str = datetime.now(tz).strftime("%Y-%m-%d")
        summary_list = [s for s in (device.daily_summaries or []) if s.get("date") == today_str]

        if not summary_list:
            return f"No usage summary available for today ({today_str}) on device '{device.name}'."

        summary = summary_list[0]

        if params.response_format == ResponseFormat.JSON:
            return to_json({"date": today_str, "device_name": device.name, "summary": summary})

        lines = [
            f"# Today's Summary — {device.name}",
            f"**Date**: {today_str}",
            "",
            f"- **Playing time**: {format_minutes(summary.get('playingTime', 0))}",
            f"- **Disabled time**: {format_minutes(summary.get('disabledTime', 0))}",
            f"- **Exceeded time**: {format_minutes(summary.get('exceededTime', 0))}",
        ]
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_get_monthly_summary",
    annotations={
        "title": "Get Monthly Usage Summary",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_get_monthly_summary(params: MonthlySummaryInput, ctx: Context) -> str:
    """Get the monthly usage summary for a Nintendo Switch device.

    Returns aggregated usage data for a specific month, including total playtime
    per player and per application. If no month is specified, returns the most
    recent available summary.

    Args:
        params (MonthlySummaryInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - year (Optional[int]): Year (e.g. 2024). Omit for most recent.
            - month (Optional[int]): Month (1-12). Required if year is provided.
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Monthly usage summary, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "No monthly summary available." if no data exists.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        search_date = None
        if params.year and params.month:
            search_date = datetime(params.year, params.month, 1)

        summary = await device.get_monthly_summary(search_date=search_date)

        if summary is None:
            return f"No monthly summary available for device '{device.name}'."

        if params.response_format == ResponseFormat.JSON:
            return to_json({"device_name": device.name, "summary": summary})

        month_label = summary.get("month", "Unknown month")
        total_time = summary.get("playingTime", 0)

        lines = [
            f"# Monthly Summary — {device.name}",
            f"**Period**: {month_label}",
            f"**Total playtime**: {format_minutes(total_time)}",
            "",
        ]

        players = summary.get("players", [])
        if players:
            lines.append("## Players")
            for player in players:
                profile = player.get("profile", {})
                player_summary = player.get("summary", {})
                nickname = profile.get("nickname", "Unknown")
                play_time = player_summary.get("playingTime", 0)
                lines.append(f"- **{nickname}**: {format_minutes(play_time)}")
            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_daily_playtime_limit",
    annotations={
        "title": "Set Daily Playtime Limit",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_daily_playtime_limit(params: SetPlaytimeLimitInput, ctx: Context) -> str:
    """Set the daily playtime limit for a Nintendo Switch device.

    Sets the maximum number of minutes the device can be used per day.
    Use -1 to remove the limit entirely.

    Args:
        params (SetPlaytimeLimitInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - minutes (int): Daily limit in minutes (0-360), or -1 to remove the limit.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the value is out of range or the API call fails.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        await device.update_max_daily_playtime(params.minutes)

        if params.minutes == -1:
            return f"✓ Daily playtime limit removed for '{device.name}'."
        return (
            f"✓ Daily playtime limit set to {format_minutes(params.minutes)} for '{device.name}'."
        )

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_add_extra_time",
    annotations={
        "title": "Add Extra Playtime",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def nintendo_add_extra_time(params: AddExtraTimeInput, ctx: Context) -> str:
    """Add extra playtime for the current day on a Nintendo Switch device.

    Grants additional playing time beyond the configured daily limit for today only.
    The extra time does not carry over to other days.

    Args:
        params (AddExtraTimeInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - minutes (int): Number of extra minutes to add (1-360).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the API call fails.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        await device.add_extra_time(params.minutes)
        return (
            f"✓ Added {format_minutes(params.minutes)} of extra playtime for '{device.name}' today."
        )

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_timer_mode",
    annotations={
        "title": "Set Timer Mode",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_timer_mode(params: SetTimerModeInput, ctx: Context) -> str:
    """Set the timer mode for a Nintendo Switch device.

    Controls whether a single daily limit applies to all days, or whether
    different limits can be set for each day of the week.

    Args:
        params (SetTimerModeInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - mode (str): 'DAILY' for a single limit, or 'EACH_DAY_OF_THE_WEEK' for per-day limits.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the mode is invalid or the API call fails.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        mode = DeviceTimerMode(params.mode)
        await device.set_timer_mode(mode)
        return f"✓ Timer mode set to '{params.mode}' for '{device.name}'."

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_day_restrictions",
    annotations={
        "title": "Set Per-Day Restrictions",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_day_restrictions(params: SetDayRestrictionsInput, ctx: Context) -> str:
    """Set playtime and bedtime restrictions for a specific day of the week.

    For per-day restrictions to take effect, the device's timer mode should be
    EACH_DAY_OF_THE_WEEK. Use nintendo_set_timer_mode first if needed.

    Args:
        params (SetDayRestrictionsInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
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
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        bedtime_start = None
        bedtime_end = None
        if params.bedtime_enabled:
            if params.bedtime_end_hour is None or params.bedtime_alarm_hour is None:
                return "Error: bedtime_alarm_hour and bedtime_end_hour are required when bedtime_enabled is true."
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

        parts = [f"✓ Restrictions updated for {params.day_of_week.value} on '{device.name}'."]
        if params.playtime_enabled and params.max_playtime_minutes is not None:
            parts.append(f"  Playtime limit: {format_minutes(params.max_playtime_minutes)}")
        else:
            parts.append("  Playtime limit: disabled")
        if params.bedtime_enabled:
            parts.append(
                f"  Bedtime: {params.bedtime_alarm_hour:02d}:{params.bedtime_alarm_minute or 0:02d} → "
                f"{params.bedtime_end_hour:02d}:{params.bedtime_end_minute or 0:02d}"
            )
        else:
            parts.append("  Bedtime: disabled")
        return "\n".join(parts)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_restriction_mode",
    annotations={
        "title": "Set Restriction Mode",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_restriction_mode(params: SetRestrictionModeInput, ctx: Context) -> str:
    """Set the restriction mode for a Nintendo Switch device.

    Controls what happens when the daily playtime limit is reached:
    either the software is suspended (FORCED_TERMINATION) or only an alarm
    is shown (ALARM).

    Args:
        params (SetRestrictionModeInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - mode (str): 'FORCED_TERMINATION' or 'ALARM'.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the API call fails.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        mode = RestrictionMode[params.mode]
        await device.set_restriction_mode(mode)

        description = (
            "software will be suspended when the limit is reached"
            if params.mode == "FORCED_TERMINATION"
            else "an alarm will be shown but software will not be suspended"
        )
        return f"✓ Restriction mode set to '{params.mode}' for '{device.name}' ({description})."

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_content_restriction_level",
    annotations={
        "title": "Set Content Restriction Level",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_content_restriction_level(
    params: SetContentRestrictionInput, ctx: Context
) -> str:
    """Set the content restriction level for a Nintendo Switch device.

    Controls which games and applications can be launched based on their age rating.

    Args:
        params (SetContentRestrictionInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - level (str): One of: 'NONE', 'CHILDREN', 'YOUNG_TEENS', 'OLDER_TEENS', 'CUSTOM'.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the level is invalid or the API call fails.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        level = FunctionalRestrictionLevel(params.level)
        await device.set_functional_restriction_level(level)
        return f"✓ Content restriction level set to '{params.level}' for '{device.name}'."

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_bedtime_alarm",
    annotations={
        "title": "Set Bedtime Alarm",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_bedtime_alarm(params: SetBedtimeAlarmInput, ctx: Context) -> str:
    """Set the bedtime alarm time for a Nintendo Switch device.

    The bedtime alarm notifies that bedtime has arrived. Must be between 16:00 and 23:00.
    Use hour=0, minute=0 to disable the alarm.

    Args:
        params (SetBedtimeAlarmInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - hour (int): Alarm hour (16-23, or 0 to disable).
            - minute (int): Alarm minute (0-59).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: ..." if the time is outside the valid range (16:00-23:00).
        - Returns "Error: Not authenticated..." if no session token is configured.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        alarm_time = time(params.hour, params.minute)
        await device.set_bedtime_alarm(alarm_time)

        if params.hour == 0 and params.minute == 0:
            return f"✓ Bedtime alarm disabled for '{device.name}'."
        return f"✓ Bedtime alarm set to {params.hour:02d}:{params.minute:02d} for '{device.name}'."

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_set_bedtime_end_time",
    annotations={
        "title": "Set Bedtime End Time",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def nintendo_set_bedtime_end_time(params: SetBedtimeEndInput, ctx: Context) -> str:
    """Set the time when bedtime restrictions end on a Nintendo Switch device.

    This is when the device can be used again after bedtime. Must be between 05:00 and 09:00.
    Use hour=0, minute=0 to disable bedtime restrictions.

    Args:
        params (SetBedtimeEndInput): Validated input containing:
            - device_id (str): The unique device ID (from nintendo_list_devices).
            - hour (int): End hour (5-9, or 0 to disable).
            - minute (int): End minute (0-59).

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: ..." if the time is outside the valid range (05:00-09:00).
        - Returns "Error: Not authenticated..." if no session token is configured.
    """
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return (
                f"Error: Device '{params.device_id}' not found. "
                "Use nintendo_list_devices to see available device IDs."
            )

        end_time = time(params.hour, params.minute)
        await device.set_bedtime_end_time(end_time)

        if params.hour == 0 and params.minute == 0:
            return f"✓ Bedtime end time disabled for '{device.name}'."
        return (
            f"✓ Bedtime end time set to {params.hour:02d}:{params.minute:02d} for '{device.name}'."
        )

    except Exception as e:
        return handle_error(e)
