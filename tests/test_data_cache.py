"""Tests for historic data cache module."""

import json
from zoneinfo import ZoneInfo

import pytest

from switch_parental_controls.data_cache import (
    clear_data_cache,
    is_current_month,
    load_data_cache,
    save_data_cache,
)


@pytest.fixture(autouse=True)
def isolate_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))


# --- is_current_month ---


def test_is_current_month_true():
    """Should return True for the current calendar month."""
    from datetime import datetime
    from unittest.mock import patch

    tz = ZoneInfo("Europe/London")
    with patch("switch_parental_controls.data_cache.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 15, tzinfo=tz)
        assert is_current_month(2026, 5, tz) is True


def test_is_current_month_false_past():
    """Should return False for a past month."""
    from datetime import datetime
    from unittest.mock import patch

    tz = ZoneInfo("Europe/London")
    with patch("switch_parental_controls.data_cache.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 15, tzinfo=tz)
        assert is_current_month(2026, 4, tz) is False


def test_is_current_month_false_future():
    """Should return False for a future month."""
    from datetime import datetime
    from unittest.mock import patch

    tz = ZoneInfo("Europe/London")
    with patch("switch_parental_controls.data_cache.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 15, tzinfo=tz)
        assert is_current_month(2026, 6, tz) is False


def test_is_current_month_different_year():
    """Should return False when year differs."""
    from datetime import datetime
    from unittest.mock import patch

    tz = ZoneInfo("Europe/London")
    with patch("switch_parental_controls.data_cache.datetime") as mock_dt:
        mock_dt.now.return_value = datetime(2026, 5, 15, tzinfo=tz)
        assert is_current_month(2025, 5, tz) is False


# --- save_data_cache / load_data_cache round-trip ---


def test_save_and_load_roundtrip():
    """Should persist and restore the cached dict."""
    data = {"overall": {"dailyStats": [{"date": "2026-04-01", "totalTime": 600}]}}
    save_data_cache("device-001", 2026, 4, data)
    loaded = load_data_cache("device-001", 2026, 4)
    assert loaded == data


def test_load_cache_miss():
    """Should return None when no cache file exists."""
    result = load_data_cache("device-001", 2026, 3)
    assert result is None


def test_load_cache_corrupt_json(tmp_path, monkeypatch):
    """Should return None when the cache file contains invalid JSON."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "switch-parental-controls" / "cache" / "device-001" / "2026-04.json"
    path.parent.mkdir(parents=True)
    path.write_text("not json")
    assert load_data_cache("device-001", 2026, 4) is None


def test_load_cache_non_dict_json(tmp_path, monkeypatch):
    """Should return None when JSON is valid but not a dict."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    path = tmp_path / "switch-parental-controls" / "cache" / "device-001" / "2026-04.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps([1, 2, 3]))
    assert load_data_cache("device-001", 2026, 4) is None


def test_save_creates_parent_dirs(tmp_path, monkeypatch):
    """Should create intermediate directories automatically."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    save_data_cache("new-device", 2025, 12, {"key": "val"})
    path = tmp_path / "switch-parental-controls" / "cache" / "new-device" / "2025-12.json"
    assert path.exists()


# --- clear_data_cache ---


def _populate(device_id, entries):
    for year, month in entries:
        save_data_cache(device_id, year, month, {"dummy": True})


def test_clear_all():
    """Should delete all cached files and return correct count."""
    _populate("dev-a", [(2026, 1), (2026, 2)])
    _populate("dev-b", [(2026, 3)])
    n = clear_data_cache()
    assert n == 3
    assert load_data_cache("dev-a", 2026, 1) is None
    assert load_data_cache("dev-b", 2026, 3) is None


def test_clear_by_device():
    """Should only delete files for the specified device."""
    _populate("dev-a", [(2026, 1), (2026, 2)])
    _populate("dev-b", [(2026, 1)])
    n = clear_data_cache(device_id="dev-a")
    assert n == 2
    assert load_data_cache("dev-a", 2026, 1) is None
    assert load_data_cache("dev-b", 2026, 1) is not None


def test_clear_by_year():
    """Should only delete files for the specified year."""
    _populate("dev-a", [(2025, 12), (2026, 1)])
    n = clear_data_cache(year=2025)
    assert n == 1
    assert load_data_cache("dev-a", 2025, 12) is None
    assert load_data_cache("dev-a", 2026, 1) is not None


def test_clear_by_year_and_month():
    """Should only delete the file for the exact year+month."""
    _populate("dev-a", [(2026, 1), (2026, 2)])
    n = clear_data_cache(year=2026, month=1)
    assert n == 1
    assert load_data_cache("dev-a", 2026, 1) is None
    assert load_data_cache("dev-a", 2026, 2) is not None


def test_clear_by_device_and_month():
    """Should filter by both device and year+month."""
    _populate("dev-a", [(2026, 1)])
    _populate("dev-b", [(2026, 1)])
    n = clear_data_cache(device_id="dev-a", year=2026, month=1)
    assert n == 1
    assert load_data_cache("dev-a", 2026, 1) is None
    assert load_data_cache("dev-b", 2026, 1) is not None


def test_clear_empty_cache():
    """Should return 0 when no cache exists."""
    assert clear_data_cache() == 0


def test_clear_no_match():
    """Should return 0 when filters match nothing."""
    _populate("dev-a", [(2026, 4)])
    assert clear_data_cache(year=2025) == 0


def test_clear_removes_empty_device_dir(tmp_path, monkeypatch):
    """Should remove device directory when it becomes empty after clearing."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    _populate("dev-a", [(2026, 1)])
    clear_data_cache(device_id="dev-a")
    device_dir = tmp_path / "switch-parental-controls" / "cache" / "dev-a"
    assert not device_dir.exists()
