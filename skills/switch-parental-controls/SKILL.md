---
name: switch-parental-controls
description: >
  Reference skill for operating the switch-parental-controls CLI to manage
  Nintendo Switch parental controls. Use this skill whenever you need to run
  `switch-parental-controls` commands — checking today's or monthly usage,
  listing devices, setting playtime limits, adding extra time, configuring
  bedtime alarms, managing content restrictions, or reviewing player and app
  data. Trigger for any task involving the switch-parental-controls CLI, even
  if the user just says "how much did the kids play today" or "add 30 minutes
  for Emma's Switch" — those map directly to CLI commands covered here.
---

## Overview

`switch-parental-controls` is a CLI (and MCP server) for managing Nintendo Switch parental controls via the Nintendo Parental Controls API. It can read usage data, set playtime limits, configure bedtime alarms, restrict content, and manage per-app allow lists.

**Binary name:** `switch-parental-controls`

**Install:**

```
pip install switch-parental-controls
```

**Run without installing:**

```
uvx switch-parental-controls <command>
```

## Authentication

**Assume the user is already authenticated.** Every command requires a saved session token, and that token is obtained through a one-time interactive login that a human must complete manually — it cannot be automated. Do not attempt to run `login` yourself.

The token is stored at `~/.config/switch-parental-controls/credentials` by default (or `$XDG_CONFIG_HOME/switch-parental-controls/credentials` if `XDG_CONFIG_HOME` is set), or override with the `SWITCH_PARENTAL_CONTROLS_SESSION_TOKEN` environment variable. If any command fails with "Error: Not authenticated", tell the user to run the following command manually in their own terminal and follow the prompts:

```
switch-parental-controls login
```

The login flow requires opening a Nintendo URL in a browser, completing the sign-in, then copying the redirect URL and pasting it back into the running terminal. Once done, the token is saved automatically and all subsequent commands work without further setup.

**Remove saved credentials:**

```
switch-parental-controls logout
```

## Global Options

These flags apply to every command and must be placed **before the subcommand name**, not after it:

```
# correct
switch-parental-controls --timezone America/New_York today-summary

# wrong — will be rejected
switch-parental-controls today-summary --timezone America/New_York
```

| Flag | Env var | Default | Description |
|------|---------|---------|-------------|
| `-t, --timezone TEXT` | `SWITCH_PARENTAL_CONTROLS_TIMEZONE` | `Europe/London` | IANA timezone (e.g. `America/New_York`) |
| `-l, --lang TEXT` | `SWITCH_PARENTAL_CONTROLS_LANG` | `en-GB` | Language code (e.g. `en-US`) |

Setting the env vars avoids having to repeat the flags on every command.

## Devices vs Players

**Device** — the physical Nintendo Switch console. Device names look like `"Switch #1"` or `"Daniel's Switch"`. This is what the `[DEVICE]` argument refers to throughout the CLI.

**Player** — a Nintendo Account profile linked to a device (a person, e.g. "Emma" or "Max"). Players are not devices. Never pass a person's name as the `[DEVICE]` argument.

If the user says "how long did Emma play today", that is a question about a **player**, not a device. Run `today-summary` on the correct device (or without a device argument if there is only one) and read the per-player breakdown from the output. Only use `list-players` / `get-player` when you need raw player metadata (player ID, account details), not for general playtime questions.

## Device Resolution

Most commands accept an optional `[DEVICE]` positional argument. `DEVICE` is the console name or ID — never a person's name. If omitted and the account has exactly one device, it is selected automatically.

`DEVICE` accepts either a **device name** (e.g. `"Switch #1"`) or a **device ID** (e.g. `abc123def456`). Names are resolved via a persistent cache at `~/.config/switch-parental-controls/devices` by default (or `$XDG_CONFIG_HOME/switch-parental-controls/devices` if `XDG_CONFIG_HOME` is set).

Every command populates the cache automatically on first use (from the already-initialized API client — no extra network call). The cache persists across sessions, so you do not need to run `list-devices` before every command. Run it explicitly only when you need to confirm current device names or after adding, removing, or renaming a device:

```
switch-parental-controls list-devices
```

## Output Formats

Most commands support `--format markdown|json`. The default is `markdown` (human-readable). Use `--format json` for machine parsing.

```
switch-parental-controls list-devices --format json
```

---

## Command Reference

### Authentication

#### `login` _(human-only, do not run as an agent)_
Interactive OAuth flow that requires a browser and human input. If the user needs to authenticate, instruct them to run this themselves — you cannot complete it on their behalf.

```
switch-parental-controls login
```

#### `logout`
Remove saved credentials from disk.

```
switch-parental-controls logout
```

---

### Device Information

#### `list-devices`
List all Nintendo Switch devices linked to the account. Overwrites the local device name cache — use this when you need to confirm current device names or after adding, removing, or renaming a device.

```
switch-parental-controls list-devices [--format markdown|json]
```

#### `get-device`
Get detailed status for a specific device.

```
switch-parental-controls get-device [DEVICE] [--format markdown|json]
```

#### `today-summary`
Show today's playtime summary for a device.

```
switch-parental-controls today-summary [DEVICE] [--format markdown|json]
```

#### `monthly-summary`
Show a monthly playtime summary. Defaults to the most recent available month (not necessarily the current one).

```
switch-parental-controls monthly-summary [DEVICE] [--year YEAR --month MONTH] [--format markdown|json]
```

- `--year` and `--month` must be provided together; neither alone is valid.

---

### Playtime Controls

#### `set-playtime-limit`
Set or remove the daily playtime limit.

```
switch-parental-controls set-playtime-limit [DEVICE] --minutes N
switch-parental-controls set-playtime-limit [DEVICE] --no-limit
```

- `--minutes N`: 0–360 minutes
- `--no-limit`: remove the daily limit entirely

#### `add-extra-time`
Add extra playtime for today only (one-time override).

```
switch-parental-controls add-extra-time [DEVICE] MINUTES
```

- `MINUTES`: 1–360

#### `set-timer-mode`
Set whether the playtime limit applies equally every day or can vary per day.

```
switch-parental-controls set-timer-mode [DEVICE] MODE
```

- `MODE`: `DAILY` or `EACH_DAY_OF_THE_WEEK`

#### `set-day-restrictions`
Configure playtime and bedtime rules for a specific day of the week.

```
switch-parental-controls set-day-restrictions [DEVICE] DAY [OPTIONS]
```

**DAY:** `MONDAY` | `TUESDAY` | `WEDNESDAY` | `THURSDAY` | `FRIDAY` | `SATURDAY` | `SUNDAY`

**Playtime options:**

| Flag | Description |
|------|-------------|
| `--playtime-enabled` | Enable playtime limit for this day |
| `--playtime-disabled` | Disable playtime limit for this day |
| `--max-playtime-minutes N` | Max minutes (required when `--playtime-enabled`) |

**Bedtime options:**

| Flag | Description |
|------|-------------|
| `--bedtime-enabled` | Enable bedtime restriction for this day |
| `--bedtime-disabled` | Disable bedtime restriction for this day |
| `--bedtime-alarm-hour H` | Alarm hour, 16–23 (required when `--bedtime-enabled`) |
| `--bedtime-alarm-minute M` | Alarm minute, 0–59 (default: 0) |
| `--bedtime-end-hour H` | End hour, 5–9 (required when `--bedtime-enabled`) |
| `--bedtime-end-minute M` | End minute, 0–59 (default: 0) |

---

### Restriction Controls

#### `set-restriction-mode`
Set what happens when the playtime limit is reached.

```
switch-parental-controls set-restriction-mode [DEVICE] MODE
```

- `MODE`: `FORCED_TERMINATION` (game stops) or `ALARM` (alarm sounds but play continues)

#### `set-content-restriction`
Set the age-based content restriction level.

```
switch-parental-controls set-content-restriction [DEVICE] LEVEL
```

- `LEVEL`: `NONE` | `CHILDREN` | `YOUNG_TEENS` | `OLDER_TEENS` | `CUSTOM`

#### `set-bedtime-alarm`
Set the bedtime alarm time (the hour the Switch locks for the night).

```
switch-parental-controls set-bedtime-alarm [DEVICE] HOUR MINUTE
```

- `HOUR`: 16–23
- `MINUTE`: 0–59
- Use `0 0` to **disable** the bedtime alarm.

#### `set-bedtime-end`
Set the time the Switch unlocks in the morning.

```
switch-parental-controls set-bedtime-end [DEVICE] HOUR MINUTE
```

- `HOUR`: 5–9
- `MINUTE`: 0–59
- Use `0 0` to **disable** the bedtime end time.

---

### Player Management

#### `list-players`
List all players (Nintendo Account profiles) registered on a device.

```
switch-parental-controls list-players [DEVICE] [--format json]
```

#### `get-player`
Get details for a specific player.

```
switch-parental-controls get-player [DEVICE] PLAYER_ID [--format json]
```

---

### Application Management

#### `list-applications`
List all applications (games) with their recorded playtime on a device.

```
switch-parental-controls list-applications [DEVICE] [--format markdown|json]
```

#### `set-app-allow-list`
Add or remove an application from the content restriction allow list. Allow-listed apps can bypass the age-based content restriction and launch regardless of the device's restriction level. Apps not on the allow list remain subject to normal restrictions — they can still launch if their rating is permitted by the active restriction level.

```
switch-parental-controls set-app-allow-list [DEVICE] APP_ID --allow
switch-parental-controls set-app-allow-list [DEVICE] APP_ID --no-allow
```

---

## Common Workflows

### Check today's playtime (all players)

```
switch-parental-controls today-summary
```

### Check how long a specific person played today

Person names ("Emma", "Max") are **players**, not devices. Run `today-summary` and read that player's entry from the output — do not pass the name as `[DEVICE]`:

```
switch-parental-controls today-summary
```

> **Note:** If any command returns "Error: Not authenticated", the user needs to run `switch-parental-controls login` manually — this is an interactive step that cannot be automated.

### Check how much was played in April 2025

```
switch-parental-controls monthly-summary --year 2025 --month 4
```

### Set a 90-minute daily limit

```
switch-parental-controls set-playtime-limit --minutes 90
```

### Add 30 extra minutes today

```
switch-parental-controls add-extra-time 30
```

### Remove the daily limit entirely

```
switch-parental-controls set-playtime-limit --no-limit
```

### Set a 9 PM bedtime, unlocks at 7 AM

```
switch-parental-controls set-bedtime-alarm 21 0
switch-parental-controls set-bedtime-end 7 0
```

### Disable bedtime alarm

```
switch-parental-controls set-bedtime-alarm 0 0
switch-parental-controls set-bedtime-end 0 0
```

### Set per-day rules (weekdays 1h, weekends 2h)

```
switch-parental-controls set-timer-mode EACH_DAY_OF_THE_WEEK
switch-parental-controls set-day-restrictions MONDAY --playtime-enabled --max-playtime-minutes 60 --bedtime-disabled
switch-parental-controls set-day-restrictions TUESDAY --playtime-enabled --max-playtime-minutes 60 --bedtime-disabled
switch-parental-controls set-day-restrictions WEDNESDAY --playtime-enabled --max-playtime-minutes 60 --bedtime-disabled
switch-parental-controls set-day-restrictions THURSDAY --playtime-enabled --max-playtime-minutes 60 --bedtime-disabled
switch-parental-controls set-day-restrictions FRIDAY --playtime-enabled --max-playtime-minutes 60 --bedtime-disabled
switch-parental-controls set-day-restrictions SATURDAY --playtime-enabled --max-playtime-minutes 120 --bedtime-disabled
switch-parental-controls set-day-restrictions SUNDAY --playtime-enabled --max-playtime-minutes 120 --bedtime-disabled
```

### Restrict content to children's titles, allow a specific game

```
switch-parental-controls set-content-restriction CHILDREN
switch-parental-controls list-applications --format json   # find APP_ID
switch-parental-controls set-app-allow-list <APP_ID> --allow
```

### Work with a specific device by name

```
switch-parental-controls today-summary "Switch #2"
switch-parental-controls set-playtime-limit "Switch #2" --minutes 60
```

---

## Constraints & Gotchas

- **Playtime minutes:** 0–360 for limits; 1–360 for extra time.
- **Bedtime alarm hour:** 16–23 (4 PM – 11 PM). Use `0 0` to disable.
- **Bedtime end hour:** 5–9 (5 AM – 9 AM). Use `0 0` to disable.
- **`set-day-restrictions`** always requires both `--playtime-enabled/--playtime-disabled` AND `--bedtime-enabled/--bedtime-disabled` — both flags are required on every call.
- With `--playtime-enabled`, `--max-playtime-minutes` is required; it must not be set with `--playtime-disabled`.
- With `--bedtime-enabled`, both `--bedtime-alarm-hour` and `--bedtime-end-hour` are required; with `--bedtime-disabled`, none of the bedtime value flags may be set (including non-zero minute values).
- **`monthly-summary`** `--year` and `--month` must be provided together.
- **Device name cache** persists across sessions at `~/.config/switch-parental-controls/devices` (or `$XDG_CONFIG_HOME/switch-parental-controls/devices` if `XDG_CONFIG_HOME` is set). Any command populates it automatically on first use if it is missing — no need to run `list-devices` upfront.
- **Auto-select** only works when the account has exactly one device. With multiple devices, always pass `[DEVICE]` explicitly.
- **Content restriction allow list** only matters when a restriction level other than `NONE` is active.
