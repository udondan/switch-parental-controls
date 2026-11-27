"""Device tools for the Nintendo MCP server.

Provides tools to read the status of Nintendo Switch devices. Usage history
lives in playtime.py and summary.py, settings in device_settings.py.
"""

from datetime import datetime

from mcp.server.mcpserver import Context

from switch_parental_controls.models import DeviceInput, ListDevicesInput, ResponseFormat
from switch_parental_controls.tools import get_client, get_device, get_timezone, model_tool, tool_annotations
from switch_parental_controls.utils import (
    ToolError,
    format_minutes,
    format_time,
    format_timestamp,
    handle_error,
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


def _device_list_entry(device) -> list[str]:
    """Markdown lines for one device in the device list."""
    return [
        f"## {device.name} ({device.model})",
        f"- **Device ID**: `{device.device_id}`",
        f"- **Today's playtime**: {format_minutes(device.today_playing_time)}",
        f"- **Daily limit**: {format_minutes(device.limit_time)}",
        f"- **Time remaining**: {format_minutes(device.today_time_remaining)}",
        f"- **Last sync**: {format_timestamp(device.last_sync)}",
        "",
    ]


@model_tool("switch_list_devices", ListDevicesInput, tool_annotations("List Nintendo Switch Devices", read_only=True))
async def switch_list_devices(params: ListDevicesInput, ctx: Context) -> str:
    """List the Nintendo Switch consoles of the account, with their device IDs.

    Start here: every other tool needs a device_id from this list. Each device
    comes with its name, model, today's playtime, daily limit, remaining time
    and last sync; the JSON adds the timer mode, bedtime and restriction mode.
    Use switch_get_device for the settings of one device.

    Returns "No Nintendo Switch devices found on this account." if there are none.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    try:
        client = get_client()
        await client.update()
        devices = list(client.devices.values())

        if not devices:
            return "No Nintendo Switch devices found on this account."

        if params.response_format == ResponseFormat.JSON:
            return to_json({"count": len(devices), "devices": [_device_to_dict(d) for d in devices]})

        lines = ["# Nintendo Switch Devices", ""]
        for device in devices:
            lines += _device_list_entry(device)
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


def _device_details(device) -> str:
    """Markdown details of one device."""
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


@model_tool("switch_get_device", DeviceInput, tool_annotations("Get Nintendo Switch Device Details", read_only=True))
async def switch_get_device(params: DeviceInput, ctx: Context) -> str:
    """Get the current parental control settings and today's usage of one device.

    Use it to see how a device is set up: timer mode, daily limit, today's
    playtime and remaining time, restriction mode (forced termination or alarm
    only), bedtime alarm and end, and the number of players and tracked apps.
    For the settings of each day of the week there is no read tool; for
    playtime history use switch_get_playtime or switch_get_monthly_summary.


    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    try:
        device = get_device(params.device_id)
        await device.update()

        if params.response_format == ResponseFormat.JSON:
            return to_json(_device_to_dict(device))
        return _device_details(device)

    except Exception as e:
        return handle_error(e)


@model_tool("switch_get_today_summary", DeviceInput, tool_annotations("Get Today's Usage Summary", read_only=True))
async def switch_get_today_summary(params: DeviceInput, ctx: Context) -> str:
    """Get today's totals of one device: playing, disabled and exceeded time.

    Use it for "how long was the console used today". Disabled time is time
    the device was blocked, exceeded time is play beyond the limit. For one
    player use switch_get_player, for other days switch_get_playtime.

    Returns "No usage summary available for today (<date>) on device '<name>'."
    before the first sync of the day.
    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
    """
    try:
        device = get_device(params.device_id)
        await device.update()

        today_str = datetime.now(get_timezone()).strftime("%Y-%m-%d")
        summary = next((s for s in (device.daily_summaries or []) if s.get("date") == today_str), None)
        if summary is None:
            raise ToolError(f"No usage summary available for today ({today_str}) on device '{device.name}'.")

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
