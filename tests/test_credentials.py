"""Tests for the credentials file in credentials.py."""

import os
import stat
from unittest.mock import patch

import pytest

from switch_parental_controls.credentials import delete_token, load_token, save_token


@pytest.fixture(autouse=True)
def credentials_path(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    return tmp_path / "switch-parental-controls" / "credentials"


def test_load_token_missing():
    assert load_token() is None


def test_load_token_empty(credentials_path):
    credentials_path.parent.mkdir(parents=True)
    credentials_path.write_text("\n")
    assert load_token() is None


def test_save_and_load_token(credentials_path):
    assert save_token("secret") == credentials_path
    assert credentials_path.read_text() == "secret\n"
    assert stat.S_IMODE(credentials_path.stat().st_mode) == 0o600
    assert load_token() == "secret"


def test_save_token_falls_back_to_plain_write(credentials_path):
    with patch("switch_parental_controls.credentials.os.open", side_effect=OSError("unsupported")):
        save_token("secret")
    assert credentials_path.read_text() == "secret\n"


def test_save_token_overwrites(credentials_path):
    save_token("first-token")
    save_token("second")
    assert load_token() == "second"


def test_delete_token(credentials_path):
    save_token("secret")
    assert delete_token() is True
    assert not credentials_path.exists()


def test_delete_token_missing():
    assert delete_token() is False


def test_delete_token_other_error(credentials_path):
    credentials_path.mkdir(parents=True)
    with pytest.raises(OSError):
        delete_token()
    assert os.path.isdir(credentials_path)
