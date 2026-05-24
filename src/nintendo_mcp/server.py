"""Nintendo Switch Parental Controls MCP Server.

This server exposes Nintendo Switch Parental Controls as MCP tools, allowing
AI assistants to monitor and manage parental control settings on Nintendo Switch
devices linked to a Nintendo account.

Authentication:
    Set the NINTENDO_SESSION_TOKEN environment variable before starting the server,
    or use the nintendo_get_login_url / nintendo_complete_login tools to authenticate
    interactively.

Environment Variables:
    NINTENDO_SESSION_TOKEN: Nintendo session token (optional at startup).
    NINTENDO_TIMEZONE: IANA timezone string (default: Europe/London).
    NINTENDO_LANG: Language code (default: en-GB).
"""

import logging
import os
from contextlib import asynccontextmanager
from typing import Any

import aiohttp
from mcp.server.fastmcp import FastMCP

logger = logging.getLogger(__name__)

# Mutable state shared across tools (populated by lifespan or nintendo_complete_login)
_state: dict[str, Any] = {
    "client": None,
    "http_session": None,
}


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Manage the aiohttp session and Nintendo client lifecycle."""
    session_token = os.environ.get("NINTENDO_SESSION_TOKEN")
    timezone = os.environ.get("NINTENDO_TIMEZONE", "Europe/London")
    lang = os.environ.get("NINTENDO_LANG", "en-GB")

    http_session = aiohttp.ClientSession()
    _state["http_session"] = http_session
    _state["timezone"] = timezone
    _state["lang"] = lang

    if session_token:
        try:
            from pynintendoparental import NintendoParental
            from pynintendoparental.authenticator import Authenticator

            auth = Authenticator(session_token=session_token, client_session=http_session)
            await auth.async_complete_login(use_session_token=True)
            client = await NintendoParental.create(auth, timezone=timezone, lang=lang)
            await client.update()
            _state["client"] = client
            logger.info("Nintendo Parental Controls client initialized successfully.")
        except Exception as e:
            logger.warning("Failed to initialize Nintendo client on startup: %s", e)
            logger.warning("Use nintendo_get_login_url to authenticate interactively.")
    else:
        logger.info("NINTENDO_SESSION_TOKEN not set. Use nintendo_get_login_url to authenticate.")

    try:
        yield _state
    finally:
        await http_session.close()
        _state["client"] = None
        _state["http_session"] = None


# Initialize the FastMCP server
mcp = FastMCP(
    "nintendo_mcp",
    instructions=(
        "This server provides tools to manage Nintendo Switch Parental Controls. "
        "If not yet authenticated, call nintendo_get_login_url first to start the login flow, "
        "then nintendo_complete_login with the redirect URL. "
        "Once authenticated, use nintendo_list_devices to see available devices."
    ),
    lifespan=lifespan,
)

# Import tool modules to register their tools on the mcp instance.
# These imports must happen after mcp is defined so the @mcp.tool decorators
# can reference the correct FastMCP instance.
# NOTE: Do NOT run this file directly (e.g. python server.py or python -m nintendo_mcp.server).
# Use 'python -m nintendo_mcp' instead, which routes through __main__.py and ensures
# this module is always imported as 'nintendo_mcp.server' — never executed as '__main__'.
from nintendo_mcp import applications, auth, devices, players  # noqa: E402, F401


def main():
    """Entry point for the MCP server."""
    mcp.run()
