"""Helpers shared by the MCP tool modules."""

import inspect
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Annotated, Any
from zoneinfo import ZoneInfo

from mcp.server.mcpserver import Context
from mcp.server.mcpserver.exceptions import ToolError as InvalidArguments
from pydantic import BaseModel, Field, ValidationError

from switch_parental_controls.models import ResponseFormat
from switch_parental_controls.server import DEFAULT_TIMEZONE, _state, mcp
from switch_parental_controls.utils import ToolError, handle_error, require_client, to_json


def tool_annotations(title: str, *, read_only: bool, idempotent: bool = True, open_world: bool = True) -> dict:
    """Build the MCP tool annotations. None of the tools is destructive."""
    return {
        "title": title,
        "readOnlyHint": read_only,
        "destructiveHint": False,
        "idempotentHint": idempotent,
        "openWorldHint": open_world,
    }


ToolFunction = Callable[[Any, Context], Awaitable[str]]


def _argument(name: str, field) -> inspect.Parameter:
    """The tool argument for one field of an input model, with its description and constraints."""
    annotation = Annotated[(field.annotation, *field.metadata, Field(description=field.description))]
    default = inspect.Parameter.empty if field.is_required() else field.default
    return inspect.Parameter(name, inspect.Parameter.KEYWORD_ONLY, default=default, annotation=annotation)


def model_tool(name: str, model: type[BaseModel], annotations: dict) -> Callable[[ToolFunction], ToolFunction]:
    """Register a `(params, ctx)` function as an MCP tool that takes the fields of `model` as its arguments.

    MCP clients see every field as a top-level argument with its description,
    instead of one `params` object around them. The tool builds the model from
    the arguments, so its validators still run, and passes it on. The function
    itself is returned unchanged for the CLI and the tests.
    """

    def register(fn: ToolFunction) -> ToolFunction:
        async def tool(ctx: Context, **arguments: Any) -> str:
            try:
                params = model(**arguments)
            except ValidationError as e:
                # Rejected like arguments that don't match the schema: the client sees why.
                raise InvalidArguments(str(e)) from e
            return await fn(params, ctx)

        parameters = [_argument(field_name, field) for field_name, field in model.model_fields.items()]
        parameters.append(inspect.Parameter("ctx", inspect.Parameter.KEYWORD_ONLY, annotation=Context))
        tool.__signature__ = inspect.Signature(parameters, return_annotation=str)
        tool.__annotations__ = {parameter.name: parameter.annotation for parameter in parameters} | {"return": str}
        tool.__name__ = fn.__name__
        tool.__doc__ = fn.__doc__
        mcp.add_tool(tool, name=name, annotations=annotations)
        return fn

    return register


def get_client():
    """Return the Nintendo client, or raise ToolError if not authenticated."""
    client = _state.get("client")
    err = require_client(client)
    if err:
        raise ToolError(err)
    return client


def get_device(device_id: str):
    """Return the device with the given ID, or raise ToolError if it doesn't exist."""
    device = get_client().devices.get(device_id)
    if device is None:
        raise ToolError(f"Error: Device '{device_id}' not found. Use switch_list_devices to see available device IDs.")
    return device


def get_timezone() -> ZoneInfo:
    """Return the configured timezone."""
    return ZoneInfo(_state.get("timezone") or DEFAULT_TIMEZONE)


@dataclass(frozen=True)
class DeviceListing:
    """How to list one kind of item (players, applications) of a device.

    `attribute` is both the device attribute holding the items and the key of
    the list in the JSON response. `empty_message` and `heading` are templates
    with a `{name}` placeholder for the device name.
    """

    attribute: str
    empty_message: str
    heading: str
    to_dict: Callable[[Any], dict]
    entry_lines: Callable[[Any], list[str]]


async def list_device_items(listing: DeviceListing, device_id: str, response_format: ResponseFormat) -> str:
    """List the items of a device as markdown or JSON."""
    try:
        device = get_device(device_id)
        await device.update()
        items = list(getattr(device, listing.attribute))

        if not items:
            return listing.empty_message.format(name=device.name)

        if response_format == ResponseFormat.JSON:
            return to_json(
                {
                    "count": len(items),
                    "device_name": device.name,
                    listing.attribute: [listing.to_dict(item) for item in items],
                }
            )

        lines = [listing.heading.format(name=device.name), ""]
        for item in items:
            lines += listing.entry_lines(item)
        return "\n".join(lines)

    except Exception as e:
        return handle_error(e)
