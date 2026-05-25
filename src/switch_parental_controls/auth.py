"""Authentication tools for the Nintendo MCP server.

These tools guide users through the Nintendo OAuth login flow to obtain
a session token. They work even when no session token is configured.
"""

import shlex

import aiohttp
from mcp.server.fastmcp import Context

from switch_parental_controls.models import CompleteLoginInput
from switch_parental_controls.server import _state, mcp
from switch_parental_controls.utils import handle_error


@mcp.tool(
    name="nintendo_get_login_url",
    annotations={
        "title": "Get Nintendo Login URL",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def nintendo_get_login_url(ctx: Context) -> str:
    """Get the Nintendo login URL to start the interactive authentication flow.

    Use this tool when you don't have a session token yet, or when the current
    token has expired. This generates a Nintendo OAuth URL that the user must
    open in their browser.

    After opening the URL and logging in with their Nintendo Account, the user
    will see a "Select this person" button. They should right-click it (or
    long-press on mobile) to copy the link, then pass that URL to
    nintendo_complete_login.

    Returns:
        str: Step-by-step instructions including the Nintendo login URL.

    Error Handling:
        - Returns "Error: ..." if the login URL cannot be generated.
    """
    try:
        http_session = _state.get("http_session")
        if http_session is None or http_session.closed:
            http_session = aiohttp.ClientSession()
            _state["http_session"] = http_session

        from pynintendoparental.authenticator import Authenticator

        # Store the authenticator in state so nintendo_complete_login can use it
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
            "6. Call **`nintendo_complete_login`** with that URL as the `redirect_url` parameter.\n\n"
            "> **Tip:** Once you have a session token, save it as the `NINTENDO_SESSION_TOKEN` "
            "environment variable to avoid logging in again next time."
        )
    except Exception as e:
        return handle_error(e)


@mcp.tool(
    name="nintendo_complete_login",
    annotations={
        "title": "Complete Nintendo Login",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def nintendo_complete_login(params: CompleteLoginInput, ctx: Context) -> str:
    """Complete the Nintendo login flow using the redirect URL from the browser.

    Call this after nintendo_get_login_url. Paste the URL you copied from the
    'Select this person' button on the Nintendo login page.

    On success, this tool returns your session token. Save it as the
    NINTENDO_SESSION_TOKEN environment variable to avoid logging in again.

    Args:
        params (CompleteLoginInput): Validated input containing:
            - redirect_url (str): The URL copied from the 'Select this person' button.
              Starts with 'npf71b963c1b7b6d119://' or similar.

    Returns:
        str: Success message with the session token, or an error message.

    Error Handling:
        - Returns "Error: ..." if the redirect URL is invalid or login fails.
        - Returns "Error: ..." if nintendo_get_login_url was not called first.
    """
    try:
        auth = _state.get("pending_auth")
        if auth is None:
            return (
                "Error: No pending login found. Please call nintendo_get_login_url first "
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
                    "update nintendo_complete_login for the installed library version"
                )
            auth._client_session = http_session

        await auth.async_complete_login(params.redirect_url)
        session_token = auth.session_token

        # Initialize the Nintendo client with the new token
        from pynintendoparental import NintendoParental

        timezone = _state.get("timezone") or "Europe/London"
        lang = _state.get("lang") or "en-GB"
        client = await NintendoParental.create(auth, timezone=timezone, lang=lang)
        await client.update()
        _state["client"] = client
        _state["pending_auth"] = None

        return (
            "## Login Successful!\n\n"
            f"Your Nintendo session token is:\n\n"
            f"```\n{session_token}\n```\n\n"
            "**Save this token** as the `NINTENDO_SESSION_TOKEN` environment variable "
            "to avoid logging in again next time:\n\n"
            f"```bash\nexport NINTENDO_SESSION_TOKEN={shlex.quote(session_token)}\n```\n\n"
            "You can now use all Nintendo parental control tools. "
            "Try `nintendo_list_devices` to see your devices."
        )
    except Exception as e:
        return handle_error(e)
