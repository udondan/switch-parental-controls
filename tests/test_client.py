"""Tests for client creation in client.py."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from switch_parental_controls.client import create_client, get_env_token, switch_client


@pytest.fixture
def mock_nintendo():
    """Patch the Authenticator and NintendoParental classes of pynintendoparental."""
    auth = MagicMock()
    auth.async_complete_login = AsyncMock()
    client = MagicMock()
    client.update = AsyncMock()
    with (
        patch("pynintendoparental.authenticator.Authenticator", return_value=auth) as auth_cls,
        patch("pynintendoparental.NintendoParental") as np_cls,
    ):
        np_cls.create = AsyncMock(return_value=client)
        yield auth_cls, auth, np_cls, client


async def test_create_client(mock_nintendo):
    auth_cls, auth, np_cls, client = mock_nintendo
    session = MagicMock()

    result = await create_client("token", "Europe/Berlin", "de-DE", session)

    assert result is client
    auth_cls.assert_called_once_with(session_token="token", client_session=session)
    auth.async_complete_login.assert_awaited_once_with(use_session_token=True)
    np_cls.create.assert_awaited_once_with(auth, timezone="Europe/Berlin", lang="de-DE")
    client.update.assert_awaited_once()


async def test_switch_client_with_token(mock_nintendo):
    _, _, _, client = mock_nintendo
    async with switch_client("Europe/London", "en-GB", "token") as (result, session):
        assert result is client
        assert not session.closed
    assert session.closed


async def test_switch_client_without_token(mock_nintendo):
    _, _, np_cls, _ = mock_nintendo
    async with switch_client("Europe/London", "en-GB", None) as (result, session):
        assert result is None
    assert session.closed
    np_cls.create.assert_not_awaited()


async def test_switch_client_closes_session_on_error(mock_nintendo):
    with pytest.raises(RuntimeError):
        async with switch_client("Europe/London", "en-GB", None) as (_, session):
            raise RuntimeError("boom")
    assert session.closed


async def test_switch_client_session_already_closed(mock_nintendo):
    async with switch_client("Europe/London", "en-GB", None) as (_, session):
        await session.close()
    assert session.closed


def test_get_env_token(monkeypatch):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "token")
    assert get_env_token() == "token"
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "")
    assert get_env_token() is None
    monkeypatch.delenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN")
    assert get_env_token() is None
