"""Tests for device_cache.py — cache I/O and device resolution."""

from unittest.mock import MagicMock

import pytest

from switch_parental_controls.device_cache import (
    devices_from_client,
    load_cache,
    resolve_device_id,
    save_cache,
)


@pytest.fixture()
def cache_path(tmp_path, monkeypatch):
    """Point the cache at a temp directory."""
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "switch-parental-controls" / "devices"


@pytest.fixture()
def mock_client():
    dev = MagicMock()
    dev.device_id = "abc123"
    dev.name = "Switch #1"
    client = MagicMock()
    client.devices = {"abc123": dev}
    return client


# ---------------------------------------------------------------------------
# save_cache / load_cache
# ---------------------------------------------------------------------------


def test_save_and_load_roundtrip(cache_path):
    save_cache({"abc123": "Switch #1"})
    assert load_cache() == {"abc123": "Switch #1"}


def test_load_cache_missing_file(cache_path):
    assert load_cache() == {}


def test_load_cache_corrupt_file(cache_path):
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("not json")
    assert load_cache() == {}


def test_save_cache_creates_parent_dirs(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "deep" / "path"))
    save_cache({"x": "y"})
    assert load_cache() == {"x": "y"}


# ---------------------------------------------------------------------------
# devices_from_client
# ---------------------------------------------------------------------------


def test_devices_from_client(mock_client):
    assert devices_from_client(mock_client) == {"abc123": "Switch #1"}


def test_devices_from_client_multiple():
    dev1 = MagicMock()
    dev1.name = "Kid's Switch"
    dev2 = MagicMock()
    dev2.name = "Living Room Switch"
    client = MagicMock()
    client.devices = {"id1": dev1, "id2": dev2}
    assert devices_from_client(client) == {"id1": "Kid's Switch", "id2": "Living Room Switch"}


# ---------------------------------------------------------------------------
# resolve_device_id
# ---------------------------------------------------------------------------


def test_resolve_by_id(cache_path, mock_client):
    save_cache({"abc123": "Switch #1"})
    assert resolve_device_id(mock_client, "abc123") == "abc123"


def test_resolve_by_exact_name(cache_path, mock_client):
    save_cache({"abc123": "Switch #1"})
    assert resolve_device_id(mock_client, "Switch #1") == "abc123"


def test_resolve_by_name_case_insensitive(cache_path, mock_client):
    save_cache({"abc123": "Switch #1"})
    assert resolve_device_id(mock_client, "switch #1") == "abc123"


def test_resolve_none_single_device(cache_path, mock_client):
    save_cache({"abc123": "Switch #1"})
    assert resolve_device_id(mock_client, None) == "abc123"


def test_resolve_none_auto_populates_cache_from_client(cache_path, mock_client):
    """When cache is empty, resolve() populates it from the client."""
    assert load_cache() == {}
    result = resolve_device_id(mock_client, None)
    assert result == "abc123"
    assert load_cache() == {"abc123": "Switch #1"}


def test_resolve_none_multiple_devices_raises(cache_path):
    save_cache({"id1": "Switch A", "id2": "Switch B"})
    client = MagicMock()
    client.devices = {}
    with pytest.raises(ValueError, match="Multiple devices"):
        resolve_device_id(client, None)


def test_resolve_unknown_name_raises(cache_path, mock_client):
    save_cache({"abc123": "Switch #1"})
    with pytest.raises(ValueError, match="not found"):
        resolve_device_id(mock_client, "does-not-exist")


def test_resolve_empty_cache_no_devices_raises(cache_path):
    client = MagicMock()
    client.devices = {}
    with pytest.raises(ValueError, match="No devices"):
        resolve_device_id(client, None)
