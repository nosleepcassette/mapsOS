# maps · cassette.help · MIT
"""Regression tests for documented Phase 2.6 fixes."""

import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments.date_resolver import resolve_date
from environments.pattern_weaver import _arc_goal_stall
from environments.vent_parser import parse_vent
from environments.viz import render_viz


def _goal(description: str, status: str, days_ago: int) -> dict:
    goal_date = (date.today() - timedelta(days=days_ago)).isoformat()
    return {"content": f"GOAL: {goal_date} | {description} | none | {status}"}


class TestVentParserPhase26Fixes:
    def test_parse_vent_routes_events_and_deadlines(self):
        entries = parse_vent(
            "therapy on monday and there's a deadline tomorrow for taxes"
        )
        tracks = [e.track for e in entries]
        assert "EVENT" in tracks
        assert "DEADLINE" in tracks

    def test_parse_vent_keeps_multiple_events(self):
        entries = parse_vent("therapy on monday and meeting on tuesday")
        event_notes = [e.note for e in entries if e.track == "EVENT"]
        assert len(event_notes) == 2

    def test_trigger_extraction_ignores_bare_because(self):
        entries = parse_vent("i feel bad because work is hard")
        triggers = [e for e in entries if e.track == "TRIGGER"]
        assert triggers == []

    def test_trigger_extraction_detects_specific_trigger_language(self):
        entries = parse_vent("i got triggered by the text from alex")
        triggers = [e for e in entries if e.track == "TRIGGER"]
        assert len(triggers) == 1

    def test_event_extraction_ignores_generic_have_phrase(self):
        entries = parse_vent("i have things to do today")
        events = [e for e in entries if e.track == "EVENT"]
        assert events == []

    def test_event_extraction_detects_specific_event_language(self):
        expected_date = resolve_date("thursday", date.today()).isoformat()
        entries = parse_vent("therapy on thursday")
        events = [e for e in entries if e.track == "EVENT"]
        assert len(events) == 1
        assert events[0].note.startswith(expected_date)


class TestPatternWeaverPhase26Fixes:
    def test_goal_stall_fires_for_old_open_goal(self):
        arc = _arc_goal_stall([_goal("finish taxes", "open", 21)])
        assert arc is not None
        assert arc.name == "goal_stall"

    def test_goal_stall_ignores_done_goal(self):
        arc = _arc_goal_stall([_goal("finish taxes", "done", 21)])
        assert arc is None


class TestDateResolverPhase26Fixes:
    def test_resolve_tomorrow(self):
        today = date(2026, 4, 10)
        assert resolve_date("tomorrow", today) == date(2026, 4, 11)


class TestVizPhase26Fixes:
    def test_render_viz_body_panel_tracks_presence_per_day(self):
        pytest.importorskip("rich")

        # Entries within the 7-day window (cutoff = today - 6 days)
        today = date.today()
        body_entries = [
            {"content": f"BODY: {(today - timedelta(days=5)).isoformat()} | sleep | poor | first"},
            {"content": f"BODY: {(today - timedelta(days=3)).isoformat()} | sleep | solid | second"},
        ]

        panel = render_viz(body_entries, [])
        # Panel should be returned and contain sleep data
        assert panel is not None
        plain = panel.renderable.plain
        # sleep row should appear somewhere in the output
        assert "sleep" in plain
