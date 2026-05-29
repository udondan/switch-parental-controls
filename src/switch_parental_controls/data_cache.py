"""Cache for historic monthly play data.

Stores raw get_monthly_summary() API responses on disk so past-month data
(which never changes) does not require a network call on subsequent requests.

Cache layout:
    ~/.config/switch-parental-controls/cache/{device_id}/{YYYY}-{MM}.json

Data for the current calendar month is never cached.
When year/month are not explicitly provided by the caller, caching is also
skipped — the implicit "most recent completed month" would require parsing the
response to determine the actual month, adding complexity with little benefit.
"""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


def _cache_dir() -> Path:
    config_home = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
    return config_home / "switch-parental-controls" / "cache"


def _cache_path(device_id: str, year: int, month: int) -> Path:
    return _cache_dir() / device_id / f"{year}-{month:02d}.json"


def is_current_month(year: int, month: int, tz: ZoneInfo) -> bool:
    """Return True if (year, month) is the current calendar month in tz."""
    now = datetime.now(tz)
    return year == now.year and month == now.month


def load_data_cache(device_id: str, year: int, month: int) -> dict | None:
    """Return the cached monthly summary dict, or None if absent/corrupt."""
    try:
        data = json.loads(_cache_path(device_id, year, month).read_text())
        if isinstance(data, dict):
            return data
        return None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def save_data_cache(device_id: str, year: int, month: int, data: dict) -> None:
    """Write the monthly summary dict to the cache (best-effort; silently ignored on failure)."""
    try:
        path = _cache_path(device_id, year, month)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")
    except OSError:
        pass


def clear_data_cache(
    device_id: str | None = None,
    year: int | None = None,
    month: int | None = None,
) -> int:
    """Delete cached files matching the given filters. Returns count of files deleted.

    With all arguments None, clears the entire cache.
    """
    base = _cache_dir()
    if not base.exists():
        return 0

    deleted = 0

    if device_id is not None:
        device_dirs = [base / device_id]
    else:
        try:
            device_dirs = [p for p in base.iterdir() if p.is_dir()]
        except OSError:
            return 0

    for device_dir in device_dirs:
        if not device_dir.is_dir():
            continue
        if year is not None and month is not None:
            candidates = [device_dir / f"{year}-{month:02d}.json"]
        elif year is not None:
            candidates = list(device_dir.glob(f"{year}-??.json"))
        else:
            candidates = list(device_dir.glob("????-??.json"))

        for f in candidates:
            try:
                f.unlink()
                deleted += 1
            except OSError:
                pass

        # Remove empty device directory
        try:
            if not any(device_dir.iterdir()):
                device_dir.rmdir()
        except OSError:
            pass

    return deleted
