# maps · cassette.help · MIT
"""Tests for mapsOS config generalization and cart bridge helpers."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments import cart_bridge
from environments.maps_os_config import (
    DEFAULT_STATE_TAGS,
    load_capacity_config,
    load_state_tags,
    load_tracks_config,
)
from environments.survival_mode import should_exit


def test_load_state_tags_defaults_and_custom_values():
    assert load_state_tags({}) == DEFAULT_STATE_TAGS
    assert load_state_tags({"state": {"tags": {"clear": "sharp", "spent": "done"}}}) == {
        "clear": "sharp",
        "spent": "done",
    }


def test_load_capacity_config_supports_low_capacity_and_survival_mode():
    default_cfg = load_capacity_config({})
    assert default_cfg["survival_mode"] is False
    assert default_cfg["mode_label"] == "low capacity"

    survival_cfg = load_capacity_config(
        {"capacity": {"survival_mode": True, "threshold": 4, "window": 6}}
    )
    assert survival_cfg["survival_mode"] is True
    assert survival_cfg["mode_label"] == "survival mode"
    assert survival_cfg["threshold"] == 4
    assert survival_cfg["window"] == 6


def test_load_tracks_config_uses_custom_tracks_when_present():
    tracks = load_tracks_config(
        {
            "tracks": [
                {"name": "BODY", "categories": ["sleep", "energy"]},
                {"name": "WORK", "categories": ["output", "blockers"]},
            ]
        }
    )
    assert tracks[0]["categories"] == ["sleep", "energy"]
    assert tracks[1]["name"] == "WORK"


def test_cart_bridge_parses_task_output_and_gracefully_handles_absence(monkeypatch):
    class _Result:
        def __init__(self, stdout: str, returncode: int = 0):
            self.stdout = stdout
            self.returncode = returncode

    monkeypatch.setattr(cart_bridge, "cart_available", lambda: True)
    monkeypatch.setattr(
        cart_bridge.subprocess,
        "run",
        lambda *args, **kwargs: _Result(
            '{"tasks":[{"id":"t1","text":"ship","status":"open","priority":"P0","project":"atlas"},'
            '{"id":"t2","text":"test","status":"open","priority":"P1"}]}'
        ),
    )

    tasks = cart_bridge.get_open_tasks("P0")

    assert tasks == [
        {
            "id": "t1",
            "text": "ship",
            "status": "open",
            "priority": "P0",
            "project": "atlas",
            "due": "",
            "path": "",
        },
        {
            "id": "t2",
            "text": "test",
            "status": "open",
            "priority": "P1",
            "project": "",
            "due": "",
            "path": "",
        },
    ]


def test_cart_bridge_prefers_sessions_recent_json(monkeypatch):
    class _Result:
        def __init__(self, stdout: str, returncode: int = 0):
            self.stdout = stdout
            self.returncode = returncode

    monkeypatch.setattr(cart_bridge, "cart_available", lambda: True)
    monkeypatch.setattr(
        cart_bridge.subprocess,
        "run",
        lambda *args, **kwargs: _Result(
            '{"schema_version":"2026-04-17","surface":"sessions.recent","count":1,'
            '"sessions":[{"id":"hermes-session-h1","title":"Hermes Session 1","agent":"hermes",'
            '"type":"agent-log","date":"2026-04-17","summary_preview":"kept context clean",'
            '"path":"/tmp/h1.md","source_type":"hermes"}]}'
        ),
    )

    sessions = cart_bridge.get_recent_sessions(1)

    assert sessions == [
        {
            "id": "hermes-session-h1",
            "title": "Hermes Session 1",
            "agent": "hermes",
            "type": "agent-log",
            "date": "2026-04-17",
            "summary_preview": "kept context clean",
            "path": "/tmp/h1.md",
            "source_type": "hermes",
        }
    ]


def test_should_exit_accepts_custom_low_state_set():
    assert should_exit("stable", was_in_survival=True, low_states={"depleted"}) is True
    assert should_exit("depleted", was_in_survival=True, low_states={"depleted"}) is False
