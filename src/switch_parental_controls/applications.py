"""Application tools for the Nintendo MCP server.

Provides tools to read application information and manage the allow-list
(safe launch settings) for games on Nintendo Switch devices.
"""

from mcp.server.mcpserver import Context
from pynintendoparental.enum import SafeLaunchSetting

from switch_parental_controls.models import DeviceInput, SetAppAllowListInput
from switch_parental_controls.tools import DeviceListing, get_device, list_device_items, model_tool, tool_annotations
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


@model_tool("switch_list_applications", DeviceInput, tool_annotations("List Applications on Device", read_only=True))
async def switch_list_applications(params: DeviceInput, ctx: Context) -> str:
    """List the games and apps played on one device, with their allow-list status.

    Use it to find an application_id for switch_set_app_allow_list, or to see
    today's playtime per app across all players. Each app comes with name,
    application ID, image URL, today's playtime and whether it is allow-listed
    (ALLOW: starts regardless of the content restriction level, NONE: normal
    restrictions). For the apps of one player use switch_get_player.

    Returns "No applications tracked on device '<name>'." if none were played.

    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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


@model_tool(
    "switch_set_app_allow_list",
    SetAppAllowListInput,
    tool_annotations("Set Application Allow-List Status", read_only=False),
)
async def switch_set_app_allow_list(params: SetAppAllowListInput, ctx: Context) -> str:
    """Allow one app regardless of the content restriction level, or remove that exception.

    Use it when a specific game is blocked by the age rating filter but should
    be allowed (allow=true), or to undo that (allow=false). To change the
    filter for all apps use switch_set_content_restriction_level instead.
    Returns a confirmation with the app name.

    Returns "Error: Application '<id>' not found on device '<name>'. ..." for an
    unknown application_id.
    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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
