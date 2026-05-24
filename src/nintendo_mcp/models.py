"""Shared Pydantic models and enums for the Nintendo MCP server."""

from enum import StrEnum

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


class DeviceInput(BaseModel):
    """Input model requiring a device ID."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(
        ...,
        description="The unique device ID (e.g. 'abc123'). Use nintendo_list_devices to find it.",
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable.",
    )


class DeviceOnlyInput(BaseModel):
    """Input model requiring only a device ID (no response format)."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")


class ListDevicesInput(BaseModel):
    """Input model for listing devices."""

    model_config = ConfigDict(validate_assignment=True, extra="forbid")

    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable.",
    )


class MonthlySummaryInput(BaseModel):
    """Input model for monthly summary queries."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    year: int | None = Field(
        default=None,
        description="Year for the summary (e.g. 2024). If omitted, returns the most recent available summary.",
        ge=2017,
        le=2100,
    )
    month: int | None = Field(
        default=None,
        description="Month for the summary (1-12). Required if year is provided.",
        ge=1,
        le=12,
    )
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable.",
    )

    @model_validator(mode="after")
    def validate_year_month(self) -> "MonthlySummaryInput":
        if self.year is not None and self.month is None:
            raise ValueError("month is required when year is provided")
        return self


class SetPlaytimeLimitInput(BaseModel):
    """Input model for setting the daily playtime limit."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    minutes: int = Field(
        ...,
        description="Daily playtime limit in minutes (0-360). Use -1 to remove the limit entirely.",
        ge=-1,
        le=360,
    )


class AddExtraTimeInput(BaseModel):
    """Input model for adding extra playtime."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    minutes: int = Field(
        ...,
        description="Number of extra minutes to add for today (must be positive).",
        ge=1,
        le=360,
    )


class SetTimerModeInput(BaseModel):
    """Input model for setting the timer mode."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    mode: str = Field(
        ...,
        description="Timer mode: 'DAILY' for a single limit for all days, or 'EACH_DAY_OF_THE_WEEK' for per-day limits.",  # noqa: E501
        pattern="^(DAILY|EACH_DAY_OF_THE_WEEK)$",
    )


class SetDayRestrictionsInput(BaseModel):
    """Input model for setting per-day-of-week restrictions."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
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

    @model_validator(mode="after")
    def validate_playtime_and_bedtime(self) -> "SetDayRestrictionsInput":
        if self.playtime_enabled and self.max_playtime_minutes is None:
            raise ValueError("max_playtime_minutes is required when playtime_enabled is true")
        if not self.playtime_enabled and self.max_playtime_minutes is not None:
            raise ValueError("max_playtime_minutes must not be set when playtime_enabled is false")
        if not self.bedtime_enabled and (
            self.bedtime_alarm_hour is not None or self.bedtime_end_hour is not None
        ):
            raise ValueError("bedtime hours must not be set when bedtime_enabled is false")
        return self


class SetRestrictionModeInput(BaseModel):
    """Input model for setting the restriction mode."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    mode: str = Field(
        ...,
        description=(
            "Restriction mode: 'FORCED_TERMINATION' to suspend software when playtime limit is reached, "
            "or 'ALARM' to only show an alarm without suspending."
        ),
        pattern="^(FORCED_TERMINATION|ALARM)$",
    )


class SetContentRestrictionInput(BaseModel):
    """Input model for setting the content restriction level."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    level: str = Field(
        ...,
        description=(
            "Content restriction level: 'NONE' (no restriction), 'CHILDREN' (young child), "
            "'YOUNG_TEENS', 'OLDER_TEENS' (teen), or 'CUSTOM'."
        ),
        pattern="^(NONE|CHILDREN|YOUNG_TEENS|OLDER_TEENS|CUSTOM)$",
    )


class SetBedtimeAlarmInput(BaseModel):
    """Input model for setting the bedtime alarm."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    hour: int = Field(
        ...,
        description="Hour for the bedtime alarm (16-23). Use 0 with minute=0 to disable the alarm.",
        ge=0,
        le=23,
    )
    minute: int = Field(
        default=0,
        description="Minute for the bedtime alarm (0-59).",
        ge=0,
        le=59,
    )

    @model_validator(mode="after")
    def validate_alarm_time(self) -> "SetBedtimeAlarmInput":
        if self.hour == 0 and self.minute != 0:
            raise ValueError("Use hour=0, minute=0 to disable the bedtime alarm")
        if self.hour != 0 and self.hour not in range(16, 24):
            raise ValueError("Bedtime alarm hour must be between 16 and 23, or 0 to disable")
        return self


class SetBedtimeEndInput(BaseModel):
    """Input model for setting the bedtime end time."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    hour: int = Field(
        ...,
        description="Hour when bedtime ends and the device can be used again (5-9). Use 0 with minute=0 to disable.",
        ge=0,
        le=9,
    )
    minute: int = Field(
        default=0,
        description="Minute when bedtime ends (0-59).",
        ge=0,
        le=59,
    )

    @model_validator(mode="after")
    def validate_end_time(self) -> "SetBedtimeEndInput":
        if self.hour == 0 and self.minute != 0:
            raise ValueError("Use hour=0, minute=0 to disable the bedtime end time")
        if self.hour != 0 and self.hour not in range(5, 10):
            raise ValueError("Bedtime end hour must be between 5 and 9, or 0 to disable")
        return self


class PlayerInput(BaseModel):
    """Input model for player queries."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    player_id: str = Field(..., description="The unique player ID. Use nintendo_list_players to find it.")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable.",
    )


class SetAppAllowListInput(BaseModel):
    """Input model for setting an application's allow-list status."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    device_id: str = Field(..., description="The unique device ID. Use nintendo_list_devices to find it.")
    application_id: str = Field(
        ...,
        description="The unique application ID. Use nintendo_list_applications to find it.",
    )
    allow: bool = Field(
        ...,
        description=(
            "True to add the application to the allow list (bypasses content restrictions). "
            "False to remove it from the allow list."
        ),
    )


class CompleteLoginInput(BaseModel):
    """Input model for completing the Nintendo login flow."""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True, extra="forbid")

    redirect_url: str = Field(
        ...,
        description=(
            "The URL you were redirected to after clicking 'Select this person' on the Nintendo login page. "
            "It starts with 'npf71b963c1b7b6d119://' or similar."
        ),
        min_length=10,
    )
