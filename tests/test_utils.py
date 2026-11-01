"""Tests for the formatting and error helpers in utils.py."""

from datetime import time

import pytest

from switch_parental_controls.utils import (
    format_minutes,
    format_time,
    format_timestamp,
    handle_error,
    require_client,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, "disabled"), (time(0, 0), "disabled"), (time(21, 5), "21:05")],
)
def test_format_time(value, expected):
    assert format_time(value) == expected


def test_format_timestamp_none():
    assert format_timestamp(None) == "never"


def test_format_timestamp_valid():
    assert format_timestamp(0).startswith("19")


def test_format_timestamp_invalid():
    assert format_timestamp(float("nan")) == "nan"


@pytest.mark.parametrize(
    ("minutes", "expected"),
    [(None, "no limit"), (-1, "no limit"), (0, "0 minutes"), (60, "1h"), (15, "15m"), (90.0, "1h 30m")],
)
def test_format_minutes(minutes, expected):
    assert format_minutes(minutes) == expected


def _error(name: str, message: str = "") -> Exception:
    return type(name, (Exception,), {})(message)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_error("ClientError", "401 Unauthorized"), "Error: Authentication failed"),
        (_error("ClientError", "403"), "Error: Access denied"),
        (_error("ClientError", "404"), "Error: Resource not found"),
        (_error("ClientError", "429"), "Error: Rate limit exceeded"),
        (_error("ClientError", "Connection timeout"), "Error: Request timed out"),
        (_error("TimeoutError"), "Error: Request timed out"),
        (_error("NoDevicesFoundException"), "Error: No Nintendo Switch devices found"),
        (_error("NotAuthenticatedError"), "Error: Not authenticated"),
        (_error("ValueError", "bad"), "Error: ValueError: bad"),
    ],
)
def test_handle_error(exc, expected):
    assert handle_error(exc).startswith(expected)


def test_require_client():
    assert require_client(None).startswith("Error: Not authenticated")
    assert require_client(object()) is None
