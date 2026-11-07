"""Application tools for the Nintendo MCP server.

Provides tools to read application information and manage the allow-list
(safe launch settings) for games on Nintendo Switch devices.
"""

from mcp.server.mcpserver import Context
from pynintendoparental.enum import SafeLaunchSetting

from switch_parental_controls.models import DeviceInput, SetAppAllowListInput
from switch_parental_controls.server import mcp
from switch_parental_controls.tools import DeviceListing, get_device, list_device_items, tool_annotations
from switch_parental_controls.utils import ToolError, format_minutes, handle_error


def _app_to_dict(app) -> dict:
    """Convert an Application object to a serializable dictionary."""
    return {
        "application_id": app.application_id,
        "name": app.name,
        "image_url": app.image_url,
        "today_time_played_minutes": app.today_time_played,
        "allow_list_status": str(app.safe_launch_setting),
    }


def _app_list_entry(app) -> list[str]:
    """Markdown lines for one application in the application list."""
    allow_label = "✓ Allow-listed" if str(app.safe_launch_setting) == "ALLOW" else "Normal restrictions"
    return [
        f"## {app.name}",
        f"- **App ID**: `{app.application_id}`",
        f"- **Today's playtime**: {format_minutes(app.today_time_played)}",
        f"- **Allow-list**: {allow_label}",
        "",
    ]


_APPLICATIONS = DeviceListing(
    attribute="applications",
    empty_message="No applications tracked on device '{name}'.",
    heading="# Applications on {name}",
    to_dict=_app_to_dict,
    entry_lines=_app_list_entry,
)


@mcp.tool(
    name="switch_list_applications",
    annotations=tool_annotations("List Applications on Device", read_only=True),
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
    return await list_device_items(_APPLICATIONS, params.device_id, params.response_format)


def _find_application(device, application_id: str):
    """Return the application of the device, or raise ToolError if it doesn't exist."""
    try:
        return device.get_application(application_id)
    except ValueError:
        raise ToolError(
            f"Error: Application '{application_id}' not found on device '{device.name}'. "
            "Use switch_list_applications to see available application IDs."
        ) from None


def _allow_list_message(app, device, allow: bool) -> str:
    if allow:
        return f"✓ '{app.name}' added to the allow-list on '{device.name}'. It can now bypass content restrictions."
    return (
        f"✓ '{app.name}' removed from the allow-list on '{device.name}'. "
        "It is now subject to normal content restrictions."
    )


@mcp.tool(
    name="switch_set_app_allow_list",
    annotations=tool_annotations("Set Application Allow-List Status", read_only=False),
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
    try:
        device = get_device(params.device_id)
        await device.update()
        app = _find_application(device, params.application_id)

        setting = SafeLaunchSetting.ALLOW if params.allow else SafeLaunchSetting.NONE
        await app.set_safe_launch_setting(setting)
        return _allow_list_message(app, device, params.allow)

    except Exception as e:
        return handle_error(e)
