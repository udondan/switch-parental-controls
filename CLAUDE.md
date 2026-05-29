# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

All commands use [mise](https://mise.jdx.dev/) as the task runner.

```bash
mise run install          # Create .venv and install all dependencies
mise run test             # Run unit tests (excludes integration tests)
mise run test-integration # Run integration tests against the real Nintendo API
mise run lint             # Run ruff linter
mise run lint-fix         # Run ruff and auto-fix issues
mise run run              # Start the MCP server
mise run inspect          # Open MCP Inspector (browser UI)
```

To run a single test:

```bash
pytest tests/test_devices.py::test_specific_name -v
pytest tests/test_cli.py -k "test_list_devices" -v
```

## Architecture

This is a dual-mode project: the same logic is exposed as both a **Click CLI** and a **FastMCP server** for AI assistant use.

### Core Data Flow

1. `cli.py` or `server.py` receives a command/tool call
2. Inputs are validated via Pydantic models in `models.py`
3. `switch_client()` context manager in `client.py` creates the `NintendoParental` client and an `aiohttp` session
4. Business logic in `devices.py`, `players.py`, `applications.py`, `auth.py` calls the underlying library
5. Results are returned as formatted markdown strings (or JSON if `response_format="json"`)

### Key Modules

| Module | Role |
| --- | --- |
| `server.py` | FastMCP server setup, lifespan, and tool imports (tools must be imported *after* `mcp` is initialized) |
| `cli.py` | Click CLI; each subcommand delegates to the same functions used by MCP tools |
| `client.py` | `switch_client()` async context manager for creating and tearing down the aiohttp session and Nintendo client |
| `models.py` | Pydantic input models with strict validation (`extra="forbid"`) |
| `device_cache.py` | Resolves device names→IDs; caches locally to avoid repeated API calls |
| `data_cache.py` | Caches monthly summary responses; always re-fetches current month |
| `credentials.py` | XDG-compliant token storage under `~/.config/switch-parental-controls/` |
| `utils.py` | `handle_error()` for consistent error messages; `to_json()` for pretty-print JSON |

### Shared State

Both CLI and MCP tools share a `_state` dict (in `server.py`) holding:

- `client`: Initialized `NintendoParental` instance
- `http_session`: Active `aiohttp.ClientSession`
- `timezone`, `lang`: Locale settings from env vars
- `pending_auth`: Authenticator object during OAuth flow

### Tool Registration Pattern

MCP tools are registered via `@mcp.tool()` decorators in their respective modules. They are imported in `server.py` after `mcp` is initialized — importing before initialization would break decorator registration.

### Device Resolution

Devices can be specified by ID or name (case-insensitive). If only one device exists, it auto-selects. Resolution goes through `resolve_device_id()` which reads from the local device cache.

## Testing Patterns

Every new feature or change must include both unit tests and integration tests — not one or the other. CI runs both suites with real Nintendo API credentials, so integration tests are treated as first-class and must pass before merging.

- All async tests use `asyncio_mode = "auto"` (configured in `pyproject.toml`)
- Shared mock factories (`make_mock_device`, `make_mock_client`) live in `conftest.py`
- Mock the `NintendoParental` client at module level; patch `switch_client` to return `(mock_client, mock_session)`
- Integration tests live in `tests/test_integration.py` and are marked `@pytest.mark.integration`

## Keeping Docs and the Skill in Sync

When adding or changing any feature:

1. **README.md** — Update it to reflect the new or changed behavior. This is the user-facing reference.

2. **CLI skill** — If the feature is exposed through the CLI, update the skill file at `skills/switch-parental-controls/SKILL.md` (inside this repository). Add a description, usage instructions, and concrete examples for the new command or flag.

   > **Important:** Always edit `skills/switch-parental-controls/SKILL.md` inside this project. Never edit the globally installed skill in `~/.claude/skills/` — that file is a copy and will be overwritten. The project-local skill is the source of truth.

## Environment Variables

| Variable | Default | Purpose |
| --- | --- | --- |
| `SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN` | — | Nintendo session token |
| `SWITCH_PARENTAL_CONTROLS_TIMEZONE` | `Europe/London` | IANA timezone |
| `SWITCH_PARENTAL_CONTROLS_LANG` | `en-GB` | Language code |
| `XDG_CONFIG_HOME` | `~/.config` | Base dir for credentials and cache |
