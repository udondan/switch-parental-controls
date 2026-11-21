"""Tests for input validation in models.py."""

import pytest
from pydantic import ValidationError

from switch_parental_controls.models import ClearCacheInput, SetBedtimeAlarmInput, SetBedtimeEndInput


def test_bedtime_alarm_disabled_with_minute_rejected():
    with pytest.raises(ValidationError, match="hour=0, minute=0 to disable the bedtime alarm"):
        SetBedtimeAlarmInput(device_id="d", hour=0, minute=30)


def test_bedtime_end_disabled_with_minute_rejected():
    with pytest.raises(ValidationError, match="hour=0, minute=0 to disable the bedtime end time"):
        SetBedtimeEndInput(device_id="d", hour=0, minute=30)


def test_bedtime_end_hour_out_of_range_rejected():
    with pytest.raises(ValidationError, match="between 5 and 9"):
        SetBedtimeEndInput(device_id="d", hour=3, minute=0)


def test_bedtime_end_valid():
    assert SetBedtimeEndInput(device_id="d", hour=0, minute=0).hour == 0
    assert SetBedtimeEndInput(device_id="d", hour=7, minute=30).minute == 30


def test_clear_cache_month_without_year_rejected():
    with pytest.raises(ValidationError, match="year is required"):
        ClearCacheInput(month=3)
