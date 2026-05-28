"""Player tools for the Nintendo MCP server.

Provides tools to read player information associated with Nintendo Switch devices.
"""

from mcp.server.fastmcp import Context

from switch_parental_controls.models import DeviceInput, PlayerInput, ResponseFormat
from switch_parental_controls.server import _state, mcp
from switch_parental_controls.utils import format_minutes, handle_error, require_client, to_json


def _player_to_dict(player) -> dict:
    """Convert a Player object to a serializable dictionary."""
    return {
        "player_id": player.player_id,
        "nickname": player.nickname,
        "player_image": player.player_image,
        "today_playing_time_minutes": player.playing_time,
        "apps_played_today": player.apps,
    }


@mcp.tool(
    name="switch_list_players",
    annotations={
        "title": "List Players on Device",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
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
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return f"Error: Device '{params.device_id}' not found. Use switch_list_devices to see available device IDs."

        await device.update()
        players = list(device.players.values())

        if not players:
            return f"No players found on device '{device.name}'."

        if params.response_format == ResponseFormat.JSON:
            return to_json(
                {
                    "count": len(players),
                    "device_name": device.name,
                    "players": [_player_to_dict(p) for p in players],
                }
            )

        lines = [f"# Players on {device.name}", ""]
        for player in players:
            lines.append(f"## {player.nickname}")
            lines.append(f"- **Player ID**: `{player.player_id}`")
            lines.append(f"- **Today's playtime**: {format_minutes(player.playing_time)}")
            if player.player_image:
                lines.append(f"- **Avatar**: {player.player_image}")
            lines.append("")
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="switch_get_player",
    annotations={
        "title": "Get Player Details",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
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
    err = require_client(_state.get("client"))
    if err:
        return err

    try:
        client = _state["client"]
        device = client.devices.get(params.device_id)
        if device is None:
            return f"Error: Device '{params.device_id}' not found. Use switch_list_devices to see available device IDs."

        await device.update()
        try:
            player = device.get_player(params.player_id)
        except ValueError:
            return (
                f"Error: Player '{params.player_id}' not found on device '{device.name}'. "
                "Use switch_list_players to see available player IDs."
            )

        if params.response_format == ResponseFormat.JSON:
            return to_json(
                {
                    "device_name": device.name,
                    "player": _player_to_dict(player),
                }
            )

        lines = [
            f"# {player.nickname}",
            f"**Player ID**: `{player.player_id}`",
            f"**Today's playtime**: {format_minutes(player.playing_time)}",
        ]
        if player.player_image:
            lines.append(f"**Avatar**: {player.player_image}")

        apps = player.apps
        if apps:
            lines.append("")
            lines.append("## Apps Played Today")
            for app_entry in apps:
                app_id = app_entry.get("meta", {}).get("applicationId", "unknown")
                play_time = app_entry.get("playingTime", 0)
                app_obj = device.applications.get(app_id)
                app_name = app_obj.name if app_obj else app_id
                lines.append(f"- **{app_name}**: {format_minutes(play_time)}")
        else:
            lines.append("")
            lines.append("No apps played today.")

        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)
