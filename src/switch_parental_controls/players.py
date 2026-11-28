"""Player tools for the Nintendo MCP server.

Provides tools to read player information associated with Nintendo Switch devices.
"""

from mcp.server.mcpserver import Context

from switch_parental_controls.models import DeviceInput, PlayerInput, ResponseFormat
from switch_parental_controls.tools import DeviceListing, get_device, list_device_items, model_tool, tool_annotations
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


@model_tool("switch_list_players", DeviceInput, tool_annotations("List Players on Device", read_only=True))
async def switch_list_players(params: DeviceInput, ctx: Context) -> str:
    """List the players (user profiles) of one device, with their player IDs.

    Use it to find a player_id for switch_get_player, switch_get_playtime or
    switch_get_monthly_summary, or to compare today's playtime of all players.
    Each player comes with nickname, player ID, avatar URL and today's
    playtime; the JSON adds the apps played today.

    Returns "No players found on device '<name>'." if the device has none.

    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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


@model_tool("switch_get_player", PlayerInput, tool_annotations("Get Player Details", read_only=True))
async def switch_get_player(params: PlayerInput, ctx: Context) -> str:
    """Get today's playtime of one player, per app.

    Use it for "what did <player> play today and for how long". It returns the
    nickname, avatar URL, today's total and the time of each app played today.
    For other days use switch_get_playtime, for a month
    switch_get_monthly_summary, both with player_id.

    Returns "Error: Player '<id>' not found on device '<name>'. ..." for an
    unknown player_id.
    Returns "Error: Device '<id>' not found. ..." for an unknown device_id.
    Returns "Error: Not authenticated. ..." without a session token and
    "Error: Authentication failed. ..." when it expired; then log in again
    with switch_get_login_url.
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
