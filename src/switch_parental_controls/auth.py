"""Authentication tools for the Nintendo MCP server.

These tools guide users through the Nintendo OAuth login flow to obtain
a session token. They work even when no session token is configured.
"""

import shlex

import aiohttp
from mcp.server.mcpserver import Context

from switch_parental_controls.models import CompleteLoginInput
from switch_parental_controls.server import DEFAULT_LANG, DEFAULT_TIMEZONE, _state, mcp
from switch_parental_controls.tools import model_tool, tool_annotations
from switch_parental_controls.utils import handle_error


@mcp.tool(
    name="switch_get_login_url",
    annotations=tool_annotations("Get Nintendo Login URL", read_only=True, idempotent=False),
)
async def switch_get_login_url(ctx: Context) -> str:
    """Start the Nintendo login: returns the login URL and the steps to follow.

    Use it first when the server has no session token, or after a tool reported
    that the token expired. The user opens the URL, logs in, copies the link of
    the "Select this person" button and gives it to switch_complete_login.
    Every call starts a new login and replaces the previous one.

    Returns "Error: ..." if the login URL cannot be created.
    """
    try:
        http_session = _state.get("http_session")
        if http_session is None or http_session.closed:
            http_session = aiohttp.ClientSession()
            _state["http_session"] = http_session

        from pynintendoparental.authenticator import Authenticator

        # Store the authenticator in state so switch_complete_login can use it
        auth = Authenticator(client_session=http_session)
        _state["pending_auth"] = auth

        login_url = auth.login_url

        return (
            "## Nintendo Login Instructions\n\n"
            "Follow these steps to authenticate with your Nintendo Account:\n\n"
            "1. **Open this URL in your browser:**\n\n"
            f"   {login_url}\n\n"
            "2. **Log in** with your Nintendo Account credentials.\n\n"
            "3. After logging in, you will see a **'Select this person'** button.\n\n"
            "4. **Right-click** (desktop) or **long-press** (mobile) the 'Select this person' button "
            "and copy the link address.\n\n"
            "5. The copied URL will start with `npf71b963c1b7b6d119://` or similar.\n\n"
            "6. Call **`switch_complete_login`** with that URL as the `redirect_url` parameter.\n\n"
            "> **Tip:** Once you have a session token, save it as the `SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN` "
            "environment variable to avoid logging in again next time."
        )
    except Exception as e:
        return handle_error(e)


@model_tool(
    "switch_complete_login",
    CompleteLoginInput,
    tool_annotations("Complete Nintendo Login", read_only=False, idempotent=False),
)
async def switch_complete_login(params: CompleteLoginInput, ctx: Context) -> str:
    """Finish the Nintendo login with the link copied after switch_get_login_url.

    Use it once the user has the link of the "Select this person" button. It
    signs in, makes the other tools usable and returns the session token with
    the command to save it as SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN.

    Returns "Error: No pending login found. ..." if switch_get_login_url was not
    called first, and "Error: ..." if the link is invalid or the login fails.
    """
    try:
        auth = _state.get("pending_auth")
        if auth is None:
            return (
                "Error: No pending login found. Please call switch_get_login_url first "
                "to generate a login URL, then complete the browser login before calling this tool."
            )

        http_session = _state.get("http_session")
        if http_session is None or http_session.closed:
            http_session = aiohttp.ClientSession()
            _state["http_session"] = http_session
            # pynintendoparental>=2.3.4 exposes no public session setter; _client_session
            # is the only way to swap a closed session between tool calls. Recreating
            # the Authenticator is not an option because PKCE state from the earlier
            # login URL call would be lost.
            if not hasattr(auth, "_client_session"):
                raise AttributeError(
                    "pynintendoparental.Authenticator no longer exposes '_client_session'; "
                    "update switch_complete_login for the installed library version"
                )
            auth._client_session = http_session

        await auth.async_complete_login(params.redirect_url)
        session_token = auth.session_token

        # Initialize the Nintendo client with the new token
        from pynintendoparental import NintendoParental

        timezone = _state.get("timezone") or DEFAULT_TIMEZONE
        lang = _state.get("lang") or DEFAULT_LANG
        client = await NintendoParental.create(auth, timezone=timezone, lang=lang)
        await client.update()
        _state["client"] = client
        _state["pending_auth"] = None

        return (
            "## Login Successful!\n\n"
            f"Your Nintendo session token is:\n\n"
            f"```\n{session_token}\n```\n\n"
            "**Save this token** as the `SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN` environment variable "
            "to avoid logging in again next time:\n\n"
            f"```bash\nexport SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN={shlex.quote(session_token)}\n```\n\n"
            "You can now use all Nintendo parental control tools. "
            "Try `switch_list_devices` to see your devices."
        )
    except Exception as e:
        return handle_error(e)
