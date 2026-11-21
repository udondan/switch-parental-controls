"""Nintendo Switch Parental Controls CLI.

Provides subcommands for all parental control operations plus login/logout and an
'mcp' subcommand that starts the MCP server.

Authentication:
    Run 'switch-parental-controls login' for an interactive OAuth flow, or set
    SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN in the environment before running any other command.

Environment Variables:
    SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN: Nintendo session token.
    SWITCH_PARENTAL_CONTROLS_TIMEZONE: IANA timezone string (default: Europe/London).
    SWITCH_PARENTAL_CONTROLS_LANG: Language code (default: en-GB).
"""

import asyncio
import os
import sys
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import click

from switch_parental_controls.client import switch_client
from switch_parental_controls.device_cache import devices_from_client, resolve_device_id, save_cache
from switch_parental_controls.models import (
    AddExtraTimeInput,
    DayOfWeek,
    DeviceInput,
    ListDevicesInput,
    MonthlySummaryInput,
    PlayerInput,
    PlaytimeInput,
    ResponseFormat,
    SetAppAllowListInput,
    SetBedtimeAlarmInput,
    SetBedtimeEndInput,
    SetContentRestrictionInput,
    SetDayRestrictionsInput,
    SetPlaytimeLimitInput,
    SetRestrictionModeInput,
    SetTimerModeInput,
)
from switch_parental_controls.server import DEFAULT_LANG, DEFAULT_TIMEZONE, _state


def _require_token() -> str:
    """Return session token from env var or credentials file, or exit with an error."""
    from switch_parental_controls.credentials import load_token

    token = os.environ.get("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN") or load_token()
    if not token:
        click.echo(
            "Error: Not authenticated.\nRun 'switch-parental-controls login' to authenticate.",
            err=True,
        )
        sys.exit(1)
    return token


def _populate_state(client, http_session, obj: dict) -> None:
    """Fill _state from the initialized client and CLI options."""
    _state["client"] = client
    _state["http_session"] = http_session
    _state["timezone"] = obj["timezone"]
    _state["lang"] = obj["lang"]


_MCP_TO_CLI = {
    "switch_list_devices": "list-devices",
    "switch_list_players": "list-players",
    "switch_list_applications": "list-applications",
    "switch_set_timer_mode": "set-timer-mode",
    "switch_get_login_url": "login",
    "switch_complete_login": "login",
}


def _output(result: str) -> None:
    """Print result and exit 1 if it is an error."""
    for mcp_name, cli_name in _MCP_TO_CLI.items():
        result = result.replace(mcp_name, cli_name)
    is_error = result.startswith("Error:")
    click.echo(result, err=is_error)
    if is_error:
        sys.exit(1)


def _execute(coro_factory) -> None:
    """Run an async coroutine factory and output the result."""
    try:
        result = asyncio.run(coro_factory())
    except (click.exceptions.ClickException, click.exceptions.Abort):
        raise
    except Exception as exc:
        exc_type = type(exc).__name__
        if "InvalidSessionToken" in exc_type or "invalid_grant" in str(exc):
            click.echo(
                "Error: Saved token is invalid or expired.\nRun 'switch-parental-controls login' to re-authenticate.",
                err=True,
            )
            sys.exit(1)
        raise click.ClickException(str(exc)) from exc
    _output(result)


@click.group()
@click.version_option(package_name="switch-parental-controls")
@click.option(
    "--timezone",
    "-t",
    envvar="SWITCH_PARENTAL_CONTROLS_TIMEZONE",
    default=DEFAULT_TIMEZONE,
    show_default=True,
    help="IANA timezone (e.g. America/New_York).",
)
@click.option(
    "--lang",
    "-l",
    envvar="SWITCH_PARENTAL_CONTROLS_LANG",
    default=DEFAULT_LANG,
    show_default=True,
    help="Language code (e.g. en-US).",
)
@click.pass_context
def cli(ctx: click.Context, timezone: str, lang: str) -> None:
    """Nintendo Switch Parental Controls CLI."""
    ctx.ensure_object(dict)
    ctx.obj["timezone"] = timezone
    ctx.obj["lang"] = lang


# ---------------------------------------------------------------------------
# MCP server subcommand
# ---------------------------------------------------------------------------


@cli.command("mcp")
def mcp_server() -> None:
    """Start the MCP server (for use with AI assistants)."""
    from switch_parental_controls.server import main

    main()


# ---------------------------------------------------------------------------
# Authentication
# ---------------------------------------------------------------------------


@cli.command("logout")
def logout_cmd() -> None:
    """Remove the saved session token from the credentials file."""
    from switch_parental_controls.credentials import delete_token

    try:
        found = delete_token()
    except OSError as exc:
        raise click.ClickException(f"Could not remove credentials file: {exc}") from exc
    if found:
        click.echo("✓ Logged out — credentials file removed.")
    else:
        click.echo("Nothing to do — no credentials file found.")


@cli.command("login")
@click.pass_obj
def login_cmd(obj: dict) -> None:
    """Interactive OAuth login — opens a Nintendo login URL then completes the flow.

    The session token is saved to ~/.config/switch-parental-controls/credentials so
    all other commands work without any further setup. For CI pipelines or other
    tools that need the token directly, the export snippet is also printed.
    """

    async def run() -> str:
        import shlex

        import aiohttp
        from pynintendoparental import NintendoParental
        from pynintendoparental.authenticator import Authenticator

        http_session = aiohttp.ClientSession()
        try:
            auth = Authenticator(client_session=http_session)
            click.echo(
                "## Nintendo Login\n\n"
                "1. Open this URL in your browser:\n\n"
                f"   {auth.login_url}\n\n"
                "2. Log in with your Nintendo Account.\n\n"
                "3. On the next page, right-click (desktop) or long-press (mobile) the\n"
                "   'Select this person' button and copy the link address.\n\n"
                "4. Paste the copied URL below."
            )
            redirect_url = click.prompt("\nRedirect URL")
            await auth.async_complete_login(redirect_url)
            session_token = auth.session_token

            client = await NintendoParental.create(auth, timezone=obj["timezone"], lang=obj["lang"])
            await client.update()
            _state["client"] = client
        finally:
            await http_session.close()

        from switch_parental_controls.credentials import save_token

        creds_path = save_token(session_token)

        return (
            f"\n✓ Login successful! Token saved to {creds_path}\n\n"
            "You can now run any command — no further setup needed.\n\n"
            "To use this token in other tools or scripts:\n\n"
            f"  export SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN={shlex.quote(session_token)}"
        )

    _execute(run)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FORMAT_OPTION = click.option(
    "--format",
    "fmt",
    type=click.Choice(["markdown", "json"]),
    default="markdown",
    show_default=True,
    help="Output format.",
)

_DEVICE_ARG = click.argument("device", required=False, default=None, metavar="[DEVICE]")

_TIMER_MODES = {"DAILY", "EACH_DAY_OF_THE_WEEK"}
_RESTRICTION_MODES = {"FORCED_TERMINATION", "ALARM"}
_CONTENT_LEVELS = {"NONE", "CHILDREN", "YOUNG_TEENS", "OLDER_TEENS", "CUSTOM"}
_DAYS = {d.value for d in DayOfWeek}
_HOUR_MINUTE_USAGE = "[DEVICE] HOUR MINUTE"


class _ArgError(Exception):
    """An invalid command argument, reported as an error result."""


def _split(args: tuple, n_extra: int, usage: str) -> tuple[str | None, tuple]:
    """Split nargs=-1 positional args into (device_or_none, extra_args).

    With n_extra=1: 'MODE' → (None, ('MODE',)); 'name MODE' → ('name', ('MODE',))
    With n_extra=2: 'H M' → (None, ('H','M')); 'name H M' → ('name', ('H','M'))
    """
    if len(args) == n_extra:
        return None, args
    if len(args) == n_extra + 1:
        return args[0], args[1:]
    raise click.UsageError(f"Expected: {usage}")


def _value_args(args: tuple, usage: str) -> Callable[[], tuple]:
    """Parser for '[DEVICE] VALUE'."""
    return lambda: _split(args, 1, usage)


def _choice_args(args: tuple, usage: str, name: str, valid: set[str]) -> Callable[[], tuple]:
    """Parser for '[DEVICE] CHOICE', where CHOICE is one of `valid` (case-insensitive)."""

    def parse() -> tuple:
        device, rest = _split(args, 1, usage)
        value = rest[0].upper()
        if value not in valid:
            raise _ArgError(f"{name} must be one of {sorted(valid)}, got '{rest[0]}'.")
        return device, (value,)

    return parse


def _int_args(args: tuple, n_extra: int, usage: str, error: str) -> Callable[[], tuple]:
    """Parser for '[DEVICE] N...' with integer values. `error` may use {0} for the first value."""

    def parse() -> tuple:
        device, rest = _split(args, n_extra, usage)
        try:
            return device, tuple(int(value) for value in rest)
        except ValueError:
            raise _ArgError(error.format(*rest)) from None

    return parse


def _resolve(client, device: str | None) -> str:
    """Resolve device name/ID/None inside an async run() body; returns device_id."""
    try:
        return resolve_device_id(client, device)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


def _run_tool(
    obj: dict,
    tool: Callable[..., Awaitable[str]],
    build_params: Callable[..., Any],
    device: str | None = None,
    parse: Callable[[], tuple] | None = None,
) -> None:
    """Run an MCP tool for one device and print its result.

    Checks the token first, then parses the positional arguments (`parse` returns
    the device and the parsed values), connects, resolves the device and calls
    the tool with `build_params(device_id, *values)`.
    """

    async def run() -> str:
        token = _require_token()
        try:
            target, values = parse() if parse else (device, ())
        except _ArgError as exc:
            return f"Error: {exc}"
        async with switch_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, target)
            try:
                params = build_params(did, *values)
            except Exception as exc:
                return f"Error: {exc}"
            return await tool(params, None)

    _execute(run)


def _device_input(fmt: str) -> Callable[[str], DeviceInput]:
    return lambda did: DeviceInput(device_id=did, response_format=ResponseFormat(fmt))


# ---------------------------------------------------------------------------
# Devices — read
# ---------------------------------------------------------------------------


@cli.command("list-devices")
@_FORMAT_OPTION
@click.pass_obj
def list_devices(obj: dict, fmt: str) -> None:
    """List all Nintendo Switch devices on the account. Refreshes the device cache."""
    from switch_parental_controls.devices import switch_list_devices

    async def run() -> str:
        token = _require_token()
        async with switch_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            result = await switch_list_devices(ListDevicesInput(response_format=ResponseFormat(fmt)), None)
            save_cache(devices_from_client(client))
            return result

    _execute(run)


@cli.command("get-device")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def get_device(obj: dict, device: str | None, fmt: str) -> None:
    """Get detailed status for a specific device."""
    from switch_parental_controls.devices import switch_get_device

    _run_tool(obj, switch_get_device, _device_input(fmt), device)


@cli.command("today-summary")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def today_summary(obj: dict, device: str | None, fmt: str) -> None:
    """Get today's usage summary for a device."""
    from switch_parental_controls.devices import switch_get_today_summary

    _run_tool(obj, switch_get_today_summary, _device_input(fmt), device)


@cli.command("monthly-summary")
@_DEVICE_ARG
@click.option("--year", type=int, default=None, help="Year (e.g. 2024). Omit for most recent.")
@click.option("--month", type=int, default=None, help="Month 1-12. Required if --year is set.")
@click.option("--player", "player_id", default=None, help="Filter to a specific player ID.")
@click.option("--no-cache", "skip_cache", is_flag=True, default=False, help="Skip cache; always fetch fresh data.")
@_FORMAT_OPTION
@click.pass_obj
def monthly_summary(obj: dict, device: str | None, fmt: str, **filters: Any) -> None:
    """Get the monthly usage summary for a device."""
    from switch_parental_controls.summary import switch_get_monthly_summary

    def build_params(did: str) -> MonthlySummaryInput:
        return MonthlySummaryInput(device_id=did, response_format=ResponseFormat(fmt), **filters)

    _run_tool(obj, switch_get_monthly_summary, build_params, device)


@cli.command("playtime")
@_DEVICE_ARG
@click.option("--year", type=int, default=None, help="Year (e.g. 2024). Omit for current month.")
@click.option("--month", type=int, default=None, help="Month 1-12. Required if --year is set.")
@click.option("--day", type=int, default=None, help="Day 1-31. Requires --year and --month.")
@click.option("--player", "player_id", default=None, help="Filter to a specific player ID.")
@click.option("--no-cache", "skip_cache", is_flag=True, default=False, help="Skip cache; always fetch fresh data.")
@_FORMAT_OPTION
@click.pass_obj
def playtime(obj: dict, device: str | None, fmt: str, **filters: Any) -> None:
    """Get per-day playtime breakdown for a month, or a single day."""
    from switch_parental_controls.playtime import switch_get_playtime

    def build_params(did: str) -> PlaytimeInput:
        return PlaytimeInput(device_id=did, response_format=ResponseFormat(fmt), **filters)

    _run_tool(obj, switch_get_playtime, build_params, device)


@cli.command("clear-cache")
@click.option("--device", default=None, metavar="DEVICE", help="Limit to a specific device (name or ID).")
@click.option("--year", type=int, default=None, help="Limit to a specific year.")
@click.option("--month", type=int, default=None, help="Limit to a specific month (1-12). Requires --year.")
@click.pass_obj
def clear_cache_cmd(obj: dict, device: str | None, year: int | None, month: int | None) -> None:
    """Clear locally cached historic play data.

    Removes cached API responses so the next monthly-summary or playtime
    request fetches fresh data. Without options, clears the entire cache.
    """
    from switch_parental_controls.data_cache import clear_data_cache, cleared_message
    from switch_parental_controls.device_cache import find_cached_device_id

    if month is not None and year is None:
        raise click.UsageError("--year is required when --month is given.")

    try:
        device_id = find_cached_device_id(device) if device is not None else None
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    click.echo(cleared_message(clear_data_cache(device_id=device_id, year=year, month=month)))


# ---------------------------------------------------------------------------
# Devices — playtime controls
# ---------------------------------------------------------------------------


@cli.command("set-playtime-limit")
@_DEVICE_ARG
@click.option("--minutes", type=int, default=None, help="Daily limit in minutes (0-360).")
@click.option("--no-limit", "remove_limit", is_flag=True, default=False, help="Remove the daily playtime limit.")
@click.pass_obj
def set_playtime_limit(obj: dict, device: str | None, minutes: int | None, remove_limit: bool) -> None:
    """Set the daily playtime limit.

    Use --minutes N to set a limit (0-360), or --no-limit to remove it entirely.
    """
    from switch_parental_controls.device_settings import switch_set_daily_playtime_limit

    def parse() -> tuple:
        if remove_limit:
            return device, (-1,)
        if minutes is not None:
            return device, (minutes,)
        raise _ArgError("Provide --minutes N or --no-limit.")

    def build_params(did: str, mins: int) -> SetPlaytimeLimitInput:
        return SetPlaytimeLimitInput(device_id=did, minutes=mins)

    _run_tool(obj, switch_set_daily_playtime_limit, build_params, parse=parse)


@dataclass(frozen=True)
class _Setting:
    """A '[DEVICE] VALUE...' command that calls a device_settings tool."""

    name: str
    metavar: str
    help_text: str
    tool_name: str
    build_params: Callable[..., Any]
    parse: Callable[[tuple], Callable[[], tuple]]


def _setting_command(setting: _Setting) -> click.Command:
    """Register the command for a setting."""

    @cli.command(setting.name, help=setting.help_text)
    @click.argument("args", nargs=-1, metavar=setting.metavar)
    @click.pass_obj
    def command(obj: dict, args: tuple) -> None:
        from switch_parental_controls import device_settings

        tool = getattr(device_settings, setting.tool_name)
        _run_tool(obj, tool, setting.build_params, parse=setting.parse(args))

    return command


def _hour_minute_args(args: tuple) -> Callable[[], tuple]:
    return _int_args(args, 2, _HOUR_MINUTE_USAGE, "HOUR and MINUTE must be integers.")


add_extra_time = _setting_command(
    _Setting(
        "add-extra-time",
        "[DEVICE] MINUTES",
        """Add extra playtime for today.

    MINUTES is required (1-360). DEVICE is optional if the account has one device.

    \b
    Examples:
      add-extra-time 30
      add-extra-time "Switch #1" 30
    """,
        "switch_add_extra_time",
        lambda did, minutes: AddExtraTimeInput(device_id=did, minutes=minutes),
        lambda args: _int_args(args, 1, "[DEVICE] MINUTES", "MINUTES must be an integer, got '{0}'."),
    )
)

set_timer_mode = _setting_command(
    _Setting(
        "set-timer-mode",
        "[DEVICE] MODE",
        """Set timer mode: DAILY or EACH_DAY_OF_THE_WEEK.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-timer-mode DAILY
      set-timer-mode "Switch #1" EACH_DAY_OF_THE_WEEK
    """,
        "switch_set_timer_mode",
        lambda did, mode: SetTimerModeInput(device_id=did, mode=mode),
        lambda args: _choice_args(args, "[DEVICE] DAILY|EACH_DAY_OF_THE_WEEK", "MODE", _TIMER_MODES),
    )
)


@cli.command("set-day-restrictions")
@click.argument("args", nargs=-1, metavar="[DEVICE] DAY")
@click.option("--playtime-enabled/--playtime-disabled", required=True, help="Enable/disable playtime limit.")
@click.option(
    "--max-playtime-minutes", type=int, default=None, help="Limit in minutes (0-360). Required with --playtime-enabled."
)  # noqa: E501
@click.option("--bedtime-enabled/--bedtime-disabled", required=True, help="Enable/disable bedtime restrictions.")
@click.option(
    "--bedtime-alarm-hour", type=int, default=None, help="Alarm hour (16-23). Required with --bedtime-enabled."
)  # noqa: E501
@click.option("--bedtime-alarm-minute", type=int, default=0, show_default=True, help="Alarm minute (0-59).")
@click.option("--bedtime-end-hour", type=int, default=None, help="End hour (5-9). Required with --bedtime-enabled.")
@click.option("--bedtime-end-minute", type=int, default=0, show_default=True, help="End minute (0-59).")
@click.pass_obj
def set_day_restrictions(obj: dict, args: tuple, **restrictions: Any) -> None:
    """Set playtime and bedtime restrictions for a specific day of the week.

    DAY must be one of: MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY SUNDAY.
    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-day-restrictions MONDAY --playtime-enabled --max-playtime-minutes 90 --bedtime-disabled
      set-day-restrictions "Switch #1" SATURDAY --playtime-disabled --bedtime-disabled
    """
    from switch_parental_controls.device_settings import switch_set_day_restrictions

    def build_params(did: str, day: str) -> SetDayRestrictionsInput:
        return SetDayRestrictionsInput(device_id=did, day_of_week=DayOfWeek(day), **restrictions)

    _run_tool(
        obj,
        switch_set_day_restrictions,
        build_params,
        parse=_choice_args(args, "[DEVICE] DAY", "DAY", _DAYS),
    )


# ---------------------------------------------------------------------------
# Devices — restriction controls
# ---------------------------------------------------------------------------

set_restriction_mode = _setting_command(
    _Setting(
        "set-restriction-mode",
        "[DEVICE] MODE",
        """Set what happens when the limit is reached: FORCED_TERMINATION or ALARM.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-restriction-mode ALARM
      set-restriction-mode "Switch #1" FORCED_TERMINATION
    """,
        "switch_set_restriction_mode",
        lambda did, mode: SetRestrictionModeInput(device_id=did, mode=mode),
        lambda args: _choice_args(args, "[DEVICE] FORCED_TERMINATION|ALARM", "MODE", _RESTRICTION_MODES),
    )
)

set_content_restriction = _setting_command(
    _Setting(
        "set-content-restriction",
        "[DEVICE] LEVEL",
        """Set content restriction level: NONE, CHILDREN, YOUNG_TEENS, OLDER_TEENS, or CUSTOM.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-content-restriction CHILDREN
      set-content-restriction "Switch #1" YOUNG_TEENS
    """,
        "switch_set_content_restriction_level",
        lambda did, level: SetContentRestrictionInput(device_id=did, level=level),
        lambda args: _choice_args(
            args, "[DEVICE] NONE|CHILDREN|YOUNG_TEENS|OLDER_TEENS|CUSTOM", "LEVEL", _CONTENT_LEVELS
        ),
    )
)

set_bedtime_alarm = _setting_command(
    _Setting(
        "set-bedtime-alarm",
        _HOUR_MINUTE_USAGE,
        """Set bedtime alarm time. HOUR 16-23 (or 0 0 to disable).

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-bedtime-alarm 21 0
      set-bedtime-alarm "Switch #1" 21 30
    """,
        "switch_set_bedtime_alarm",
        lambda did, hour, minute: SetBedtimeAlarmInput(device_id=did, hour=hour, minute=minute),
        _hour_minute_args,
    )
)

set_bedtime_end = _setting_command(
    _Setting(
        "set-bedtime-end",
        _HOUR_MINUTE_USAGE,
        """Set when bedtime ends / device is usable again. HOUR 5-9 (or 0 0 to disable).

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-bedtime-end 7 0
      set-bedtime-end "Switch #1" 7 30
    """,
        "switch_set_bedtime_end_time",
        lambda did, hour, minute: SetBedtimeEndInput(device_id=did, hour=hour, minute=minute),
        _hour_minute_args,
    )
)


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


@cli.command("list-players")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def list_players(obj: dict, device: str | None, fmt: str) -> None:
    """List all players (Nintendo accounts) on a device."""
    from switch_parental_controls.players import switch_list_players

    _run_tool(obj, switch_list_players, _device_input(fmt), device)


@cli.command("get-player")
@click.argument("args", nargs=-1, metavar="[DEVICE] PLAYER_ID")
@_FORMAT_OPTION
@click.pass_obj
def get_player(obj: dict, args: tuple, fmt: str) -> None:
    """Get details for a specific player on a device.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      get-player player-001
      get-player "Switch #1" player-001
    """
    from switch_parental_controls.players import switch_get_player

    _run_tool(
        obj,
        switch_get_player,
        lambda did, player_id: PlayerInput(device_id=did, player_id=player_id, response_format=ResponseFormat(fmt)),
        parse=_value_args(args, "[DEVICE] PLAYER_ID"),
    )


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


@cli.command("list-applications")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def list_applications(obj: dict, device: str | None, fmt: str) -> None:
    """List all tracked applications (games) on a device."""
    from switch_parental_controls.applications import switch_list_applications

    _run_tool(obj, switch_list_applications, _device_input(fmt), device)


@cli.command("set-app-allow-list")
@click.argument("args", nargs=-1, metavar="[DEVICE] APP_ID")
@click.option("--allow/--no-allow", required=True, help="Add or remove the app from the allow list.")
@click.pass_obj
def set_app_allow_list(obj: dict, args: tuple, allow: bool) -> None:
    """Add or remove an app from the content-restriction allow list.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-app-allow-list 0100D71004694000 --allow
      set-app-allow-list "Switch #1" 0100D71004694000 --no-allow
    """
    from switch_parental_controls.applications import switch_set_app_allow_list

    _run_tool(
        obj,
        switch_set_app_allow_list,
        lambda did, app_id: SetAppAllowListInput(device_id=did, application_id=app_id, allow=allow),
        parse=_value_args(args, "[DEVICE] APP_ID"),
    )
