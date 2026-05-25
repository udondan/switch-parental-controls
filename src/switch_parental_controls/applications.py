"""Application tools for the Nintendo MCP server.

Provides tools to read application information and manage the allow-list
(safe launch settings) for games on Nintendo Switch devices.
"""

from mcp.server.fastmcp import Context
from pynintendoparental.enum import SafeLaunchSetting

from switch_parental_controls.models import DeviceInput, ResponseFormat, SetAppAllowListInput
from switch_parental_controls.server import _state, mcp
from switch_parental_controls.utils import format_minutes, handle_error, require_client, to_json


def _app_to_dict(app) -> dict:
    """Convert an Application object to a serializable dictionary."""
    return {
        "application_id": app.application_id,
        "name": app.name,
        "image_url": app.image_url,
        "today_time_played_minutes": app.today_time_played,
        "allow_list_status": str(app.safe_launch_setting),
    }


@mcp.tool(
    name="switch_list_applications",
    annotations={
        "title": "List Applications on Device",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def switch_list_applications(params: DeviceInput, ctx: Context) -> str:
    """List all applications (games) tracked on a Nintendo Switch device.

    Returns all games and applications that have been played on the device,
    including their names, today's playtime, and allow-list status.

    The allow-list status indicates whether an application can bypass content
    restrictions (ALLOW) or is subject to normal restrictions (NONE).

    Args:
        params (DeviceInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: List of applications with their status, or an error message.

        Success response (JSON):
        {
            "count": int,
            "device_name": str,
            "applications": [
                {
                    "application_id": str,
                    "name": str,
                    "image_url": str,
                    "today_time_played_minutes": int,
                    "allow_list_status": str   # "NONE" or "ALLOW"
                }
            ]
        }

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "No applications found..." if no apps have been tracked.
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
                "Use switch_list_devices to see available device IDs."
            )

        await device.update()
        apps = list(device.applications.values())

        if not apps:
            return f"No applications tracked on device '{device.name}'."

        if params.response_format == ResponseFormat.JSON:
            return to_json(
                {
                    "count": len(apps),
                    "device_name": device.name,
                    "applications": [_app_to_dict(a) for a in apps],
                }
            )

        lines = [f"# Applications on {device.name}", ""]
        for app in apps:
            allow_status = str(app.safe_launch_setting)
            allow_label = "✓ Allow-listed" if allow_status == "ALLOW" else "Normal restrictions"
            lines.append(f"## {app.name}")
            lines.append(f"- **App ID**: `{app.application_id}`")
            lines.append(f"- **Today's playtime**: {format_minutes(app.today_time_played)}")
            lines.append(f"- **Allow-list**: {allow_label}")
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="switch_set_app_allow_list",
    annotations={
        "title": "Set Application Allow-List Status",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def switch_set_app_allow_list(params: SetAppAllowListInput, ctx: Context) -> str:
    """Set whether an application can bypass content restrictions on a Nintendo Switch device.

    Adding an application to the allow-list lets it be launched regardless of the
    device's content restriction level (age rating filter). This is useful for
    educational apps or games that are safe but might be blocked by strict settings.

    Args:
        params (SetAppAllowListInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - application_id (str): The unique app ID (from switch_list_applications).
            - allow (bool): True to add to allow-list, False to remove from allow-list.

    Returns:
        str: Confirmation message, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the application_id is not found on the device.
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
                "Use switch_list_devices to see available device IDs."
            )

        await device.update()
        try:
            app = device.get_application(params.application_id)
        except ValueError:
            return (
                f"Error: Application '{params.application_id}' not found on device '{device.name}'. "
                "Use switch_list_applications to see available application IDs."
            )

        setting = SafeLaunchSetting.ALLOW if params.allow else SafeLaunchSetting.NONE
        await app.set_safe_launch_setting(setting)

        if params.allow:
            return (
                f"✓ '{app.name}' added to the allow-list on '{device.name}'. "
                "It can now bypass content restrictions."
            )
        return (
            f"✓ '{app.name}' removed from the allow-list on '{device.name}'. "
            "It is now subject to normal content restrictions."
        )

    except Exception as e:
        return handle_error(e)
