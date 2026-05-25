"""Shared Nintendo client initialization for MCP server and CLI."""

import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

import aiohttp


async def create_client(
    session_token: str,
    timezone: str,
    lang: str,
    http_session: aiohttp.ClientSession,
):
    """Initialize and return a NintendoParental client from a session token."""
    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    auth = Authenticator(session_token=session_token, client_session=http_session)
    await auth.async_complete_login(use_session_token=True)
    client = await NintendoParental.create(auth, timezone=timezone, lang=lang)
    await client.update()
    return client


@asynccontextmanager
async def nintendo_client(
    timezone: str,
    lang: str,
    session_token: str | None,
) -> AsyncGenerator[tuple, None]:
    """Async context manager that yields (client_or_None, http_session).

    Creates an aiohttp session, optionally initializes a NintendoParental client,
    and ensures the session is closed on exit even if an exception occurs.
    """
    http_session = aiohttp.ClientSession()
    client = None
    try:
        if session_token:
            client = await create_client(session_token, timezone, lang, http_session)
        yield client, http_session
    finally:
        if not http_session.closed:
            await http_session.close()


def get_env_token() -> str | None:
    """Return NINTENDO_SESSION_TOKEN from environment, or None."""
    return os.environ.get("NINTENDO_SESSION_TOKEN") or None
