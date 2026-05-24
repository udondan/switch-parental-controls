"""Tests for Nintendo MCP player tools."""

import json
from unittest.mock import MagicMock

import pytest

from nintendo_mcp import server
from tests.conftest import make_mock_client, make_mock_device, make_mock_player


@pytest.fixture
def mock_player():
    return make_mock_player(apps=[{"applicationId": "app-001", "playingTime": 30}])


@pytest.fixture
def mock_device(mock_player):
    device = make_mock_device()
    device.players = {mock_player.player_id: mock_player}
    return device


@pytest.fixture
def mock_client(mock_device):
    return make_mock_client(devices={mock_device.device_id: mock_device})


@pytest.fixture(autouse=True)
def set_client(mock_client):
    server._state["client"] = mock_client


# --- nintendo_list_players ---


@pytest.mark.asyncio
async def test_list_players_markdown(mock_player):
    """Should return markdown list of players."""
    from nintendo_mcp.models import DeviceInput
    from nintendo_mcp.players import nintendo_list_players

    ctx = MagicMock()
    result = await nintendo_list_players(DeviceInput(device_id="device-001"), ctx)

    assert "TestKid" in result
    assert "player-001" in result
    assert "45" in result  # playing_time


@pytest.mark.asyncio
async def test_list_players_json(mock_player):
    """Should return JSON list of players."""
    from nintendo_mcp.models import DeviceInput, ResponseFormat
    from nintendo_mcp.players import nintendo_list_players

    ctx = MagicMock()
    result = await nintendo_list_players(
        DeviceInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx
    )
    data = json.loads(result)

    assert data["count"] == 1
    assert data["players"][0]["player_id"] == "player-001"
    assert data["players"][0]["nickname"] == "TestKid"


@pytest.mark.asyncio
async def test_list_players_no_client():
    """Should return auth error when client is not set."""
    server._state["client"] = None
    from nintendo_mcp.models import DeviceInput
    from nintendo_mcp.players import nintendo_list_players

    ctx = MagicMock()
    result = await nintendo_list_players(DeviceInput(device_id="device-001"), ctx)
    assert "Error" in result


@pytest.mark.asyncio
async def test_list_players_device_not_found():
    """Should return error for unknown device ID."""
    from nintendo_mcp.models import DeviceInput
    from nintendo_mcp.players import nintendo_list_players

    ctx = MagicMock()
    result = await nintendo_list_players(DeviceInput(device_id="nonexistent"), ctx)
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_list_players_empty(mock_device, mock_client):
    """Should return 'no players' message when device has no players."""
    mock_device.players = {}
    from nintendo_mcp.models import DeviceInput
    from nintendo_mcp.players import nintendo_list_players

    ctx = MagicMock()
    result = await nintendo_list_players(DeviceInput(device_id="device-001"), ctx)
    assert "No players found" in result


# --- nintendo_get_player ---


@pytest.mark.asyncio
async def test_get_player_markdown(mock_player, mock_device):
    """Should return detailed player info in markdown."""
    from nintendo_mcp.models import PlayerInput
    from nintendo_mcp.players import nintendo_get_player

    ctx = MagicMock()
    result = await nintendo_get_player(
        PlayerInput(device_id="device-001", player_id="player-001"), ctx
    )

    assert "TestKid" in result
    assert "player-001" in result
    assert "45" in result


@pytest.mark.asyncio
async def test_get_player_not_found():
    """Should return error for unknown player ID."""
    from nintendo_mcp.models import PlayerInput
    from nintendo_mcp.players import nintendo_get_player

    ctx = MagicMock()
    result = await nintendo_get_player(
        PlayerInput(device_id="device-001", player_id="nonexistent"), ctx
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_get_player_json(mock_player):
    """Should return JSON player info."""
    from nintendo_mcp.models import PlayerInput, ResponseFormat
    from nintendo_mcp.players import nintendo_get_player

    ctx = MagicMock()
    result = await nintendo_get_player(
        PlayerInput(
            device_id="device-001", player_id="player-001", response_format=ResponseFormat.JSON
        ),
        ctx,
    )
    data = json.loads(result)

    assert data["player"]["player_id"] == "player-001"
    assert data["player"]["nickname"] == "TestKid"
