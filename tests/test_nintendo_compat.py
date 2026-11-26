"""Tests for the pynintendoparental app version workaround."""

from unittest.mock import MagicMock

import pytest
from pynintendoparental import api, const

from switch_parental_controls.nintendo_compat import APP_BUILD, APP_VERSION, patch_app_version


@pytest.fixture
def upstream_constants(monkeypatch):
    """Reset the patched constants to given upstream values; monkeypatch restores them afterwards."""

    def set_version(version: str, build: str):
        user_agent = f"moon_ANDROID/{version} ({const.MOBILE_APP_PKG}; build:{build}; {const.OS_STR})"
        for module in (api, const):
            monkeypatch.setattr(module, "MOBILE_APP_VERSION", version)
            monkeypatch.setattr(module, "MOBILE_APP_BUILD", build)
            monkeypatch.setattr(module, "USER_AGENT", user_agent)

    return set_version


def _headers() -> dict:
    return api.Api(MagicMock(access_token="token"), "Europe/Berlin", "de-DE")._headers


def test_package_import_applies_patch():
    headers = _headers()
    assert headers["X-Moon-App-Display-Version"] == APP_VERSION
    assert headers["X-Moon-App-Internal-Version"] == APP_BUILD


def test_patches_outdated_version(upstream_constants):
    upstream_constants("2.6.0", "700")

    assert patch_app_version() is True

    headers = _headers()
    assert headers["X-Moon-App-Display-Version"] == "2.7.0"
    assert headers["X-Moon-App-Internal-Version"] == "740"
    assert headers["User-Agent"] == f"moon_ANDROID/2.7.0 ({const.MOBILE_APP_PKG}; build:740; {const.OS_STR})"


@pytest.mark.parametrize(("version", "build"), [("2.7.0", "740"), ("2.8.0", "800"), ("10.0.0", "1")])
def test_keeps_same_or_newer_upstream_version(upstream_constants, version, build):
    upstream_constants(version, build)

    assert patch_app_version() is False

    headers = _headers()
    assert headers["X-Moon-App-Display-Version"] == version
    assert headers["X-Moon-App-Internal-Version"] == build
