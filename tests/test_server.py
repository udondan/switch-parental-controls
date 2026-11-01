"""Tests for the MCP server lifespan and entry points."""

import logging
import runpy
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from switch_parental_controls import server


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    for var in (
        "SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN",
        "SWITCH_PARENTAL_CONTROLS_TIMEZONE",
        "SWITCH_PARENTAL_CONTROLS_LANG",
    ):
        monkeypatch.delenv(var, raising=False)


def _assert_state_cleared():
    for key in ("client", "http_session", "pending_auth", "timezone", "lang"):
        assert server._state[key] is None


async def test_lifespan_with_env_token(monkeypatch):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "env-token")
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_TIMEZONE", "Europe/Berlin")
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_LANG", "de-DE")
    client = MagicMock()

    with patch("switch_parental_controls.client.create_client", AsyncMock(return_value=client)) as create:
        async with server.lifespan(server.mcp) as state:
            assert state["client"] is client
            assert state["timezone"] == "Europe/Berlin"
            assert state["lang"] == "de-DE"
            session = state["http_session"]
            assert not session.closed

    create.assert_awaited_once_with("env-token", "Europe/Berlin", "de-DE", session)
    assert session.closed
    _assert_state_cleared()


async def test_lifespan_with_saved_token():
    with (
        patch("switch_parental_controls.credentials.load_token", return_value="saved-token"),
        patch("switch_parental_controls.client.create_client", AsyncMock(return_value=MagicMock())) as create,
    ):
        async with server.lifespan(server.mcp) as state:
            assert state["timezone"] == "Europe/London"
            assert state["lang"] == "en-GB"

    assert create.await_args.args[0] == "saved-token"
    _assert_state_cleared()


async def test_lifespan_without_token(caplog):
    caplog.set_level(logging.INFO, logger="switch_parental_controls.server")
    with patch("switch_parental_controls.credentials.load_token", side_effect=RuntimeError("unreadable")):
        async with server.lifespan(server.mcp) as state:
            assert state["client"] is None

    assert "SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN not set" in caplog.text
    _assert_state_cleared()


async def test_lifespan_client_init_fails(monkeypatch, caplog):
    monkeypatch.setenv("SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN", "bad-token")
    with patch("switch_parental_controls.client.create_client", AsyncMock(side_effect=RuntimeError("expired"))):
        async with server.lifespan(server.mcp) as state:
            assert state["client"] is None

    assert "Failed to initialize Nintendo client on startup: expired" in caplog.text
    _assert_state_cleared()


async def test_lifespan_session_closed_during_run():
    async with server.lifespan(server.mcp) as state:
        await state["http_session"].close()
        state["http_session"] = None
    _assert_state_cleared()


def test_main_runs_server():
    with patch.object(server.mcp, "run") as run:
        server.main()
    run.assert_called_once_with()


def test_module_entry_point_runs_cli():
    with patch("switch_parental_controls.cli.cli") as cli:
        runpy.run_module("switch_parental_controls", run_name="__main__")
    cli.assert_called_once_with()
