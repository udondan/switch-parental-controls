"""Integration tests for Nintendo MCP tools using real Nintendo API credentials.

These tests call the actual Nintendo Parental Controls API. They require a
NINTENDO_SESSION_TOKEN set in a .env file or environment. All tests are
read-only — they do not modify any parental control settings.

Run:
    pytest -m integration tests/test_integration.py -v
"""

import os
from unittest.mock import MagicMock

import aiohttp
import pytest

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
async def real_client():
    """Create a real Nintendo Parental Controls client, pre-fetched with a single update()."""
    from dotenv import load_dotenv

    load_dotenv()
    token = os.environ.get("NINTENDO_SESSION_TOKEN")
    if not token:
        pytest.skip("NINTENDO_SESSION_TOKEN not set")

    from pynintendoparental import NintendoParental
    from pynintendoparental.authenticator import Authenticator

    timezone = os.environ.get("NINTENDO_TIMEZONE") or "Europe/London"
    lang = os.environ.get("NINTENDO_LANG") or "en-GB"

    session = aiohttp.ClientSession()
    try:
        auth = Authenticator(session_token=token, client_session=session)
        await auth.async_complete_login(use_session_token=True)
        client = await NintendoParental.create(auth, timezone=timezone, lang=lang)
        await client.update()
        yield client
    finally:
        await session.close()


@pytest.fixture(autouse=True)
async def inject_client(real_client, monkeypatch):
    """Inject the real client into server state.

    The module fixture already called update() once. Stub out subsequent update()
    calls so tests don't hammer the Nintendo API — fresh data is already loaded.
    """
    from unittest.mock import AsyncMock

    from nintendo_mcp import server

    monkeypatch.setattr(real_client, "update", AsyncMock())
    for device in real_client.devices.values():
        monkeypatch.setattr(device, "update", AsyncMock())

    server._state["client"] = real_client
    yield
    server._state["client"] = None


@pytest.fixture(scope="module")
async def first_device_id(real_client):
    """Return the ID of the first device on the account (client already updated)."""
    if not real_client.devices:
        pytest.skip("No Nintendo Switch devices found on this account")
    return next(iter(real_client.devices))


async def test_list_devices():
    """Real device list should be returned as a non-empty string without error."""
    from nintendo_mcp.devices import nintendo_list_devices
    from nintendo_mcp.models import ListDevicesInput

    result = await nintendo_list_devices(ListDevicesInput(), MagicMock())
    assert "Error" not in result
    assert len(result) > 0


async def test_get_device(first_device_id):
    """Real device details should be returned without error."""
    from nintendo_mcp.devices import nintendo_get_device
    from nintendo_mcp.models import DeviceInput

    result = await nintendo_get_device(DeviceInput(device_id=first_device_id), MagicMock())
    assert "Error" not in result
    assert first_device_id in result


async def test_get_today_summary(first_device_id):
    """Today's summary should be returned without an auth error."""
    from nintendo_mcp.devices import nintendo_get_today_summary
    from nintendo_mcp.models import DeviceInput

    result = await nintendo_get_today_summary(DeviceInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_get_monthly_summary(first_device_id):
    """Monthly summary should be returned without an auth error."""
    from nintendo_mcp.devices import nintendo_get_monthly_summary
    from nintendo_mcp.models import MonthlySummaryInput

    result = await nintendo_get_monthly_summary(MonthlySummaryInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_list_players(first_device_id):
    """Player list should be returned without an auth error."""
    from nintendo_mcp.models import DeviceInput
    from nintendo_mcp.players import nintendo_list_players

    result = await nintendo_list_players(DeviceInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result


async def test_list_applications(first_device_id):
    """Application list should be returned without an auth error."""
    from nintendo_mcp.applications import nintendo_list_applications
    from nintendo_mcp.models import DeviceInput

    result = await nintendo_list_applications(DeviceInput(device_id=first_device_id), MagicMock())
    assert isinstance(result, str)
    assert "Error: Not authenticated" not in result
