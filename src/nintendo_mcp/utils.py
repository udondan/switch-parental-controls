"""Shared utility functions for the Nintendo MCP server."""

import json
from datetime import datetime, time
from typing import Any


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
    except (ValueError, OSError):
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


def handle_error(e: Exception) -> str:
    """Return a clear, actionable error message for common exceptions."""
    error_type = type(e).__name__
    message = str(e)

    if "401" in message or "Unauthorized" in message:
        return (
            "Error: Authentication failed. Your session token may have expired. "
            "Call nintendo_get_login_url to start a new login flow."
        )
    if "403" in message or "Forbidden" in message:
        return "Error: Access denied. You don't have permission to perform this action."
    if "404" in message or "Not Found" in message:
        return "Error: Resource not found. Check that the device_id or player_id is correct."
    if "429" in message or "Too Many Requests" in message:
        return "Error: Rate limit exceeded. Please wait a moment before trying again."
    if "timeout" in message.lower() or "TimeoutError" in error_type:
        return "Error: Request timed out. Nintendo's servers may be slow. Please try again."
    if "NoDevicesFound" in error_type:
        return "Error: No Nintendo Switch devices found on this account."
    if "NotAuthenticated" in error_type:
        return (
            "Error: Not authenticated. Set the NINTENDO_SESSION_TOKEN environment variable, "
            "or call nintendo_get_login_url to start the login flow."
        )

    return f"Error: {error_type}: {message}"


def to_json(data: Any) -> str:
    """Serialize data to a pretty-printed JSON string."""
    return json.dumps(data, indent=2, default=str)


def require_client(client: Any) -> str | None:
    """Return an error string if the client is not initialized, else None."""
    if client is None:
        return (
            "Error: Not authenticated. Set the NINTENDO_SESSION_TOKEN environment variable "
            "before starting the server, or call nintendo_get_login_url to start the interactive login flow."
        )
    return None
