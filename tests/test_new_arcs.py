# maps · cassette.help · MIT
"""Tests for new arcs 9, 12, 13, 15 in pattern_weaver.py."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments.pattern_weaver import (
    weave,
    _arc_productivity_spiral,
    _arc_catastrophizing_spike,
    _arc_intrusive_loop,
    _arc_planning_hyperfocus,
)


def _state(tag: str, note: str = "") -> dict:
    return {"content": f"STATE: 2026-04-09 | {tag} | {note}"}


def _mind(category: str, status: str) -> dict:
    return {"content": f"MIND: 2026-04-09 | {category} | {status} | note"}


def _spirit(category: str, status: str) -> dict:
    return {"content": f"SPIRIT: 2026-04-09 | {category} | {status} | note"}


def _flash(text: str) -> dict:
    return {"content": f"FLASH: 2026-04-09 | {text}"}


def _intention(name: str, status: str) -> dict:
    return {"content": f"INTENTION: {name} | {status} | 2026-04-09 | note"}


# ---------------------------------------------------------------------------
# ARC 9 — Productivity Spiral
# ---------------------------------------------------------------------------

class TestArc9ProductivitySpiral:
    def test_fires_on_depleted_with_work_language_and_no_spirit(self):
        states = [_state("depleted", "been building all day shipped the thing")]
        mind = [_mind("flow", "high")]
        spirit = []  # nothing logged
        arc = _arc_productivity_spiral(states * 3, mind, spirit)
        assert arc is not None
        assert arc.name == "productivity_spiral"
        assert arc.severity == "insight"

    def test_fires_on_manic_with_no_purpose(self):
        states = [_state("manic", "working working working output output")]
        mind = [_mind("focus", "hyper")]
        spirit = [_spirit("isolation", "high")]  # no purpose/connection
        arc = _arc_productivity_spiral(states * 3, mind, spirit * 3)
        assert arc is not None

    def test_does_not_fire_if_spirit_purpose_present(self):
        states = [_state("depleted", "built the thing feels meaningful")]
        mind = [_mind("flow", "high")]
        spirit = [_spirit("purpose", "present")]
        arc = _arc_productivity_spiral(states * 3, mind, spirit)
        assert arc is None

    def test_does_not_fire_if_spirit_connection_present(self):
        states = [_state("manic", "shipping")]
        mind = [_mind("flow", "high")]
        spirit = [_spirit("connection", "rising")]
        arc = _arc_productivity_spiral(states * 3, mind, spirit)
        assert arc is None

    def test_does_not_fire_on_stable_state(self):
        states = [_state("stable", "worked on project")]
        mind = [_mind("flow", "high")]
        spirit = []
        arc = _arc_productivity_spiral(states * 3, mind, spirit)
        assert arc is None

    def test_fires_when_spirit_completely_absent(self):
        # Zero spirit entries + depleted + work language = spiral signal
        states = [_state("depleted", "building")]
        mind = [_mind("flow", "high")]
        spirit = []
        arc = _arc_productivity_spiral(states * 3, mind, spirit)
        assert arc is not None


# ---------------------------------------------------------------------------
# ARC 12 — Catastrophizing Spike
# ---------------------------------------------------------------------------

class TestArc12CatastrophizingSpike:
    def test_fires_on_everything_is_fucked(self):
        states = [_state("flooded", "everything is fucked and nothing works")]
        arc = _arc_catastrophizing_spike(states)
        assert arc is not None
        assert arc.name == "catastrophizing_spike"
        assert arc.severity == "insight"

    def test_fires_on_its_over(self):
        states = [_state("depleted", "its over i can't fix this")]
        arc = _arc_catastrophizing_spike(states)
        assert arc is not None

    def test_fires_on_complete_failure(self):
        states = [_state("grieving", "this is a complete failure")]
        arc = _arc_catastrophizing_spike(states)
        assert arc is not None

    def test_does_not_fire_on_normal_venting(self):
        states = [_state("depleted", "had a rough day, things are hard")]
        arc = _arc_catastrophizing_spike(states)
        assert arc is None

    def test_does_not_fire_on_empty_notes(self):
        states = [_state("stable")]
        arc = _arc_catastrophizing_spike(states)
        assert arc is None

    def test_checks_recent_3_entries(self):
        # Only fires if catastrophizing is in recent 3
        old = [_state("stable", "nothing is fucked")] * 5
        recent = [_state("flooded", "everything is fucked")]
        arc = _arc_catastrophizing_spike(old + recent)
        assert arc is not None

    def test_message_asks_for_specific_thing(self):
        states = [_state("flooded", "everything is fucked")]
        arc = _arc_catastrophizing_spike(states)
        assert "one actual thing" in arc.message.lower()


# ---------------------------------------------------------------------------
# ARC 13 — Intrusive Loop
# ---------------------------------------------------------------------------

class TestArc13IntrusiveLoop:
    def test_fires_when_topic_appears_3_times(self):
        flashes = [
            _flash("thinking about emma again"),
            _flash("cant stop thinking about emma"),
            _flash("emma keeps coming up"),
        ]
        arc = _arc_intrusive_loop(flashes)
        assert arc is not None
        assert arc.name == "intrusive_loop"
        assert arc.severity == "insight"
        assert "emma" in arc.message.lower()

    def test_does_not_fire_with_fewer_than_3_entries(self):
        flashes = [_flash("emma"), _flash("emma")]
        arc = _arc_intrusive_loop(flashes)
        assert arc is None

    def test_does_not_fire_on_varied_content(self):
        flashes = [
            _flash("thinking about emma"),
            _flash("working on polycule project"),
            _flash("grocery list"),
        ]
        arc = _arc_intrusive_loop(flashes)
        assert arc is None

    def test_fires_on_name_repetition(self):
        flashes = [_flash(f"still thinking about dana") for _ in range(4)]
        arc = _arc_intrusive_loop(flashes)
        assert arc is not None

    def test_count_in_message(self):
        flashes = [_flash("thinking about cassette") for _ in range(5)]
        arc = _arc_intrusive_loop(flashes)
        assert arc is not None
        assert "5" in arc.message or "loop" in arc.message.lower()

    def test_returns_none_on_empty_list(self):
        assert _arc_intrusive_loop([]) is None


# ---------------------------------------------------------------------------
# ARC 15 — Planning Hyperfocus
# ---------------------------------------------------------------------------

class TestArc15PlanningHyperfocus:
    def test_fires_when_planning_language_no_intentions(self):
        states = [_state("stable", "working on a plan for the whole system architecture")]
        mind = [_mind("flow", "high")]
        intentions = []  # no intentions today
        arc = _arc_planning_hyperfocus(states * 3, mind, intentions)
        assert arc is not None
        assert arc.name == "planning_hyperfocus"
        assert arc.severity == "insight"

    def test_does_not_fire_in_crisis(self):
        states = [_state("depleted", "planning everything")]
        mind = [_mind("flow", "high")]
        arc = _arc_planning_hyperfocus(states * 3, mind, [])
        assert arc is None

    def test_does_not_fire_if_intentions_logged_today(self):
        states = [_state("stable", "planning the roadmap strategy")]
        mind = [_mind("focus", "high")]
        # intention logged today
        intentions = [{"content": "INTENTION: water | met | 2026-04-09 | done"}]
        arc = _arc_planning_hyperfocus(states * 3, mind, intentions)
        assert arc is None

    def test_does_not_fire_without_high_mind(self):
        states = [_state("stable", "planning something")]
        mind = [_mind("focus", "scattered")]  # not high/flow
        arc = _arc_planning_hyperfocus(states * 3, mind, [])
        assert arc is None

    def test_message_references_first_move(self):
        states = [_state("stable", "building a planning system for the workflow")]
        mind = [_mind("flow", "high")]
        arc = _arc_planning_hyperfocus(states * 3, mind, [])
        assert arc is not None
        assert "first move" in arc.message.lower() or "first step" in arc.message.lower()

    def test_does_not_fire_on_grieving_state(self):
        states = [_state("grieving", "planning a strategy")]
        mind = [_mind("flow", "high")]
        arc = _arc_planning_hyperfocus(states * 3, mind, [])
        assert arc is None


# ---------------------------------------------------------------------------
# Integration — weave() with new arcs and flash_entries
# ---------------------------------------------------------------------------

class TestWeaveIntegration:
    def test_weave_accepts_flash_entries(self):
        """weave() should accept flash_entries kwarg without error."""
        flashes = [_flash("emma") for _ in range(4)]
        arcs = weave([], [], [], [], [], flash_entries=flashes)
        assert isinstance(arcs, list)

    def test_weave_without_flash_entries_still_works(self):
        """Old callers with 5 positional args still work."""
        arcs = weave([], [], [], [], [])
        assert isinstance(arcs, list)

    def test_weave_returns_intrusive_loop_arc(self):
        flashes = [_flash("still thinking about emma") for _ in range(4)]
        arcs = weave([], [], [], [], [], flash_entries=flashes)
        names = [a.name for a in arcs]
        assert "intrusive_loop" in names

    def test_weave_returns_catastrophizing_arc(self):
        states = [_state("flooded", "everything is fucked nothing works")]
        arcs = weave(states, [], [], [], [])
        names = [a.name for a in arcs]
        assert "catastrophizing_spike" in names

    def test_alert_suppresses_new_insight_arcs(self):
        """A manic spike alert should still fire; new arcs are insights (not stackable alerts)."""
        states = [_state("manic", "building building shipping")]
        body = [{"content": "BODY: 2026-04-09 | sleep | none | no sleep"}]
        mind = [_mind("flow", "hyper")]
        arcs = weave(states, body, mind, [], [])
        alerts = [a for a in arcs if a.severity == "alert"]
        assert len(alerts) <= 1  # at most one alert


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
