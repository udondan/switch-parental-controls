"""Shared utility functions for the Nintendo MCP server."""

import json
from datetime import datetime, time
from typing import Any

# Month label in summaries, e.g. "March 2024".
MONTH_LABEL_FORMAT = "%B %Y"


def format_time(t: time | None) -> str:
    """Format a time object as HH:MM string, or 'disabled' if None or 00:00."""
    if t is None or t == time(0, 0):
        return "disabled"
    return t.strftime("%H:%M")


def format_timestamp(ts: float | None) -> str:
    """Format a Unix timestamp as a human-readable datetime string."""
    if ts is None:
        return "never"
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, OSError, OverflowError):
        return str(ts)


def format_minutes(minutes: int | float | None) -> str:
    """Format minutes as a human-readable string (e.g. '1h 30m' or 'no limit')."""
    if minutes is None or minutes == -1:
        return "no limit"
    minutes = int(minutes)
    if minutes == 0:
        return "0 minutes"
    hours, mins = divmod(minutes, 60)
    parts = []
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    return " ".join(parts)


class ToolError(Exception):
    """An error whose message is returned to the caller unchanged."""


# (matches(error_type, message), user-facing message), checked in order.
_ERROR_RULES = [
    (
        lambda _t, m: "401" in m or "Unauthorized" in m,
        "Error: Authentication failed. Your session token may have expired. "
        "Call switch_get_login_url to start a new login flow.",
    ),
    (
        lambda _t, m: "403" in m or "Forbidden" in m,
        "Error: Access denied. You don't have permission to perform this action.",
    ),
    (
        lambda _t, m: "404" in m or "Not Found" in m,
        "Error: Resource not found. Check that the device_id or player_id is correct.",
    ),
    (
        lambda _t, m: "429" in m or "Too Many Requests" in m,
        "Error: Rate limit exceeded. Please wait a moment before trying again.",
    ),
    (
        lambda t, m: "timeout" in m.lower() or "TimeoutError" in t,
        "Error: Request timed out. Nintendo's servers may be slow. Please try again.",
    ),
    (
        lambda t, _m: "NoDevicesFound" in t,
        "Error: No Nintendo Switch devices found on this account.",
    ),
    (
        lambda t, _m: "NotAuthenticated" in t,
        "Error: Not authenticated. Set the SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN environment variable, "
        "or call switch_get_login_url to start the login flow.",
    ),
]


def handle_error(e: Exception) -> str:
    """Return a clear, actionable error message for common exceptions."""
    if isinstance(e, ToolError):
        return str(e)
    error_type = type(e).__name__
    message = str(e)
    for matches, text in _ERROR_RULES:
        if matches(error_type, message):
            return text
    return f"Error: {error_type}: {message}"


def to_json(data: Any) -> str:
    """Serialize data to a pretty-printed JSON string."""
    return json.dumps(data, indent=2, default=str)


def require_client(client: Any) -> str | None:
    """Return an error string if the client is not initialized, else None."""
    if client is None:
        return (
            "Error: Not authenticated. Set the SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN environment variable "
            "before starting the server, or call switch_get_login_url to start the interactive login flow."
        )
    return None
