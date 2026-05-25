"""Device list cache for the CLI.

Stores {device_id: device_name} in ~/.config/switch-parental-controls/devices so
commands that require a device ID can:
  - Accept a device name as well as an ID.
  - Auto-select the device when there is only one on the account.
  - Avoid an extra API round-trip on every invocation.

list-devices always overwrites the cache. All other device commands populate it
lazily on first use (from the already-initialized client, no extra API call).
"""

import json
import os
from pathlib import Path


def _cache_path() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / "switch-parental-controls" / "devices"


def load_cache() -> dict[str, str]:
    """Return {device_id: device_name} from the cache file, or {} if absent/corrupt."""
    try:
        return json.loads(_cache_path().read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_cache(devices: dict[str, str]) -> None:
    """Write {device_id: device_name} to the cache file."""
    path = _cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(devices, indent=2) + "\n")


def devices_from_client(client) -> dict[str, str]:
    """Extract {device_id: device_name} from an initialized NintendoParental client."""
    return {dev_id: dev.name for dev_id, dev in client.devices.items()}


def resolve_device_id(client, name_or_id: str | None) -> str:
    """Return a device_id from a name, ID, or None (auto-select if single device).

    Uses the cache first; if the cache is empty it populates it from the already-
    initialized client (no extra API call — create_client already called update()).

    Raises ValueError with a human-readable message if resolution fails.
    """
    cache = load_cache()

    if not cache:
        cache = devices_from_client(client)
        if cache:
            save_cache(cache)

    def _candidates() -> str:
        return ", ".join(f"'{name}' ({did})" for did, name in cache.items())

    if name_or_id is not None:
        # Exact ID match
        if name_or_id in cache:
            return name_or_id
        # Case-insensitive name match
        lower = name_or_id.lower()
        for dev_id, dev_name in cache.items():
            if dev_name.lower() == lower:
                return dev_id
        raise ValueError(f"Device '{name_or_id}' not found. Available: {_candidates()}")

    # No device specified — auto-select if unambiguous
    if len(cache) == 0:
        raise ValueError("No devices found on this account.")
    if len(cache) == 1:
        return next(iter(cache))
    raise ValueError(f"Multiple devices found — pass a name or ID. Available: {_candidates()}")
