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


def test_bedtime_end_after_nine_rejected():
    with pytest.raises(ValidationError, match="latest bedtime end time is 09:00"):
        SetBedtimeEndInput(device_id="d", hour=9, minute=15)


def test_bedtime_times_match_the_library_bounds():
    """Every time the models accept passes the checks of pynintendoparental."""
    from datetime import time

    from pynintendoparental.device._helpers import validate_bedtime_alarm, validate_bedtime_end

    for model, validate in ((SetBedtimeEndInput, validate_bedtime_end), (SetBedtimeAlarmInput, validate_bedtime_alarm)):
        for hour in range(24):
            for minute in range(60):
                try:
                    model(device_id="d", hour=hour, minute=minute)
                except ValidationError:
                    continue
                validate(time(hour, minute))


def test_clear_cache_month_without_year_rejected():
    with pytest.raises(ValidationError, match="year is required"):
        ClearCacheInput(month=3)
