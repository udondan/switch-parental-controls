"""The tool definitions MCP clients see: flat, described arguments built from the input models."""

import pytest

from switch_parental_controls import server
from switch_parental_controls.models import SetDayRestrictionsInput


async def _tools() -> dict:
    return {tool.name: tool for tool in await server.mcp.list_tools()}


async def test_every_argument_has_a_description():
    for tool in (await _tools()).values():
        for name, schema in tool.input_schema.get("properties", {}).items():
            assert schema.get("description"), f"{tool.name}.{name} has no description"


async def test_arguments_are_the_fields_of_the_input_model():
    schema = (await _tools())["switch_set_day_restrictions"].input_schema
    assert list(schema["properties"]) == list(SetDayRestrictionsInput.model_fields)
    assert sorted(schema["required"]) == ["bedtime_enabled", "day_of_week", "device_id", "playtime_enabled"]
    assert schema["properties"]["bedtime_alarm_hour"]["anyOf"][0]["minimum"] == 16
    assert schema["properties"]["bedtime_alarm_minute"]["default"] == 0


async def test_tool_without_arguments_takes_none():
    schema = (await _tools())["switch_get_login_url"].input_schema
    assert not schema.get("properties")


async def test_call_builds_the_input_model():
    server._state["client"] = None
    result = await server.mcp.call_tool("switch_get_playtime", {"device_id": "device-001"})
    assert "Error: Not authenticated" in str(result)


async def test_call_runs_the_model_validators():
    with pytest.raises(Exception, match="month is required when year is provided"):
        await server.mcp.call_tool("switch_get_playtime", {"device_id": "device-001", "year": 2025})
