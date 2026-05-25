# Nintendo Switch Parental Controls

A [CLI](#cli-usage) and [MCP (Model Context Protocol)](https://modelcontextprotocol.io) server that expose Nintendo Switch Parental Controls as commands and AI-accessible tools. It wraps the [`pynintendoparental`](https://github.com/pantherale0/pynintendoparental) library and allows humans and AI assistants to monitor and manage parental control settings on Nintendo Switch devices.

## Features

- **Authentication**: Interactive Nintendo OAuth login flow, or pre-configured session token
- **Device monitoring**: List devices, view playtime, remaining time, sync status
- **Playtime controls**: Set daily limits, add extra time, configure per-day-of-week schedules
- **Bedtime controls**: Set bedtime alarms and end times
- **Restriction controls**: Set restriction mode (forced termination vs. alarm), content restriction levels
- **Player tracking**: View player profiles and today's app usage
- **Application management**: List apps, manage the allow-list (bypass content restrictions)

## Prerequisites

- [uv](https://docs.astral.sh/uv/) — install once, no Python or clone needed:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## Authentication: Getting Your Nintendo Session Token

The server requires a Nintendo session token to access the Parental Controls API. You can obtain one in two ways:

### Method 1: Interactive MCP Tool (Recommended for first-time setup)

1. Start the MCP server (see below)
2. Ask your AI assistant to call `nintendo_get_login_url`
3. Open the returned URL in your browser
4. Log in with your Nintendo Account
5. On the "Select this person" page, **right-click** the "Select this person" button and copy the link
6. Ask your AI assistant to call `nintendo_complete_login` with the copied URL
7. The tool will return your session token — **save it!**

### Method 2: Manual (if you already have a token)

If you already have a session token, set it as an environment variable:

```bash
export NINTENDO_SESSION_TOKEN="your-token-here"
```

### Saving Your Token

Once you have a session token, add it to your environment so you don't need to log in again:

```bash
# Add to your shell profile (~/.zshrc, ~/.bashrc, etc.)
export NINTENDO_SESSION_TOKEN="your-token-here"

# Or create a .env file (never commit this!)
echo 'NINTENDO_SESSION_TOKEN=your-token-here' >> .env
```

> **Note**: Session tokens can expire. If you get authentication errors, repeat the login flow.

## CLI Usage

The `nintendo` CLI gives you direct terminal access to all parental control features.

### Installation

No clone required — run directly with `uvx`:

```bash
uvx switch-parental-controls --help
```

Or install globally:

```bash
pip install switch-parental-controls
switch-parental-controls --help
```

### Login

```bash
switch-parental-controls login
```

This starts an interactive flow:

1. A Nintendo login URL is printed — open it in your browser
2. Log in with your Nintendo Account
3. Right-click the **"Select this person"** button and copy the link
4. Paste the copied URL at the prompt

On success, your session token is printed. Export it so future commands work:

```bash
export NINTENDO_SESSION_TOKEN="your-token-here"
```

### Global Options

```text
switch-parental-controls [OPTIONS] COMMAND [ARGS]...

Options:
  -t, --timezone TEXT   IANA timezone  [env: NINTENDO_TIMEZONE; default: Europe/London]
  -l, --lang TEXT       Language code  [env: NINTENDO_LANG; default: en-GB]
```

### Commands

**Device info:**

```bash
switch-parental-controls list-devices [--format markdown|json]
switch-parental-controls get-device <device-id> [--format markdown|json]
switch-parental-controls today-summary <device-id> [--format markdown|json]
switch-parental-controls monthly-summary <device-id> [--year YEAR --month MONTH] [--format markdown|json]
```

**Playtime limits:**

```bash
switch-parental-controls set-playtime-limit <device-id> --minutes 120   # set 2-hour limit
switch-parental-controls set-playtime-limit <device-id> --no-limit       # remove limit
switch-parental-controls add-extra-time <device-id> 30                   # add 30 extra minutes today
switch-parental-controls set-timer-mode <device-id> DAILY
switch-parental-controls set-timer-mode <device-id> EACH_DAY_OF_THE_WEEK
```

**Per-day restrictions:**

```bash
# Enable playtime + bedtime on Monday
switch-parental-controls set-day-restrictions <device-id> MONDAY \
  --playtime-enabled --max-playtime-minutes 90 \
  --bedtime-enabled \
  --bedtime-alarm-hour 21 --bedtime-alarm-minute 0 \
  --bedtime-end-hour 7 --bedtime-end-minute 0

# Disable all restrictions on Saturday
switch-parental-controls set-day-restrictions <device-id> SATURDAY \
  --playtime-disabled --bedtime-disabled
```

**Restriction and content controls:**

```bash
switch-parental-controls set-restriction-mode <device-id> FORCED_TERMINATION
switch-parental-controls set-restriction-mode <device-id> ALARM
switch-parental-controls set-content-restriction <device-id> CHILDREN
switch-parental-controls set-bedtime-alarm <device-id> 21 0    # 21:00
switch-parental-controls set-bedtime-alarm <device-id> 0 0     # disable
switch-parental-controls set-bedtime-end <device-id> 7 0       # 07:00
```

**Players and applications:**

```bash
switch-parental-controls list-players <device-id> [--format json]
switch-parental-controls get-player <device-id> <player-id>
switch-parental-controls list-applications <device-id>
switch-parental-controls set-app-allow-list <device-id> <app-id> --allow
switch-parental-controls set-app-allow-list <device-id> <app-id> --no-allow
```

**Start the MCP server:**

```bash
switch-parental-controls mcp
```

## Running the Server

```bash
uvx switch-parental-controls mcp
```

No clone or install required — `uvx` fetches the package from PyPI and runs it in an isolated environment.

### Environment Variables

| Variable                 | Required | Default         | Description                             |
| ------------------------ | -------- | --------------- | --------------------------------------- |
| `NINTENDO_SESSION_TOKEN` | No\*     | —               | Nintendo session token                  |
| `NINTENDO_TIMEZONE`      | No       | `Europe/London` | IANA timezone (e.g. `America/New_York`) |
| `NINTENDO_LANG`          | No       | `en-GB`         | Language code (e.g. `en-US`)            |

\*Required for any tool that accesses Nintendo data, unless you use the interactive login tools.

### MCP Client Configuration

Add to your MCP client configuration (e.g. Claude Desktop `claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "nintendo": {
      "command": "uvx",
      "args": ["switch-parental-controls", "mcp"],
      "env": {
        "NINTENDO_SESSION_TOKEN": "your-token-here",
        "NINTENDO_TIMEZONE": "America/New_York",
        "NINTENDO_LANG": "en-US"
      }
    }
  }
}
```

## Available Tools

### Authentication

| Tool                      | Description                                                   |
| ------------------------- | ------------------------------------------------------------- |
| `nintendo_get_login_url`  | Generate the Nintendo login URL and step-by-step instructions |
| `nintendo_complete_login` | Complete login with the redirect URL from the browser         |

### Devices

| Tool                           | Description                                                 |
| ------------------------------ | ----------------------------------------------------------- |
| `nintendo_list_devices`        | List all Nintendo Switch devices on the account             |
| `nintendo_get_device`          | Get detailed status for a specific device                   |
| `nintendo_get_today_summary`   | Get today's usage summary for a device                      |
| `nintendo_get_monthly_summary` | Get monthly usage summary (optionally for a specific month) |

### Playtime Controls

| Tool                                | Description                                               |
| ----------------------------------- | --------------------------------------------------------- |
| `nintendo_set_daily_playtime_limit` | Set the daily playtime limit (0-360 min, or -1 to remove) |
| `nintendo_add_extra_time`           | Add extra playtime for today                              |
| `nintendo_set_timer_mode`           | Switch between DAILY and EACH_DAY_OF_THE_WEEK modes       |
| `nintendo_set_day_restrictions`     | Set per-day playtime and bedtime restrictions             |

### Restriction Controls

| Tool                                     | Description                              |
| ---------------------------------------- | ---------------------------------------- |
| `nintendo_set_restriction_mode`          | Set FORCED_TERMINATION or ALARM mode     |
| `nintendo_set_content_restriction_level` | Set age-based content restrictions       |
| `nintendo_set_bedtime_alarm`             | Set the bedtime alarm time (16:00-23:00) |
| `nintendo_set_bedtime_end_time`          | Set when bedtime ends (05:00-09:00)      |

### Players

| Tool                    | Description                                    |
| ----------------------- | ---------------------------------------------- |
| `nintendo_list_players` | List all players on a device                   |
| `nintendo_get_player`   | Get player details including apps played today |

### Applications

| Tool                          | Description                                               |
| ----------------------------- | --------------------------------------------------------- |
| `nintendo_list_applications`  | List all tracked applications on a device                 |
| `nintendo_set_app_allow_list` | Add/remove an app from the content restriction allow-list |

## Development

Requires [mise](https://mise.jdx.dev/):

```bash
# Install dependencies
mise run install

# Run tests
mise run test

# Run linter
mise run lint

# Fix lint issues
mise run lint-fix

# Open MCP Inspector (browser UI to test tools interactively)
mise run inspect
```

### MCP Inspector

The `inspect` task launches the [MCP Inspector](https://github.com/modelcontextprotocol/inspector) — a browser-based UI for testing MCP tools interactively without needing a full AI client.

```bash
mise run inspect
```

This opens the inspector connected to the switch_parental_controls server. You can call any tool directly from the UI, which is useful for testing the authentication flow and verifying tool responses.

### Testing with opencode locally

An example opencode config is provided at [`opencode.jsonc.example`](./opencode.jsonc.example). To use it:

```bash
# 1. Copy the example config
cp opencode.jsonc.example opencode.jsonc

# 2. Optionally set NINTENDO_SESSION_TOKEN in opencode.jsonc

# 3. Open opencode in this project directory — it will pick up the local config
opencode
```

The local `opencode.jsonc` is gitignored so your session token stays private.

## CI

Tests run automatically on pull requests via GitHub Actions. See [`.github/workflows/test.yml`](.github/workflows/test.yml).

## License

MIT
