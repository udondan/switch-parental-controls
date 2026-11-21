"""Monthly usage summary tool for the Nintendo MCP server.

Also holds the helpers to load a monthly summary (with the historic data cache)
and to find a player in it, which playtime.py uses as well.
"""

from datetime import date, datetime

from mcp.server.mcpserver import Context

from switch_parental_controls.data_cache import is_current_month, load_data_cache, save_data_cache
from switch_parental_controls.models import MonthlySummaryInput, ResponseFormat
from switch_parental_controls.server import mcp
from switch_parental_controls.tools import get_device, get_timezone, tool_annotations
from switch_parental_controls.utils import MONTH_LABEL_FORMAT, ToolError, format_minutes, handle_error, to_json


async def known_player_nickname(device, player_id: str) -> str | None:
    """Return the nickname of a player linked to the device, or None if unknown.

    Used to tell apart an unknown player ID from a known player who simply has
    no playtime in the requested period (e.g. on the first day of a month).
    """
    if not len(device.players):
        await device.update()
    player = device.players.get(player_id)
    if player is None:
        return None
    return player.nickname or player_id


def empty_player_entry(player_id: str, nickname: str) -> dict:
    """Build a monthly-summary player entry with no playtime."""
    return {
        "profile": {"playerId": player_id, "nickname": nickname},
        "summary": {"dailyStats": []},
    }


async def find_player_entry(device, summary: dict, player_id: str) -> dict | None:
    """Return the player's entry of a monthly summary.

    A known player without playtime in that month gets an empty entry. Returns
    None if the player is unknown.
    """
    entry = next(
        (p for p in summary.get("players", []) if p.get("profile", {}).get("playerId") == player_id),
        None,
    )
    if entry is None:
        nickname = await known_player_nickname(device, player_id)
        if nickname is not None:
            entry = empty_player_entry(player_id, nickname)
    return entry


async def load_monthly_summary(device, device_id: str, year: int | None, month: int | None, use_cache: bool):
    """Return the monthly summary (or None), from the cache if use_cache is set.

    Without year and month the API returns the most recent summary.
    """
    summary = load_data_cache(device_id, year, month) if use_cache else None
    if summary is None:
        search_date = datetime(year, month, 1) if year and month else None
        summary = await device.get_monthly_summary(search_date=search_date)
        if use_cache and summary is not None:
            save_data_cache(device_id, year, month, summary)
    return summary


def sorted_daily_stats(summary: dict) -> list[dict]:
    """Return the dailyStats of a summary (overall or of one player), sorted by date."""
    return sorted(summary.get("dailyStats", []), key=lambda d: d["date"])


def total_time(daily_stats: list[dict]) -> int:
    """Sum of the totalTime of all days."""
    return sum(d.get("totalTime", 0) for d in daily_stats)


def _month_label(summary: dict) -> str:
    """Month of the summary, derived from its first daily stat (format: "YYYY-MM-DD")."""
    daily_stats = summary.get("overall", {}).get("dailyStats", [])
    if daily_stats and daily_stats[0].get("date"):
        return date.fromisoformat(daily_stats[0]["date"]).strftime(MONTH_LABEL_FORMAT)
    return "Unknown month"


def _player_summary(device, entry: dict, player_id: str, month_label: str) -> str:
    """Markdown summary of one player."""
    nickname = entry.get("profile", {}).get("nickname", player_id)
    player_daily = sorted_daily_stats(entry.get("summary", {}))
    lines = [
        f"# Monthly Summary — {nickname} on {device.name}",
        f"**Period**: {month_label}",
        f"**Total playtime**: {format_minutes(total_time(player_daily))}",
        "",
    ]
    if player_daily:
        lines.append("## Daily Breakdown")
        lines += [f"- **{d['date']}**: {format_minutes(d.get('totalTime', 0))}" for d in player_daily]
        lines.append("")
    return "\n".join(lines)


def _device_summary(device, summary: dict, month_label: str) -> str:
    """Markdown summary of the device with the total time of each player."""
    daily_stats = summary.get("overall", {}).get("dailyStats", [])
    lines = [
        f"# Monthly Summary — {device.name}",
        f"**Period**: {month_label}",
        f"**Total playtime**: {format_minutes(total_time(daily_stats))}",
        "",
    ]
    players = summary.get("players", [])
    if players:
        lines.append("## Players")
        for player in players:
            nickname = player.get("profile", {}).get("nickname", "Unknown")
            play_time = total_time(player.get("summary", {}).get("dailyStats", []))
            lines.append(f"- **{nickname}**: {format_minutes(play_time)}")
        lines.append("")
    return "\n".join(lines)


async def _requested_player_entry(device, summary: dict, player_id: str) -> dict:
    """Return the player's entry, or raise ToolError if the player is unknown."""
    entry = await find_player_entry(device, summary, player_id)
    if entry is None:
        raise ToolError(
            f"Error: Player '{player_id}' not found in monthly summary for "
            f"device '{device.name}'. Use switch_list_players to see available player IDs."
        )
    return entry


@mcp.tool(name="switch_get_monthly_summary", annotations=tool_annotations("Get Monthly Usage Summary", read_only=True))
async def switch_get_monthly_summary(params: MonthlySummaryInput, ctx: Context) -> str:
    """Get the monthly usage summary for a Nintendo Switch device.

    Returns aggregated usage data for a specific month, including total playtime
    per player and per application. If no month is specified, returns the most
    recent available summary. When player_id is provided, returns a detailed
    summary for that specific player including a per-day breakdown.

    Args:
        params (MonthlySummaryInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - year (Optional[int]): Year (e.g. 2024). Omit for most recent.
            - month (Optional[int]): Month (1-12). Required if year is provided.
            - player_id (Optional[str]): Filter to a specific player ID.
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Monthly usage summary, or an error message.

    Error Handling:
        - Returns "Error: Not authenticated..." if no session token is configured.
        - Returns "No monthly summary available." if no data exists.
    """
    try:
        device = get_device(params.device_id)
        explicit_month = bool(params.year and params.month)
        cacheable = explicit_month and not is_current_month(params.year, params.month, get_timezone())
        use_cache = cacheable and not params.skip_cache
        summary = await load_monthly_summary(device, params.device_id, params.year, params.month, use_cache)
        if summary is None:
            raise ToolError(f"No monthly summary available for device '{device.name}'.")

        entry = await _requested_player_entry(device, summary, params.player_id) if params.player_id else None

        if params.response_format == ResponseFormat.JSON:
            content = {"player": entry} if params.player_id else {"summary": summary}
            return to_json({"device_name": device.name, **content})

        month_label = _month_label(summary)
        if entry is not None:
            return _player_summary(device, entry, params.player_id, month_label)
        return _device_summary(device, summary, month_label)

    except Exception as e:
        return handle_error(e)
