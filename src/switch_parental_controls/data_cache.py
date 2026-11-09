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
from contextlib import suppress
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
    with suppress(OSError):
        path = _cache_path(device_id, year, month)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2) + "\n")


def _device_dirs(base: Path, device_id: str | None) -> list[Path]:
    """Cache directories of the given device, or of all devices."""
    if device_id is not None:
        return [base / device_id]
    try:
        return [p for p in base.iterdir() if p.is_dir()]
    except OSError:
        return []


def _cached_files(device_dir: Path, year: int | None, month: int | None) -> list[Path]:
    """Cache files of a device directory matching the year/month filter."""
    if year is not None and month is not None:
        return [device_dir / f"{year}-{month:02d}.json"]
    if year is not None:
        return list(device_dir.glob(f"{year}-??.json"))
    return list(device_dir.glob("????-??.json"))


def _delete_files(files: list[Path]) -> int:
    """Delete the files and return how many were deleted."""
    deleted = 0
    for f in files:
        with suppress(OSError):
            f.unlink()
            deleted += 1
    return deleted


def _remove_if_empty(directory: Path) -> None:
    with suppress(OSError):
        if not any(directory.iterdir()):
            directory.rmdir()


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
    for device_dir in _device_dirs(base, device_id):
        if device_dir.is_dir():
            deleted += _delete_files(_cached_files(device_dir, year, month))
            _remove_if_empty(device_dir)
    return deleted


def cleared_message(count: int) -> str:
    """Result message for clear_data_cache()."""
    if count == 0:
        return "No cached files found matching the given filters."
    return f"✓ Cleared {count} cached file{'s' if count != 1 else ''}."
