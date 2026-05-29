"""Shared test fixtures for the Nintendo MCP server tests."""

from datetime import time
from unittest.mock import AsyncMock, MagicMock

import pytest


def make_mock_device(
    device_id="device-001",
    name="My Switch",
    model="Switch",
    limit_time=120,
    today_playing_time=45,
    today_time_remaining=75,
    bedtime_alarm=time(21, 0),
    bedtime_end=time(7, 0),
    forced_termination_mode=True,
    alarms_enabled=True,
    last_sync=1700000000.0,
    timer_mode_str="DAILY",
):
    """Create a mock Device object."""
    from pynintendoparental.enum import DeviceTimerMode

    device = MagicMock()
    device.device_id = device_id
    device.name = name
    device.model = model
    device.limit_time = limit_time
    device.today_playing_time = today_playing_time
    device.today_time_remaining = today_time_remaining
    device.bedtime_alarm = bedtime_alarm
    device.bedtime_end = bedtime_end
    device.forced_termination_mode = forced_termination_mode
    device.alarms_enabled = alarms_enabled
    device.last_sync = last_sync
    device.timer_mode = DeviceTimerMode(timer_mode_str)
    device.daily_summaries = [
        {
            "date": "2026-05-01",
            "playingTime": 60,
            "disabledTime": 0,
            "exceededTime": 0,
            "players": [
                {
                    "profile": {"playerId": "player-001", "nickname": "TestKid", "imageUri": "https://example.com/avatar.png"},
                    "playingTime": 45,
                    "playedGames": [],
                }
            ],
        },
        {
            "date": "2026-05-02",
            "playingTime": 90,
            "disabledTime": 5,
            "exceededTime": 10,
            "players": [
                {
                    "profile": {"playerId": "player-001", "nickname": "TestKid", "imageUri": "https://example.com/avatar.png"},
                    "playingTime": 75,
                    "playedGames": [],
                }
            ],
        },
        {
            "date": "2026-04-07",
            "playingTime": 45,
            "disabledTime": 0,
            "exceededTime": 0,
            "players": [
                {
                    "profile": {"playerId": "player-001", "nickname": "TestKid", "imageUri": "https://example.com/avatar.png"},
                    "playingTime": 30,
                    "playedGames": [],
                }
            ],
        },
    ]
    device.players = {}
    device.applications = {}

    # Async methods
    device.update = AsyncMock()
    device.update_max_daily_playtime = AsyncMock()
    device.add_extra_time = AsyncMock()
    device.set_timer_mode = AsyncMock()
    device.set_daily_restrictions = AsyncMock()
    device.set_restriction_mode = AsyncMock()
    device.set_functional_restriction_level = AsyncMock()
    device.set_bedtime_alarm = AsyncMock()
    device.set_bedtime_end_time = AsyncMock()
    device.get_monthly_summary = AsyncMock(
        return_value={
            "overall": {
                "stat": {"totalDays": 20, "averageTime": 60},
                "dailyStats": [
                    {"date": "2026-04-01", "totalTime": 600, "games": {}},
                    {"date": "2026-04-02", "totalTime": 600, "games": {}},
                ],
            },
            "players": [
                {
                    "profile": {"playerId": "player-001", "nickname": "TestKid"},
                    "summary": {
                        "stat": {"totalDays": 2, "averageTime": 60},
                        "dailyStats": [
                            {"date": "2026-04-01", "totalTime": 600, "games": {}},
                            {"date": "2026-04-02", "totalTime": 600, "games": {}},
                        ],
                    },
                }
            ],
        }
    )

    def get_player(player_id):
        if player_id in device.players:
            return device.players[player_id]
        raise ValueError(f"Player {player_id} not found")

    def get_application(app_id):
        if app_id in device.applications:
            return device.applications[app_id]
        raise ValueError(f"Application {app_id} not found")

    device.get_player = get_player
    device.get_application = get_application

    return device


def make_mock_player(
    player_id="player-001",
    nickname="TestKid",
    player_image="https://example.com/avatar.png",
    playing_time=45,
    apps=None,
):
    """Create a mock Player object."""
    player = MagicMock()
    player.player_id = player_id
    player.nickname = nickname
    player.player_image = player_image
    player.playing_time = playing_time
    player.apps = apps or []
    return player


def make_mock_application(
    application_id="app-001",
    name="Test Game",
    image_url="https://example.com/game.png",
    today_time_played=30,
    safe_launch_setting_str="NONE",
):
    """Create a mock Application object."""
    from pynintendoparental.enum import SafeLaunchSetting

    app = MagicMock()
    app.application_id = application_id
    app.name = name
    app.image_url = image_url
    app.today_time_played = today_time_played
    app.safe_launch_setting = SafeLaunchSetting(safe_launch_setting_str)
    app.set_safe_launch_setting = AsyncMock()
    return app


def make_mock_client(devices=None):
    """Create a mock NintendoParental client."""
    client = MagicMock()
    client.update = AsyncMock()
    client.devices = devices or {}
    return client


@pytest.fixture(autouse=True)
async def reset_state():
    """Reset server state before each test.

    Snapshots _state keys before the test, then on teardown restores the
    snapshot and unconditionally clears client/http_session/pending_auth to
    prevent resource or auth leaks across tests.
    """
    from switch_parental_controls import server

    original_state = dict(server._state)
    yield
    # Close any session opened during the test to avoid resource leaks.
    # Real aiohttp sessions and mock sessions with closed=False both pass through here;
    # mock sessions must expose an async close() so the await succeeds.
    session = server._state.get("http_session")
    if session is not None and not session.closed:
        await session.close()
    server._state.clear()
    server._state.update(original_state)
    server._state["client"] = None
    server._state["http_session"] = None
    server._state["pending_auth"] = None
