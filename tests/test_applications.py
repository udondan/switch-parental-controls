"""Tests for Nintendo MCP application tools."""

import json
from unittest.mock import MagicMock

import pytest

from nintendo_mcp import server
from tests.conftest import make_mock_application, make_mock_client, make_mock_device


@pytest.fixture
def mock_app():
    return make_mock_application()


@pytest.fixture
def mock_device(mock_app):
    device = make_mock_device()
    device.applications = {mock_app.application_id: mock_app}
    return device


@pytest.fixture
def mock_client(mock_device):
    return make_mock_client(devices={mock_device.device_id: mock_device})


@pytest.fixture(autouse=True)
def set_client(mock_client):
    server._state["client"] = mock_client


# --- nintendo_list_applications ---


@pytest.mark.asyncio
async def test_list_applications_markdown(mock_app):
    """Should return markdown list of applications."""
    from nintendo_mcp.applications import nintendo_list_applications
    from nintendo_mcp.models import DeviceInput

    ctx = MagicMock()
    result = await nintendo_list_applications(DeviceInput(device_id="device-001"), ctx)

    assert "Test Game" in result
    assert "app-001" in result
    assert "30" in result  # today_time_played


@pytest.mark.asyncio
async def test_list_applications_json(mock_app):
    """Should return JSON list of applications."""
    from nintendo_mcp.applications import nintendo_list_applications
    from nintendo_mcp.models import DeviceInput, ResponseFormat

    ctx = MagicMock()
    result = await nintendo_list_applications(
        DeviceInput(device_id="device-001", response_format=ResponseFormat.JSON), ctx
    )
    data = json.loads(result)

    assert data["count"] == 1
    assert data["applications"][0]["application_id"] == "app-001"
    assert data["applications"][0]["name"] == "Test Game"
    assert data["applications"][0]["allow_list_status"] == "NONE"


@pytest.mark.asyncio
async def test_list_applications_no_client():
    """Should return auth error when client is not set."""
    server._state["client"] = None
    from nintendo_mcp.applications import nintendo_list_applications
    from nintendo_mcp.models import DeviceInput

    ctx = MagicMock()
    result = await nintendo_list_applications(DeviceInput(device_id="device-001"), ctx)
    assert "Error" in result


@pytest.mark.asyncio
async def test_list_applications_empty(mock_device, mock_client):
    """Should return 'no applications' message when device has no apps."""
    mock_device.applications = {}
    from nintendo_mcp.applications import nintendo_list_applications
    from nintendo_mcp.models import DeviceInput

    ctx = MagicMock()
    result = await nintendo_list_applications(DeviceInput(device_id="device-001"), ctx)
    assert "No applications tracked" in result


# --- nintendo_set_app_allow_list ---


@pytest.mark.asyncio
async def test_set_app_allow_list_allow(mock_app):
    """Should add app to allow-list."""
    from pynintendoparental.enum import SafeLaunchSetting

    from nintendo_mcp.applications import nintendo_set_app_allow_list
    from nintendo_mcp.models import SetAppAllowListInput

    ctx = MagicMock()
    result = await nintendo_set_app_allow_list(
        SetAppAllowListInput(device_id="device-001", application_id="app-001", allow=True), ctx
    )

    mock_app.set_safe_launch_setting.assert_called_once_with(SafeLaunchSetting.ALLOW)
    assert "allow-list" in result
    assert "Test Game" in result


@pytest.mark.asyncio
async def test_set_app_allow_list_remove(mock_app):
    """Should remove app from allow-list."""
    from pynintendoparental.enum import SafeLaunchSetting

    from nintendo_mcp.applications import nintendo_set_app_allow_list
    from nintendo_mcp.models import SetAppAllowListInput

    ctx = MagicMock()
    result = await nintendo_set_app_allow_list(
        SetAppAllowListInput(device_id="device-001", application_id="app-001", allow=False), ctx
    )

    mock_app.set_safe_launch_setting.assert_called_once_with(SafeLaunchSetting.NONE)
    assert "removed" in result


@pytest.mark.asyncio
async def test_set_app_allow_list_app_not_found():
    """Should return error for unknown application ID."""
    from nintendo_mcp.applications import nintendo_set_app_allow_list
    from nintendo_mcp.models import SetAppAllowListInput

    ctx = MagicMock()
    result = await nintendo_set_app_allow_list(
        SetAppAllowListInput(device_id="device-001", application_id="nonexistent", allow=True), ctx
    )
    assert "Error" in result
    assert "not found" in result


@pytest.mark.asyncio
async def test_set_app_allow_list_device_not_found():
    """Should return error for unknown device ID."""
    from nintendo_mcp.applications import nintendo_set_app_allow_list
    from nintendo_mcp.models import SetAppAllowListInput

    ctx = MagicMock()
    result = await nintendo_set_app_allow_list(
        SetAppAllowListInput(device_id="nonexistent", application_id="app-001", allow=True), ctx
    )
    assert "Error" in result
    assert "not found" in result
