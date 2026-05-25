"""Nintendo Switch Parental Controls MCP Server.

This server exposes Nintendo Switch Parental Controls as MCP tools, allowing
AI assistants to monitor and manage parental control settings on Nintendo Switch
devices linked to a Nintendo account.

Authentication:
    Set the SWITCH_PARENTAL_CONTROL_SESSION_TOKEN environment variable before starting the server,
    or use the switch_get_login_url / switch_complete_login tools to authenticate
    interactively.

Environment Variables:
    SWITCH_PARENTAL_CONTROL_SESSION_TOKEN: Nintendo session token (optional at startup).
    SWITCH_PARENTAL_CONTROL_TIMEZONE: IANA timezone string (default: Europe/London).
    SWITCH_PARENTAL_CONTROL_LANG: Language code (default: en-GB).
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Mutable state shared across tools (populated by lifespan, switch_complete_login, or CLI via _populate_state)
_state: dict[str, Any] = {
    "client": None,
    "http_session": None,
}


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage the aiohttp session and Nintendo client lifecycle."""
    session_token = os.environ.get("SWITCH_PARENTAL_CONTROL_SESSION_TOKEN")
    if not session_token:
        try:
            from switch_parental_controls.credentials import load_token

            session_token = load_token()
        except Exception:
            pass
    timezone = os.environ.get("SWITCH_PARENTAL_CONTROL_TIMEZONE") or "Europe/London"
    lang = os.environ.get("SWITCH_PARENTAL_CONTROL_LANG") or "en-GB"

    http_session = aiohttp.ClientSession()
    _state["http_session"] = http_session
    _state["timezone"] = timezone
    _state["lang"] = lang

    if session_token:
        try:
            from switch_parental_controls.client import create_client

            _state["client"] = await create_client(session_token, timezone, lang, http_session)
            logger.info("Nintendo Parental Controls client initialized successfully.")
        except Exception as e:
            logger.warning("Failed to initialize Nintendo client on startup: %s", e)
            logger.warning("Use switch_get_login_url to authenticate interactively.")
    else:
        logger.info("SWITCH_PARENTAL_CONTROL_SESSION_TOKEN not set. Use switch_get_login_url to authenticate.")

    try:
        yield _state
    finally:
        session = _state.get("http_session")
        if session is not None and not session.closed:
            await session.close()
        _state["client"] = None
        _state["http_session"] = None
        _state["pending_auth"] = None
        _state["timezone"] = None
        _state["lang"] = None


# Initialize the FastMCP server
mcp = FastMCP(
    "switch_parental_controls",
    instructions=(
        "This server provides tools to manage Nintendo Switch Parental Controls. "
        "If not yet authenticated, call switch_get_login_url first to start the login flow, "
        "then switch_complete_login with the redirect URL. "
        "Once authenticated, use switch_list_devices to see available devices."
    ),
    lifespan=lifespan,
)

# Import tool modules to register their tools on the mcp instance.
# These imports must happen after mcp is defined so the @mcp.tool decorators
# can reference the correct FastMCP instance.
# NOTE: Do NOT run this file directly (e.g. python server.py or python -m switch_parental_controls.server).
# Use 'python -m switch_parental_controls mcp' (or 'switch-parental-controls mcp') instead, which
# routes through __main__.py and ensures this module is always imported as
# 'switch_parental_controls.server' — never executed as '__main__'.
from switch_parental_controls import applications, auth, devices, players  # noqa: E402, F401


def main():
    """Entry point for the MCP server."""
    mcp.run()
