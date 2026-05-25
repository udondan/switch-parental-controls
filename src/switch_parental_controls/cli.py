"""Nintendo Switch Parental Controls CLI.

Each subcommand mirrors an MCP tool. The 'mcp' subcommand starts the MCP server.

Authentication:
    Run 'switch-parental-controls login' for an interactive OAuth flow, or set
    NINTENDO_SESSION_TOKEN in the environment before running any other command.

Environment Variables:
    NINTENDO_SESSION_TOKEN: Nintendo session token.
    NINTENDO_TIMEZONE: IANA timezone string (default: Europe/London).
    NINTENDO_LANG: Language code (default: en-GB).
"""

import asyncio
import os
import sys

import click

from switch_parental_controls.client import nintendo_client
from switch_parental_controls.device_cache import devices_from_client, resolve_device_id, save_cache
from switch_parental_controls.models import (
    AddExtraTimeInput,
    DayOfWeek,
    DeviceInput,
    ListDevicesInput,
    MonthlySummaryInput,
    PlayerInput,
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
from switch_parental_controls.server import _state


def _require_token() -> str:
    """Return session token from env var or credentials file, or exit with an error."""
    from switch_parental_controls.credentials import load_token

    token = os.environ.get("NINTENDO_SESSION_TOKEN") or load_token()
    if not token:
        click.echo(
            "Error: Not authenticated.\n"
            "Run 'switch-parental-controls login' to authenticate.",
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


def _output(result: str) -> None:
    """Print result and exit 1 if it is an error."""
    click.echo(result)
    if result.startswith("Error:"):
        sys.exit(1)


def _execute(coro_factory) -> None:
    """Run an async coroutine factory and output the result."""
    try:
        result = asyncio.run(coro_factory())
    except Exception as exc:
        exc_type = type(exc).__name__
        if "InvalidSessionToken" in exc_type or "invalid_grant" in str(exc):
            click.echo(
                "Error: Saved token is invalid or expired.\n"
                "Run 'switch-parental-controls login' to re-authenticate.",
                err=True,
            )
            sys.exit(1)
        raise
    _output(result)


@click.group()
@click.option(
    "--timezone",
    "-t",
    envvar="NINTENDO_TIMEZONE",
    default="Europe/London",
    show_default=True,
    help="IANA timezone (e.g. America/New_York).",
)
@click.option(
    "--lang",
    "-l",
    envvar="NINTENDO_LANG",
    default="en-GB",
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

    if delete_token():
        click.echo("✓ Logged out — credentials file removed.")
    else:
        click.echo("Nothing to do — no credentials file found.")


@cli.command("login")
@click.pass_obj
def login_cmd(obj: dict) -> None:
    """Interactive OAuth login — opens a Nintendo login URL then completes the flow.

    After running this command you will receive a session token. Export it as
    NINTENDO_SESSION_TOKEN to use all other commands without logging in again.
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
            f"  export NINTENDO_SESSION_TOKEN={shlex.quote(session_token)}"
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


def _resolve(client, device: str | None) -> str:
    """Resolve device name/ID/None inside an async run() body; returns device_id."""
    try:
        return resolve_device_id(client, device)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc


# ---------------------------------------------------------------------------
# Devices — read
# ---------------------------------------------------------------------------


@cli.command("list-devices")
@_FORMAT_OPTION
@click.pass_obj
def list_devices(obj: dict, fmt: str) -> None:
    """List all Nintendo Switch devices on the account. Refreshes the device cache."""
    from switch_parental_controls.devices import nintendo_list_devices

    async def run() -> str:
        token = _require_token()
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            result = await nintendo_list_devices(ListDevicesInput(response_format=ResponseFormat(fmt)), None)
            save_cache(devices_from_client(client))
            return result

    _execute(run)


@cli.command("get-device")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def get_device(obj: dict, device: str | None, fmt: str) -> None:
    """Get detailed status for a specific device."""
    from switch_parental_controls.devices import nintendo_get_device

    async def run() -> str:
        token = _require_token()
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device)
            return await nintendo_get_device(DeviceInput(device_id=did, response_format=ResponseFormat(fmt)), None)

    _execute(run)


@cli.command("today-summary")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def today_summary(obj: dict, device: str | None, fmt: str) -> None:
    """Get today's usage summary for a device."""
    from switch_parental_controls.devices import nintendo_get_today_summary

    async def run() -> str:
        token = _require_token()
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device)
            return await nintendo_get_today_summary(
                DeviceInput(device_id=did, response_format=ResponseFormat(fmt)), None
            )

    _execute(run)


@cli.command("monthly-summary")
@_DEVICE_ARG
@click.option("--year", type=int, default=None, help="Year (e.g. 2024). Omit for most recent.")
@click.option("--month", type=int, default=None, help="Month 1-12. Required if --year is set.")
@_FORMAT_OPTION
@click.pass_obj
def monthly_summary(obj: dict, device: str | None, year: int | None, month: int | None, fmt: str) -> None:
    """Get the monthly usage summary for a device."""
    from switch_parental_controls.devices import nintendo_get_monthly_summary

    async def run() -> str:
        token = _require_token()
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device)
            try:
                params = MonthlySummaryInput(device_id=did, year=year, month=month, response_format=ResponseFormat(fmt))
            except Exception as exc:
                return f"Error: {exc}"
            return await nintendo_get_monthly_summary(params, None)

    _execute(run)


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
    from switch_parental_controls.devices import nintendo_set_daily_playtime_limit

    async def run() -> str:
        token = _require_token()
        if remove_limit:
            mins = -1
        elif minutes is not None:
            mins = minutes
        else:
            return "Error: Provide --minutes N or --no-limit."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device)
            try:
                params = SetPlaytimeLimitInput(device_id=did, minutes=mins)
            except Exception as exc:
                return f"Error: {exc}"
            return await nintendo_set_daily_playtime_limit(params, None)

    _execute(run)


@cli.command("add-extra-time")
@click.argument("args", nargs=-1, metavar="[DEVICE] MINUTES")
@click.pass_obj
def add_extra_time(obj: dict, args: tuple) -> None:
    """Add extra playtime for today.

    MINUTES is required (1-360). DEVICE is optional if the account has one device.

    \b
    Examples:
      add-extra-time 30
      add-extra-time "Switch #1" 30
    """
    from switch_parental_controls.devices import nintendo_add_extra_time

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] MINUTES")
        try:
            minutes = int(rest[0])
        except ValueError:
            return f"Error: MINUTES must be an integer, got '{rest[0]}'."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            try:
                params = AddExtraTimeInput(device_id=did, minutes=minutes)
            except Exception as exc:
                return f"Error: {exc}"
            return await nintendo_add_extra_time(params, None)

    _execute(run)


@cli.command("set-timer-mode")
@click.argument("args", nargs=-1, metavar="[DEVICE] MODE")
@click.pass_obj
def set_timer_mode(obj: dict, args: tuple) -> None:
    """Set timer mode: DAILY or EACH_DAY_OF_THE_WEEK.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-timer-mode DAILY
      set-timer-mode "Switch #1" EACH_DAY_OF_THE_WEEK
    """
    from switch_parental_controls.devices import nintendo_set_timer_mode

    _valid_modes = {"DAILY", "EACH_DAY_OF_THE_WEEK"}

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] DAILY|EACH_DAY_OF_THE_WEEK")
        mode = rest[0].upper()
        if mode not in _valid_modes:
            return f"Error: MODE must be one of {sorted(_valid_modes)}, got '{rest[0]}'."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            return await nintendo_set_timer_mode(SetTimerModeInput(device_id=did, mode=mode), None)

    _execute(run)


@cli.command("set-day-restrictions")
@click.argument("args", nargs=-1, metavar="[DEVICE] DAY")
@click.option("--playtime-enabled/--playtime-disabled", required=True, help="Enable/disable playtime limit.")
@click.option("--max-playtime-minutes", type=int, default=None, help="Limit in minutes (0-360). Required with --playtime-enabled.")  # noqa: E501
@click.option("--bedtime-enabled/--bedtime-disabled", required=True, help="Enable/disable bedtime restrictions.")
@click.option("--bedtime-alarm-hour", type=int, default=None, help="Alarm hour (16-23). Required with --bedtime-enabled.")  # noqa: E501
@click.option("--bedtime-alarm-minute", type=int, default=0, show_default=True, help="Alarm minute (0-59).")
@click.option("--bedtime-end-hour", type=int, default=None, help="End hour (5-9). Required with --bedtime-enabled.")
@click.option("--bedtime-end-minute", type=int, default=0, show_default=True, help="End minute (0-59).")
@click.pass_obj
def set_day_restrictions(
    obj: dict,
    args: tuple,
    playtime_enabled: bool,
    max_playtime_minutes: int | None,
    bedtime_enabled: bool,
    bedtime_alarm_hour: int | None,
    bedtime_alarm_minute: int,
    bedtime_end_hour: int | None,
    bedtime_end_minute: int,
) -> None:
    """Set playtime and bedtime restrictions for a specific day of the week.

    DAY must be one of: MONDAY TUESDAY WEDNESDAY THURSDAY FRIDAY SATURDAY SUNDAY.
    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-day-restrictions MONDAY --playtime-enabled --max-playtime-minutes 90 --bedtime-disabled
      set-day-restrictions "Switch #1" SATURDAY --playtime-disabled --bedtime-disabled
    """
    from switch_parental_controls.devices import nintendo_set_day_restrictions

    _valid_days = {d.value for d in DayOfWeek}

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] DAY")
        day = rest[0].upper()
        if day not in _valid_days:
            return f"Error: DAY must be one of {sorted(_valid_days)}, got '{rest[0]}'."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            try:
                params = SetDayRestrictionsInput(
                    device_id=did,
                    day_of_week=DayOfWeek(day),
                    playtime_enabled=playtime_enabled,
                    max_playtime_minutes=max_playtime_minutes,
                    bedtime_enabled=bedtime_enabled,
                    bedtime_alarm_hour=bedtime_alarm_hour,
                    bedtime_alarm_minute=bedtime_alarm_minute,
                    bedtime_end_hour=bedtime_end_hour,
                    bedtime_end_minute=bedtime_end_minute,
                )
            except Exception as exc:
                return f"Error: {exc}"
            return await nintendo_set_day_restrictions(params, None)

    _execute(run)


# ---------------------------------------------------------------------------
# Devices — restriction controls
# ---------------------------------------------------------------------------


@cli.command("set-restriction-mode")
@click.argument("args", nargs=-1, metavar="[DEVICE] MODE")
@click.pass_obj
def set_restriction_mode(obj: dict, args: tuple) -> None:
    """Set what happens when the limit is reached: FORCED_TERMINATION or ALARM.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-restriction-mode ALARM
      set-restriction-mode "Switch #1" FORCED_TERMINATION
    """
    from switch_parental_controls.devices import nintendo_set_restriction_mode

    _valid = {"FORCED_TERMINATION", "ALARM"}

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] FORCED_TERMINATION|ALARM")
        mode = rest[0].upper()
        if mode not in _valid:
            return f"Error: MODE must be one of {sorted(_valid)}, got '{rest[0]}'."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            return await nintendo_set_restriction_mode(SetRestrictionModeInput(device_id=did, mode=mode), None)

    _execute(run)


@cli.command("set-content-restriction")
@click.argument("args", nargs=-1, metavar="[DEVICE] LEVEL")
@click.pass_obj
def set_content_restriction(obj: dict, args: tuple) -> None:
    """Set content restriction level: NONE, CHILDREN, YOUNG_TEENS, OLDER_TEENS, or CUSTOM.

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-content-restriction CHILDREN
      set-content-restriction "Switch #1" YOUNG_TEENS
    """
    from switch_parental_controls.devices import nintendo_set_content_restriction_level

    _valid = {"NONE", "CHILDREN", "YOUNG_TEENS", "OLDER_TEENS", "CUSTOM"}

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] NONE|CHILDREN|YOUNG_TEENS|OLDER_TEENS|CUSTOM")
        level = rest[0].upper()
        if level not in _valid:
            return f"Error: LEVEL must be one of {sorted(_valid)}, got '{rest[0]}'."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            return await nintendo_set_content_restriction_level(
                SetContentRestrictionInput(device_id=did, level=level), None
            )

    _execute(run)


@cli.command("set-bedtime-alarm")
@click.argument("args", nargs=-1, metavar="[DEVICE] HOUR MINUTE")
@click.pass_obj
def set_bedtime_alarm(obj: dict, args: tuple) -> None:
    """Set bedtime alarm time. HOUR 16-23 (or 0 0 to disable).

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-bedtime-alarm 21 0
      set-bedtime-alarm "Switch #1" 21 30
    """
    from switch_parental_controls.devices import nintendo_set_bedtime_alarm

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 2, "[DEVICE] HOUR MINUTE")
        try:
            hour, minute = int(rest[0]), int(rest[1])
        except ValueError:
            return "Error: HOUR and MINUTE must be integers."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            try:
                params = SetBedtimeAlarmInput(device_id=did, hour=hour, minute=minute)
            except Exception as exc:
                return f"Error: {exc}"
            return await nintendo_set_bedtime_alarm(params, None)

    _execute(run)


@cli.command("set-bedtime-end")
@click.argument("args", nargs=-1, metavar="[DEVICE] HOUR MINUTE")
@click.pass_obj
def set_bedtime_end(obj: dict, args: tuple) -> None:
    """Set when bedtime ends / device is usable again. HOUR 5-9 (or 0 0 to disable).

    DEVICE is optional if the account has one device.

    \b
    Examples:
      set-bedtime-end 7 0
      set-bedtime-end "Switch #1" 7 30
    """
    from switch_parental_controls.devices import nintendo_set_bedtime_end_time

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 2, "[DEVICE] HOUR MINUTE")
        try:
            hour, minute = int(rest[0]), int(rest[1])
        except ValueError:
            return "Error: HOUR and MINUTE must be integers."
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            try:
                params = SetBedtimeEndInput(device_id=did, hour=hour, minute=minute)
            except Exception as exc:
                return f"Error: {exc}"
            return await nintendo_set_bedtime_end_time(params, None)

    _execute(run)


# ---------------------------------------------------------------------------
# Players
# ---------------------------------------------------------------------------


@cli.command("list-players")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def list_players(obj: dict, device: str | None, fmt: str) -> None:
    """List all players (Nintendo accounts) on a device."""
    from switch_parental_controls.players import nintendo_list_players

    async def run() -> str:
        token = _require_token()
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device)
            return await nintendo_list_players(DeviceInput(device_id=did, response_format=ResponseFormat(fmt)), None)

    _execute(run)


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
    from switch_parental_controls.players import nintendo_get_player

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] PLAYER_ID")
        player_id = rest[0]
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            return await nintendo_get_player(
                PlayerInput(device_id=did, player_id=player_id, response_format=ResponseFormat(fmt)), None
            )

    _execute(run)


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------


@cli.command("list-applications")
@_DEVICE_ARG
@_FORMAT_OPTION
@click.pass_obj
def list_applications(obj: dict, device: str | None, fmt: str) -> None:
    """List all tracked applications (games) on a device."""
    from switch_parental_controls.applications import nintendo_list_applications

    async def run() -> str:
        token = _require_token()
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device)
            return await nintendo_list_applications(
                DeviceInput(device_id=did, response_format=ResponseFormat(fmt)), None
            )

    _execute(run)


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
    from switch_parental_controls.applications import nintendo_set_app_allow_list

    async def run() -> str:
        token = _require_token()
        device_raw, rest = _split(args, 1, "[DEVICE] APP_ID")
        application_id = rest[0]
        async with nintendo_client(obj["timezone"], obj["lang"], token) as (client, http_session):
            _populate_state(client, http_session, obj)
            did = _resolve(client, device_raw)
            return await nintendo_set_app_allow_list(
                SetAppAllowListInput(device_id=did, application_id=application_id, allow=allow), None
            )

    _execute(run)
