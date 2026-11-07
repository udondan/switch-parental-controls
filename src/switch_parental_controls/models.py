"""Shared Pydantic models and enums for the Nintendo MCP server."""

from enum import StrEnum
from typing import ClassVar

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResponseFormat(StrEnum):
    """Output format for tool responses."""

    MARKDOWN = "markdown"
    JSON = "json"


class DayOfWeek(StrEnum):
    """Days of the week as used by the Nintendo API."""

    MONDAY = "MONDAY"
    TUESDAY = "TUESDAY"
    WEDNESDAY = "WEDNESDAY"
    THURSDAY = "THURSDAY"
    FRIDAY = "FRIDAY"
    SATURDAY = "SATURDAY"
    SUNDAY = "SUNDAY"


_STRICT_CONFIG = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")
RESPONSE_FORMAT_DESCRIPTION = "Output format: 'markdown' for human-readable or 'json' for machine-readable."
DEVICE_ID_DESCRIPTION = "The unique device ID. Use switch_list_devices to find it."


def _response_format_field():
    return Field(default=ResponseFormat.MARKDOWN, description=RESPONSE_FORMAT_DESCRIPTION)


class _DeviceModel(BaseModel):
    """Base for input models that take a device ID."""

    model_config = _STRICT_CONFIG

    device_id: str = Field(..., description=DEVICE_ID_DESCRIPTION)


class DeviceInput(_DeviceModel):
    """Input model requiring a device ID."""

    device_id: str = Field(
        ...,
        description="The unique device ID (e.g. 'abc123'). Use switch_list_devices to find it.",
    )
    response_format: ResponseFormat = _response_format_field()


class DeviceOnlyInput(_DeviceModel):
    """Input model requiring only a device ID (no response format)."""


class ListDevicesInput(BaseModel):
    """Input model for listing devices."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    response_format: ResponseFormat = _response_format_field()


class MonthlySummaryInput(_DeviceModel):
    """Input model for monthly summary queries."""

    year: int | None = Field(
        default=None,
        description="Year for the summary (e.g. 2024). If omitted, returns the most recent available summary.",
        ge=2017,
        le=2100,
    )
    month: int | None = Field(
        default=None,
        description="Month for the summary (1-12). Required if year is provided; must be omitted if year is omitted.",
        ge=1,
        le=12,
    )
    response_format: ResponseFormat = _response_format_field()
    player_id: str | None = Field(
        default=None,
        description="Filter results to a specific player ID. Use switch_list_players to find player IDs.",
    )
    skip_cache: bool = Field(
        default=False,
        description=(
            "Skip reading from and writing to the local cache. "
            "Always fetches fresh data from the Nintendo API. "
            "Useful when data looks stale or unexpected."
        ),
    )

    @model_validator(mode="after")
    def validate_year_month(self) -> "MonthlySummaryInput":
        if self.year is not None and self.month is None:
            raise ValueError("month is required when year is provided")
        if self.month is not None and self.year is None:
            raise ValueError("year is required when month is provided")
        return self


class PlaytimeInput(MonthlySummaryInput):
    """Input model for playtime queries, extending monthly summary with a day filter."""

    year: int | None = Field(
        default=None,
        description="Year for the breakdown (e.g. 2024). If omitted, returns the current month's live data.",
        ge=2017,
        le=2100,
    )
    month: int | None = Field(
        default=None,
        description="Month for the breakdown (1-12). Required if year is provided; must be omitted if year is omitted.",
        ge=1,
        le=12,
    )
    day: int | None = Field(
        default=None,
        description="Filter results to a specific day (1-31). Requires year and month to be set.",
        ge=1,
        le=31,
    )

    @model_validator(mode="after")
    def validate_day(self) -> "PlaytimeInput":
        if self.day is not None and (self.year is None or self.month is None):
            raise ValueError("year and month are required when day is provided")
        return self


class SetPlaytimeLimitInput(_DeviceModel):
    """Input model for setting the daily playtime limit."""

    minutes: int = Field(
        ...,
        description="Daily playtime limit in minutes (0-360). Use -1 to remove the limit entirely.",
        ge=-1,
        le=360,
    )


class AddExtraTimeInput(_DeviceModel):
    """Input model for adding extra playtime."""

    minutes: int = Field(
        ...,
        description="Number of extra minutes to add for today (must be positive).",
        ge=1,
        le=360,
    )


class SetTimerModeInput(_DeviceModel):
    """Input model for setting the timer mode."""

    mode: str = Field(
        ...,
        description="Timer mode: 'DAILY' for a single limit for all days, or 'EACH_DAY_OF_THE_WEEK' for per-day limits.",  # noqa: E501
        pattern="^(DAILY|EACH_DAY_OF_THE_WEEK)$",
    )


class SetDayRestrictionsInput(_DeviceModel):
    """Input model for setting per-day-of-week restrictions."""

    day_of_week: DayOfWeek = Field(..., description="Day of the week to configure (e.g. 'MONDAY').")
    playtime_enabled: bool = Field(..., description="Whether to enable a playtime limit for this day.")
    max_playtime_minutes: int | None = Field(
        default=None,
        description="Maximum playtime in minutes for this day (0-360). Required if playtime_enabled is true.",
        ge=0,
        le=360,
    )
    bedtime_enabled: bool = Field(..., description="Whether to enable bedtime restrictions for this day.")
    bedtime_alarm_hour: int | None = Field(
        default=None,
        description="Hour for the bedtime alarm (16-23). Required if bedtime_enabled is true.",
        ge=16,
        le=23,
    )
    bedtime_alarm_minute: int | None = Field(
        default=0,
        description="Minute for the bedtime alarm (0-59).",
        ge=0,
        le=59,
    )
    bedtime_end_hour: int | None = Field(
        default=None,
        description="Hour when bedtime ends / device can be used again (5-9). Required if bedtime_enabled is true.",
        ge=5,
        le=9,
    )
    bedtime_end_minute: int | None = Field(
        default=0,
        description="Minute when bedtime ends (0-59).",
        ge=0,
        le=59,
    )

    def _has_bedtime_values(self) -> bool:
        """True if any bedtime field is set to something other than its default."""
        hours_set = self.bedtime_alarm_hour is not None or self.bedtime_end_hour is not None
        return hours_set or bool(self.bedtime_alarm_minute) or bool(self.bedtime_end_minute)

    @model_validator(mode="after")
    def validate_playtime_and_bedtime(self) -> "SetDayRestrictionsInput":
        if self.playtime_enabled and self.max_playtime_minutes is None:
            raise ValueError("max_playtime_minutes is required when playtime_enabled is true")
        if not self.playtime_enabled and self.max_playtime_minutes is not None:
            raise ValueError("max_playtime_minutes must not be set when playtime_enabled is false")
        if self.bedtime_enabled and None in (self.bedtime_alarm_hour, self.bedtime_end_hour):
            raise ValueError("bedtime_alarm_hour and bedtime_end_hour are required when bedtime_enabled is true")
        if not self.bedtime_enabled and self._has_bedtime_values():
            raise ValueError("bedtime fields must not be set when bedtime_enabled is false")
        return self


class SetRestrictionModeInput(_DeviceModel):
    """Input model for setting the restriction mode."""

    mode: str = Field(
        ...,
        description=(
            "Restriction mode: 'FORCED_TERMINATION' to suspend software when playtime limit is reached, "
            "or 'ALARM' to only show an alarm without suspending."
        ),
        pattern="^(FORCED_TERMINATION|ALARM)$",
    )


class SetContentRestrictionInput(_DeviceModel):
    """Input model for setting the content restriction level."""

    level: str = Field(
        ...,
        description=(
            "Content restriction level: 'NONE' (no restriction), 'CHILDREN' (young child), "
            "'YOUNG_TEENS', 'OLDER_TEENS' (teen), or 'CUSTOM'."
        ),
        pattern="^(NONE|CHILDREN|YOUNG_TEENS|OLDER_TEENS|CUSTOM)$",
    )


def _hour_field(description: str, max_hour: int):
    return Field(..., description=description, ge=0, le=max_hour)


def _minute_field(description: str):
    return Field(default=0, description=description, ge=0, le=59)


class _BedtimeTimeInput(_DeviceModel):
    """Base for setting a bedtime time. 00:00 disables the setting."""

    setting_name: ClassVar[str]
    hour_label: ClassVar[str]
    valid_hours: ClassVar[range]

    hour: int
    minute: int

    @model_validator(mode="after")
    def validate_time(self):
        if self.hour == 0 and self.minute != 0:
            raise ValueError(f"Use hour=0, minute=0 to disable the {self.setting_name}")
        if self.hour != 0 and self.hour not in self.valid_hours:
            first, last = self.valid_hours[0], self.valid_hours[-1]
            raise ValueError(f"{self.hour_label} must be between {first} and {last}, or 0 to disable")
        return self


class SetBedtimeAlarmInput(_BedtimeTimeInput):
    """Input model for setting the bedtime alarm."""

    hour: int = _hour_field("Hour for the bedtime alarm (16-23). Use 0 with minute=0 to disable the alarm.", 23)
    minute: int = _minute_field("Minute for the bedtime alarm (0-59).")

    setting_name: ClassVar[str] = "bedtime alarm"
    hour_label: ClassVar[str] = "Bedtime alarm hour"
    valid_hours: ClassVar[range] = range(16, 24)


class SetBedtimeEndInput(_BedtimeTimeInput):
    """Input model for setting the bedtime end time."""

    hour: int = _hour_field(
        "Hour when bedtime ends and the device can be used again (5-9). Use 0 with minute=0 to disable.", 9
    )
    minute: int = _minute_field("Minute when bedtime ends (0-59).")

    setting_name: ClassVar[str] = "bedtime end time"
    hour_label: ClassVar[str] = "Bedtime end hour"
    valid_hours: ClassVar[range] = range(5, 10)


class PlayerInput(_DeviceModel):
    """Input model for player queries."""

    player_id: str = Field(..., description="The unique player ID. Use switch_list_players to find it.")
    response_format: ResponseFormat = _response_format_field()


class SetAppAllowListInput(_DeviceModel):
    """Input model for setting an application's allow-list status."""

    application_id: str = Field(
        ...,
        description="The unique application ID. Use switch_list_applications to find it.",
    )
    allow: bool = Field(
        ...,
        description=(
            "True to add the application to the allow list (bypasses content restrictions). "
            "False to remove it from the allow list."
        ),
    )


class ClearCacheInput(BaseModel):
    """Input model for clearing the historic data cache."""

    model_config = _STRICT_CONFIG

    device_id: str | None = Field(
        default=None,
        description="Limit clearing to this device ID. Omit to clear cache for all devices.",
    )
    year: int | None = Field(
        default=None,
        description="Limit clearing to this year. Omit to clear all years.",
        ge=2017,
        le=2100,
    )
    month: int | None = Field(
        default=None,
        description="Limit clearing to this month (1-12). Requires year to be set.",
        ge=1,
        le=12,
    )

    @model_validator(mode="after")
    def validate_year_month(self) -> "ClearCacheInput":
        if self.month is not None and self.year is None:
            raise ValueError("year is required when month is provided")
        return self


class CompleteLoginInput(BaseModel):
    """Input model for completing the Nintendo login flow."""

    model_config = _STRICT_CONFIG

    redirect_url: str = Field(
        ...,
        description=(
            "The URL you were redirected to after clicking 'Select this person' on the Nintendo login page. "
            "It starts with 'npf71b963c1b7b6d119://' or similar."
        ),
        min_length=10,
    )
