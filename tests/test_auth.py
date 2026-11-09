"""Tests for Nintendo MCP authentication tools."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from switch_parental_controls import server


@pytest.mark.asyncio
async def test_get_login_url_returns_instructions():
    """switch_get_login_url should return step-by-step instructions with a URL."""
    mock_auth = MagicMock()
    mock_auth.login_url = "https://accounts.nintendo.com/connect/1.0.0/authorize?test=1"

    with patch("pynintendoparental.authenticator.Authenticator", return_value=mock_auth):
        from switch_parental_controls.auth import switch_get_login_url

        ctx = MagicMock()
        result = await switch_get_login_url(ctx)

    assert mock_auth.login_url in result
    assert "switch_complete_login" in result
    assert "Select this person" in result
    assert "SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN" in result


@pytest.mark.asyncio
async def test_get_login_url_stores_pending_auth():
    """switch_get_login_url should store the authenticator in _state."""
    mock_auth = MagicMock()
    mock_auth.login_url = "https://accounts.nintendo.com/test"

    with patch("pynintendoparental.authenticator.Authenticator", return_value=mock_auth):
        from switch_parental_controls.auth import switch_get_login_url

        ctx = MagicMock()
        await switch_get_login_url(ctx)

    assert server._state.get("pending_auth") is mock_auth


@pytest.mark.asyncio
async def test_complete_login_without_pending_auth():
    """switch_complete_login should return an error if no pending auth exists."""
    server._state["pending_auth"] = None

    from switch_parental_controls.auth import switch_complete_login
    from switch_parental_controls.models import CompleteLoginInput

    ctx = MagicMock()
    params = CompleteLoginInput(redirect_url="npf71b963c1b7b6d119://auth#session_token=abc")
    result = await switch_complete_login(params, ctx)

    assert "Error" in result
    assert "switch_get_login_url" in result


@pytest.mark.asyncio
async def test_complete_login_success():
    """switch_complete_login should authenticate and return the session token."""
    mock_auth = MagicMock()
    mock_auth.async_complete_login = AsyncMock()
    mock_auth.session_token = "test-session-token-12345"

    mock_http_session = MagicMock(closed=False)
    mock_http_session.close = AsyncMock()
    mock_client = MagicMock()
    mock_client.update = AsyncMock()
    server._state["pending_auth"] = mock_auth
    server._state["http_session"] = mock_http_session
    server._state["timezone"] = "Europe/London"
    server._state["lang"] = "en-GB"

    with patch("pynintendoparental.NintendoParental") as mock_np_class:
        mock_np_class.create = AsyncMock(return_value=mock_client)

        from switch_parental_controls.auth import switch_complete_login
        from switch_parental_controls.models import CompleteLoginInput

        ctx = MagicMock()
        params = CompleteLoginInput(redirect_url="npf71b963c1b7b6d119://auth#session_token=abc")
        result = await switch_complete_login(params, ctx)

    assert "test-session-token-12345" in result
    assert "Login Successful" in result
    assert server._state["client"] is mock_client
    assert server._state["pending_auth"] is None


@pytest.mark.asyncio
async def test_complete_login_api_error():
    """switch_complete_login should return an error if the API call fails."""
    mock_auth = MagicMock()
    mock_auth.async_complete_login = AsyncMock(side_effect=Exception("Invalid redirect URL"))
    mock_http_session = MagicMock(closed=False)
    mock_http_session.close = AsyncMock()
    server._state["pending_auth"] = mock_auth
    server._state["http_session"] = mock_http_session

    from switch_parental_controls.auth import switch_complete_login
    from switch_parental_controls.models import CompleteLoginInput

    ctx = MagicMock()
    params = CompleteLoginInput(redirect_url="npf71b963c1b7b6d119://auth#bad=data")
    result = await switch_complete_login(params, ctx)

    assert "Error" in result


@pytest.mark.asyncio
async def test_get_login_url_failure():
    """switch_get_login_url should return an error if the authenticator can't be created."""
    with patch("pynintendoparental.authenticator.Authenticator", side_effect=RuntimeError("boom")):
        from switch_parental_controls.auth import switch_get_login_url

        result = await switch_get_login_url(MagicMock())

    assert result == "Error: RuntimeError: boom"


@pytest.mark.asyncio
async def test_complete_login_replaces_closed_session():
    """switch_complete_login should give the pending authenticator a new session if the old one is closed."""
    mock_auth = MagicMock()
    mock_auth.async_complete_login = AsyncMock()
    mock_auth.session_token = "test-session-token"
    mock_auth._client_session = MagicMock(closed=True)
    server._state["pending_auth"] = mock_auth
    server._state["http_session"] = MagicMock(closed=True)

    with patch("pynintendoparental.NintendoParental") as mock_np_class:
        mock_np_class.create = AsyncMock(return_value=MagicMock(update=AsyncMock()))

        from switch_parental_controls.auth import switch_complete_login
        from switch_parental_controls.models import CompleteLoginInput

        params = CompleteLoginInput(redirect_url="npf71b963c1b7b6d119://auth#session_token=abc")
        result = await switch_complete_login(params, MagicMock())

    new_session = server._state["http_session"]
    assert "Login Successful" in result
    assert not new_session.closed
    assert mock_auth._client_session is new_session


@pytest.mark.asyncio
async def test_complete_login_authenticator_without_client_session():
    """switch_complete_login should fail clearly if the library drops the _client_session attribute."""
    mock_auth = MagicMock(spec=["async_complete_login", "session_token"])
    server._state["pending_auth"] = mock_auth
    server._state["http_session"] = None

    from switch_parental_controls.auth import switch_complete_login
    from switch_parental_controls.models import CompleteLoginInput

    params = CompleteLoginInput(redirect_url="npf71b963c1b7b6d119://auth#session_token=abc")
    result = await switch_complete_login(params, MagicMock())

    assert result.startswith("Error: AttributeError: pynintendoparental.Authenticator no longer exposes")
