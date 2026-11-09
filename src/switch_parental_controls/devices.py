"""Device tools for the Nintendo MCP server.

Provides tools to read the status of Nintendo Switch devices. Usage history
lives in playtime.py and summary.py, settings in device_settings.py.
"""

from datetime import datetime

from mcp.server.mcpserver import Context

from switch_parental_controls.models import DeviceInput, ListDevicesInput, ResponseFormat
from switch_parental_controls.server import mcp
from switch_parental_controls.tools import get_client, get_device, get_timezone, tool_annotations
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


@mcp.tool(name="switch_list_devices", annotations=tool_annotations("List Nintendo Switch Devices", read_only=True))
async def switch_list_devices(params: ListDevicesInput, ctx: Context) -> str:
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


@mcp.tool(name="switch_get_device", annotations=tool_annotations("Get Nintendo Switch Device Details", read_only=True))
async def switch_get_device(params: DeviceInput, ctx: Context) -> str:
    """Get detailed status and settings for a specific Nintendo Switch device.

    Returns comprehensive information about a device including playtime limits,
    bedtime settings, restriction mode, and current usage.

    Args:
        params (DeviceInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Detailed device information, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: Resource not found..." if device_id is invalid.
    """
    try:
        device = get_device(params.device_id)
        await device.update()

        if params.response_format == ResponseFormat.JSON:
            return to_json(_device_to_dict(device))
        return _device_details(device)

    except Exception as e:
        return handle_error(e)


@mcp.tool(name="switch_get_today_summary", annotations=tool_annotations("Get Today's Usage Summary", read_only=True))
async def switch_get_today_summary(params: DeviceInput, ctx: Context) -> str:
    """Get today's usage summary for a Nintendo Switch device.

    Returns the daily summary including total playtime, disabled time,
    and exceeded time for the current day.

    Args:
        params (DeviceInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Today's usage summary, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "No summary available for today." if no data exists yet.
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
