"""Player tools for the Nintendo MCP server.

Provides tools to read player information associated with Nintendo Switch devices.
"""

from mcp.server.mcpserver import Context

from switch_parental_controls.models import DeviceInput, PlayerInput, ResponseFormat
from switch_parental_controls.server import mcp
from switch_parental_controls.tools import DeviceListing, get_device, list_device_items, tool_annotations
from switch_parental_controls.utils import ToolError, format_minutes, handle_error, to_json


def _player_to_dict(player) -> dict:
    """Convert a Player object to a serializable dictionary."""
    return {
        "player_id": player.player_id,
        "nickname": player.nickname,
        "player_image": player.player_image,
        "today_playing_time_minutes": player.playing_time,
        "apps_played_today": player.apps,
    }


def _player_list_entry(player) -> list[str]:
    """Markdown lines for one player in the player list."""
    lines = [
        f"## {player.nickname}",
        f"- **Player ID**: `{player.player_id}`",
        f"- **Today's playtime**: {format_minutes(player.playing_time)}",
    ]
    if player.player_image:
        lines.append(f"- **Avatar**: {player.player_image}")
    lines.append("")
    return lines


_PLAYERS = DeviceListing(
    attribute="players",
    empty_message="No players found on device '{name}'.",
    heading="# Players on {name}",
    to_dict=_player_to_dict,
    entry_lines=_player_list_entry,
)


@mcp.tool(name="switch_list_players", annotations=tool_annotations("List Players on Device", read_only=True))
async def switch_list_players(params: DeviceInput, ctx: Context) -> str:
    """List all players (Nintendo accounts) associated with a Nintendo Switch device.

    Returns all player profiles linked to the device, including their nicknames,
    avatar URLs, and today's playing time.

    Args:
        params (DeviceInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: List of players with their status, or an error message.

        Success response (JSON):
        {
            "count": int,
            "device_name": str,
            "players": [
                {
                    "player_id": str,
                    "nickname": str,
                    "player_image": str,
                    "today_playing_time_minutes": int,
                    "apps_played_today": list
                }
            ]
        }

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "No players found..." if the device has no associated players.
    """
    return await list_device_items(_PLAYERS, params.device_id, params.response_format)


def _find_player(device, player_id: str):
    """Return the player of the device, or raise ToolError if it doesn't exist."""
    try:
        return device.get_player(player_id)
    except ValueError:
        raise ToolError(
            f"Error: Player '{player_id}' not found on device '{device.name}'. "
            "Use switch_list_players to see available player IDs."
        ) from None


def _app_name(device, app_id: str) -> str:
    """Name of the application, or its ID if the device doesn't know it."""
    app = device.applications.get_application(app_id) if app_id in device.applications else None
    return app.name if app else app_id


def _apps_played_today(device, player) -> list[str]:
    """Markdown lines with the time the player spent on each app today."""
    if not player.apps:
        return ["", "No apps played today."]
    lines = ["", "## Apps Played Today"]
    for app_entry in player.apps:
        app_id = app_entry.get("meta", {}).get("applicationId", "unknown")
        lines.append(f"- **{_app_name(device, app_id)}**: {format_minutes(app_entry.get('playingTime', 0))}")
    return lines


def _player_details(device, player) -> str:
    """Markdown details of one player."""
    lines = [
        f"# {player.nickname}",
        f"**Player ID**: `{player.player_id}`",
        f"**Today's playtime**: {format_minutes(player.playing_time)}",
    ]
    if player.player_image:
        lines.append(f"**Avatar**: {player.player_image}")
    lines += _apps_played_today(device, player)
    return "\n".join(lines)


@mcp.tool(name="switch_get_player", annotations=tool_annotations("Get Player Details", read_only=True))
async def switch_get_player(params: PlayerInput, ctx: Context) -> str:
    """Get detailed information for a specific player on a Nintendo Switch device.

    Returns the player's profile and a list of applications they played today,
    including the time spent on each application.

    Args:
        params (PlayerInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - player_id (str): The unique player ID (from switch_list_players).
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Detailed player information including apps played today, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "Error: ..." if the player_id is not found on the device.
    """
    try:
        device = get_device(params.device_id)
        await device.update()
        player = _find_player(device, params.player_id)

        if params.response_format == ResponseFormat.JSON:
            return to_json({"device_name": device.name, "player": _player_to_dict(player)})
        return _player_details(device, player)

    except Exception as e:
        return handle_error(e)
