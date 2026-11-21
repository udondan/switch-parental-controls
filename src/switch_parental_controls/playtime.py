"""Per-day playtime tool for the Nintendo MCP server.

The current month comes from the live daily summaries of the device, past
months from the monthly summary (with the historic data cache).
"""

import calendar
from dataclasses import dataclass
from datetime import date, datetime

from mcp.server.mcpserver import Context

from switch_parental_controls.data_cache import is_current_month
from switch_parental_controls.models import PlaytimeInput, ResponseFormat
from switch_parental_controls.server import mcp
from switch_parental_controls.summary import (
    find_player_entry,
    known_player_nickname,
    load_monthly_summary,
    sorted_daily_stats,
)
from switch_parental_controls.tools import get_device, get_timezone, tool_annotations
from switch_parental_controls.utils import MONTH_LABEL_FORMAT, ToolError, format_minutes, handle_error, to_json


@dataclass
class _Period:
    """The requested month, and optionally a single day of it."""

    year: int
    month: int
    current: bool
    target_date: str | None

    @property
    def prefix(self) -> str:
        """The month as "YYYY-MM"."""
        return f"{self.year}-{self.month:02d}"


@dataclass
class _Days:
    """Per-day data of a device or of one player.

    The live daily summaries hold the time in "playingTime", the monthly
    summary in "totalTime".
    """

    days: list[dict]
    time_key: str
    nickname: str | None = None


def _resolve_period(params: PlaytimeInput, now: datetime) -> _Period:
    """Fill in the current month if none is given and validate the day."""
    year = params.year or now.year
    month = params.month or now.month
    target_date = None
    if params.day is not None:
        max_days = calendar.monthrange(year, month)[1]
        if params.day > max_days:
            raise ToolError(f"Error: day {params.day} is out of range for {year}-{month:02d} (max: {max_days}).")
        target_date = f"{year}-{month:02d}-{params.day:02d}"
    current = year == now.year and month == now.month
    return _Period(year, month, current, target_date)


async def _current_player_days(device, entries: list[dict], params: PlaytimeInput, period: _Period) -> _Days:
    """Playtime of one player per day of the current month."""
    nickname = None
    days = []
    for entry in entries:
        player = next(
            (p for p in entry.get("players", []) if p.get("profile", {}).get("playerId") == params.player_id),
            None,
        )
        if player is None:
            continue
        if nickname is None:
            nickname = player.get("profile", {}).get("nickname", params.player_id)
        days.append({"date": entry["date"], "playingTime": player.get("playingTime", 0)})

    if not days:
        nickname = await known_player_nickname(device, params.player_id)
        if nickname is None:
            raise ToolError(
                f"Error: Player '{params.player_id}' not found in daily data for {period.prefix} "
                f"on device '{device.name}'. Use switch_list_players to see available player IDs."
            )
        if params.response_format != ResponseFormat.JSON and period.target_date is None:
            raise ToolError(
                f"No playtime recorded for player '{nickname}' in {period.prefix} on device '{device.name}'."
            )
    return _Days(days, "playingTime", nickname)


async def _current_days(device, params: PlaytimeInput, period: _Period) -> _Days:
    """Per-day data of the current month from the live daily summaries."""
    await device.update()
    entries = sorted(
        [s for s in (device.daily_summaries or []) if s.get("date", "").startswith(period.prefix)],
        key=lambda s: s["date"],
    )
    if not entries:
        raise ToolError(f"No daily data available for {period.prefix} on device '{device.name}'.")
    if params.player_id:
        return await _current_player_days(device, entries, params, period)
    return _Days(entries, "playingTime")


async def _past_player_days(device, summary: dict, params: PlaytimeInput, period: _Period) -> _Days:
    """Playtime of one player per day of a past month."""
    entry = await find_player_entry(device, summary, params.player_id)
    if entry is None:
        raise ToolError(
            f"Error: Player '{params.player_id}' not found in monthly summary for "
            f"{period.prefix} on device '{device.name}'. "
            "Use switch_list_players to see available player IDs."
        )
    nickname = entry.get("profile", {}).get("nickname", params.player_id)
    days = sorted_daily_stats(entry.get("summary", {}))
    if not days:
        raise ToolError(f"No daily data for player '{nickname}' in {period.prefix} on device '{device.name}'.")
    return _Days(days, "totalTime", nickname)


async def _past_days(device, params: PlaytimeInput, period: _Period) -> _Days:
    """Per-day data of a past month from the monthly summary."""
    cacheable = params.year is not None and not is_current_month(period.year, period.month, get_timezone())
    use_cache = cacheable and not params.skip_cache
    summary = await load_monthly_summary(device, params.device_id, period.year, period.month, use_cache)
    if summary is None:
        raise ToolError(f"No monthly summary available for {period.prefix} on device '{device.name}'.")
    if params.player_id:
        return await _past_player_days(device, summary, params, period)

    days = sorted_daily_stats(summary.get("overall", {}))
    if not days:
        raise ToolError(f"No daily data in monthly summary for {period.prefix} on device '{device.name}'.")
    return _Days(days, "totalTime")


def _filter_day(data: _Days, device, target_date: str) -> None:
    """Keep only the requested day, or raise ToolError if there is no data for it."""
    data.days = [d for d in data.days if d.get("date") == target_date]
    if data.days:
        return
    if data.nickname is not None:
        raise ToolError(f"No data available for {target_date} for player '{data.nickname}' on device '{device.name}'.")
    raise ToolError(f"No data available for {target_date} on device '{device.name}'.")


def _to_json(data: _Days, device, params: PlaytimeInput, period: _Period) -> str:
    """The playtime as JSON."""
    result: dict = {"device_name": device.name}
    if params.player_id:
        result |= {"player_id": params.player_id, "player_nickname": data.nickname}
    result |= {"year": period.year, "month": period.month, "current": period.current, "days": data.days}
    return to_json(result)


def _title(heading: str, data: _Days, device) -> str:
    """Markdown title for the device or for one player on the device."""
    if data.nickname is not None:
        return f"# {heading} — {data.nickname} on {device.name}"
    return f"# {heading} — {device.name}"


def _render_day(data: _Days, device, period: _Period, show_extras: bool) -> str:
    """Markdown summary of a single day."""
    day = data.days[0]
    lines = [
        _title("Day Summary", data, device),
        f"**Date**: {period.target_date}",
        "",
        f"- **Playing time**: {format_minutes(day.get(data.time_key, 0))}",
    ]
    if show_extras and day.get("disabledTime", 0) > 0:
        lines.append(f"- **Disabled time**: {format_minutes(day['disabledTime'])}")
    if show_extras and day.get("exceededTime", 0) > 0:
        lines.append(f"- **Exceeded time**: {format_minutes(day['exceededTime'])}")
    return "\n".join(lines)


def _day_extras(day: dict) -> str:
    """Disabled and exceeded time of a day, e.g. " (disabled: 10m, exceeded: 5m)"."""
    extras = []
    if day.get("disabledTime", 0) > 0:
        extras.append(f"disabled: {format_minutes(day['disabledTime'])}")
    if day.get("exceededTime", 0) > 0:
        extras.append(f"exceeded: {format_minutes(day['exceededTime'])}")
    return f" ({', '.join(extras)})" if extras else ""


def _render_month(data: _Days, device, period: _Period, show_extras: bool) -> str:
    """Markdown breakdown of all days of the month."""
    month_label = date(period.year, period.month, 1).strftime(MONTH_LABEL_FORMAT)
    suffix = " (current)" if period.current else ""
    lines = [_title("Daily Breakdown", data, device), f"**Period**: {month_label}{suffix}", ""]
    for day in data.days:
        extras = _day_extras(day) if show_extras else ""
        lines.append(f"- **{day['date']}**: {format_minutes(day.get(data.time_key, 0))}{extras}")
    total = sum(d.get(data.time_key, 0) for d in data.days)
    lines += ["", f"**Total**: {format_minutes(total)}"]
    return "\n".join(lines)


@mcp.tool(name="switch_get_playtime", annotations=tool_annotations("Get Playtime", read_only=True))
async def switch_get_playtime(params: PlaytimeInput, ctx: Context) -> str:
    """Get per-day playtime breakdown for a month, or a single day when day is specified.

    For the current month, returns data from the live daily summaries feed,
    including playing time, disabled time, and exceeded time per day.
    For past months, returns total playing time per day from the monthly summary.
    When player_id is provided, filters results to that specific player.
    When day is provided, returns data for that single day only.

    Args:
        params (PlaytimeInput): Validated input containing:
            - device_id (str): The unique device ID (from switch_list_devices).
            - year (Optional[int]): Year (e.g. 2024). Omit for current month.
            - month (Optional[int]): Month (1-12). Required if year is provided.
            - day (Optional[int]): Day (1-31). Requires year and month to be set.
            - player_id (Optional[str]): Filter to a specific player ID.
            - response_format (str): 'markdown' or 'json' (default: 'markdown').

    Returns:
        str: Per-day playtime breakdown, or an error message.
    """
    try:
        device = get_device(params.device_id)
        period = _resolve_period(params, datetime.now(get_timezone()))
        load_days = _current_days if period.current else _past_days
        data = await load_days(device, params, period)

        if period.target_date is not None:
            _filter_day(data, device, period.target_date)

        if params.response_format == ResponseFormat.JSON:
            return _to_json(data, device, params, period)

        # Disabled and exceeded time only exist in the live data of the whole device.
        show_extras = period.current and not params.player_id
        render = _render_month if period.target_date is None else _render_day
        return render(data, device, period, show_extras)

    except Exception as e:
        return handle_error(e)
