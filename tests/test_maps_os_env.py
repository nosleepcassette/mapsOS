# maps · cassette.help · MIT
"""
Tests for mapsOS: vent_parser, pattern_weaver, survival_mode, maps_os_env.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments.vent_parser import (
    parse_vent, format_garden_commands, Entry, VALID_STATE_TAGS
)
from environments.pattern_weaver import (
    weave, check_survival_trigger, Arc
)
from environments.survival_mode import (
    evaluate as eval_survival, briefing as survival_briefing,
    filter_entries_for_survival, should_exit, exit_message
)
from environments.maps_os_env import (
    MapsOSEnv, MapsOSScenario, SCENARIOS, compute_maps_os_reward
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _state_entry(tag: str, date: str = "2026-04-09") -> dict:
    return {"content": f"STATE: {date} | {tag} | test entry"}


def _body_entry(category: str, status: str, date: str = "2026-04-09") -> dict:
    return {"content": f"BODY: {date} | {category} | {status} | test"}


def _mind_entry(category: str, status: str, date: str = "2026-04-09") -> dict:
    return {"content": f"MIND: {date} | {category} | {status} | test"}


def _spirit_entry(category: str, status: str, date: str = "2026-04-09") -> dict:
    return {"content": f"SPIRIT: {date} | {category} | {status} | test"}


def _intention_entry(name: str, status: str, date: str = "2026-04-09") -> dict:
    return {"content": f"INTENTION: {name} | {status} | {date} | test"}


# ---------------------------------------------------------------------------
# vent_parser tests
# ---------------------------------------------------------------------------

class TestVentParser:
    def test_returns_list(self):
        result = parse_vent("i'm fine")
        assert isinstance(result, list)

    def test_always_has_state_first(self):
        result = parse_vent("i'm exhausted and depleted")
        assert len(result) >= 1
        assert result[0].track == "STATE"

    def test_state_is_valid_tag(self):
        result = parse_vent("running on fumes and spite")
        assert result[0].category in VALID_STATE_TAGS

    def test_depleted_detection(self):
        result = parse_vent("i'm fucking exhausted but i can't stop coding, running on fumes")
        state = result[0]
        assert state.category == "depleted"

    def test_manic_detection(self):
        result = parse_vent("ideas everywhere, can't stop, going going going, everything is clicking")
        assert result[0].category == "manic"

    def test_grieving_detection(self):
        result = parse_vent("i can't stop crying, i just miss her so much, everything feels like loss")
        assert result[0].category == "grieving"

    def test_flooded_detection(self):
        result = parse_vent("too much, everything is too much, i'm drowning and spinning out")
        assert result[0].category == "flooded"

    def test_clear_detection(self):
        result = parse_vent("weirdly clear today, post-storm calm, things feel sharp")
        assert result[0].category == "clear"

    def test_thriving_detection(self):
        result = parse_vent("feeling really good, things are clicking and in it")
        assert result[0].category == "thriving"

    def test_grounded_detection(self):
        result = parse_vent("feeling grounded today, actually okay and present")
        assert result[0].category == "grounded"

    def test_tender_detection(self):
        result = parse_vent("feel tender after that call, emotionally open")
        assert result[0].category == "tender"

    def test_stable_fallback(self):
        result = parse_vent("okay, fine, neutral, nothing happening")
        assert result[0].category == "stable"

    def test_body_sleep_detected(self):
        result = parse_vent("haven't slept, been up since 3am, can't stop coding")
        tracks = [e.track for e in result]
        assert "BODY" in tracks
        body = next(e for e in result if e.track == "BODY" and e.category == "sleep")
        assert body.status == "none"

    def test_body_hunger_detected(self):
        result = parse_vent("i forgot to eat, haven't eaten all day")
        body = next((e for e in result if e.track == "BODY" and e.category == "hunger"), None)
        assert body is not None
        assert body.status in ("starving", "ignored")

    def test_body_pain_detected(self):
        result = parse_vent("my back is really sore from sitting, headache too")
        body = next((e for e in result if e.track == "BODY" and e.category == "pain"), None)
        assert body is not None

    def test_body_movement_detected(self):
        result = parse_vent("went for a run this morning, feeling better")
        body = next((e for e in result if e.track == "BODY" and e.category == "movement"), None)
        assert body is not None

    def test_mind_focus_hyper(self):
        result = parse_vent("i literally can't stop coding, been at it for 6 hours")
        mind = next((e for e in result if e.track == "MIND" and e.category == "focus"), None)
        assert mind is not None
        assert mind.status == "hyper"

    def test_mind_flow(self):
        result = parse_vent("i lost track of time, hours passed, totally in the zone")
        mind = next((e for e in result if e.track == "MIND" and e.category == "flow"), None)
        assert mind is not None

    def test_spirit_isolation(self):
        result = parse_vent("i feel so alone, haven't talked to anyone, isolated and disconnected")
        spirit = next((e for e in result if e.track == "SPIRIT" and e.category == "isolation"), None)
        assert spirit is not None

    def test_spirit_connection(self):
        result = parse_vent("had a really nice call, feeling connected and seen")
        spirit = next((e for e in result if e.track == "SPIRIT" and e.category == "connection"), None)
        assert spirit is not None

    def test_no_duplicate_categories(self):
        result = parse_vent("exhausted, so tired, wiped out, running on empty, dead inside")
        tracks_cats = [(e.track, e.category) for e in result]
        assert len(tracks_cats) == len(set(tracks_cats)), "duplicate track/category found"

    def test_narrative_truncated_to_80_chars(self):
        long_text = "i am feeling very exhausted and overwhelmed by everything that is happening today and it won't stop"
        result = parse_vent(long_text)
        assert len(result[0].note) <= 83  # 80 + "..."

    def test_empty_input_returns_empty(self):
        assert parse_vent("") == []
        assert parse_vent("   ") == []

    def test_to_garden_state(self):
        e = Entry(track="STATE", date="2026-04-09", category="depleted",
                  status=None, note="running on fumes")
        assert e.to_garden() == "STATE: 2026-04-09 | depleted | running on fumes"

    def test_to_garden_body(self):
        e = Entry(track="BODY", date="2026-04-09", category="sleep",
                  status="none", note="up since 3am")
        assert e.to_garden() == "BODY: 2026-04-09 | sleep | none | up since 3am"

    def test_to_garden_intention(self):
        e = Entry(track="INTENTION", date="2026-04-09", category="water",
                  status="missed", note="forgot again")
        assert e.to_garden() == "INTENTION: water | missed | 2026-04-09 | forgot again"

    def test_format_garden_commands(self):
        result = parse_vent("exhausted, haven't slept")
        cmds = format_garden_commands(result)
        assert len(cmds) == len(result)
        assert all(c.startswith("garden remember '") for c in cmds)
        assert all("--graph cassette" in c for c in cmds)

    def test_custom_date(self):
        result = parse_vent("feeling okay", log_date="2026-01-15")
        assert result[0].date == "2026-01-15"

    def test_combined_vent(self):
        """The canonical example from the spec."""
        result = parse_vent(
            "i'm fucking exhausted but i can't stop coding, "
            "i feel like i'm running on fumes and spite"
        )
        state = result[0]
        assert state.track == "STATE"
        assert state.category == "depleted"
        has_body_energy = any(e.track == "BODY" and e.category == "energy" for e in result)
        has_mind_focus = any(e.track == "MIND" and e.category == "focus" for e in result)
        assert has_body_energy or has_mind_focus


# ---------------------------------------------------------------------------
# pattern_weaver tests
# ---------------------------------------------------------------------------

class TestPatternWeaver:
    def test_returns_list(self):
        arcs = weave([], [], [], [], [], apply_cooldown=False)
        assert isinstance(arcs, list)

    def test_no_arcs_when_no_data(self):
        arcs = weave([], [], [], [], [], apply_cooldown=False)
        assert arcs == []

    def test_survival_trigger_two_depleted(self):
        states = [_state_entry("depleted"), _state_entry("depleted", "2026-04-10")]
        assert check_survival_trigger(states) is True

    def test_survival_trigger_grieving_depleted(self):
        states = [_state_entry("grieving"), _state_entry("depleted", "2026-04-10")]
        assert check_survival_trigger(states) is True

    def test_no_survival_trigger_one_depleted(self):
        states = [_state_entry("depleted")]
        assert check_survival_trigger(states) is False

    def test_no_survival_trigger_mixed_good(self):
        states = [_state_entry("thriving"), _state_entry("stable"), _state_entry("depleted")]
        assert check_survival_trigger(states) is False

    def test_manic_spike_arc(self):
        states = [_state_entry("manic")]
        body = [_body_entry("sleep", "none")]
        mind = [_mind_entry("flow", "high")]
        arcs = weave(states, body, mind, [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "manic_spike" in names

    def test_manic_spike_requires_bad_sleep_and_flow(self):
        # Manic with good sleep — no spike arc
        states = [_state_entry("manic")]
        body = [_body_entry("sleep", "solid")]
        mind = [_mind_entry("flow", "high")]
        arcs = weave(states, body, mind, [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "manic_spike" not in names

    def test_isolation_creep_three_days(self):
        spirit = [
            _spirit_entry("isolation", "high"),
            _spirit_entry("isolation", "high", "2026-04-10"),
            _spirit_entry("isolation", "high", "2026-04-11"),
        ]
        arcs = weave([], [], [], spirit, [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "isolation_creep" in names

    def test_body_neglect_high_flow(self):
        body = [
            _body_entry("hunger", "starving"),
            _body_entry("movement", "none"),
        ]
        mind = [_mind_entry("flow", "high")]
        arcs = weave([], body, mind, [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "body_neglect" in names

    def test_body_neglect_no_flow(self):
        # Hungry but not in flow — no body neglect arc
        body = [_body_entry("hunger", "starving")]
        mind = [_mind_entry("focus", "low")]
        arcs = weave([], body, mind, [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "body_neglect" not in names

    def test_state_dip_holding(self):
        states = [
            _state_entry("depleted"),
            _state_entry("depleted", "2026-04-10"),
            _state_entry("grieving", "2026-04-11"),
        ]
        arcs = weave(states, [], [], [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "state_dip_holding" in names

    def test_post_manic_drop(self):
        states = [
            _state_entry("manic", "2026-04-07"),
            _state_entry("manic", "2026-04-08"),
            _state_entry("depleted", "2026-04-09"),
        ]
        arcs = weave(states, [], [], [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "post_manic_drop" in names

    def test_thriving_streak(self):
        states = [
            _state_entry("thriving", "2026-04-07"),
            _state_entry("thriving", "2026-04-08"),
            _state_entry("thriving", "2026-04-09"),
        ]
        arcs = weave(states, [], [], [], [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "thriving_streak" in names

    def test_spirit_rising_insight(self):
        states = [_state_entry("depleted")]
        spirit = [_spirit_entry("connection", "rising")]
        arcs = weave(states, [], [], spirit, [], apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "spirit_rising" in names

    def test_intention_miss_pattern(self):
        intentions = [
            _intention_entry("water", "missed", f"2026-04-0{i}") for i in range(1, 6)
        ]
        arcs = weave([], [], [], [], intentions, apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "intention_miss_pattern" in names

    def test_intention_miss_needs_four_days(self):
        # Only 3 misses — should not trigger
        intentions = [
            _intention_entry("water", "missed", f"2026-04-0{i}") for i in range(1, 4)
        ]
        arcs = weave([], [], [], [], intentions, apply_cooldown=False)
        names = [a.name for a in arcs]
        assert "intention_miss_pattern" not in names

    def test_alerts_do_not_stack(self):
        """Only one alert-level arc should fire."""
        states = [_state_entry("manic")]
        body = [_body_entry("sleep", "none"), _body_entry("hunger", "starving")]
        mind = [_mind_entry("flow", "high")]
        spirit = [
            _spirit_entry("isolation", "high"),
            _spirit_entry("isolation", "high", "2026-04-10"),
            _spirit_entry("isolation", "high", "2026-04-11"),
        ]
        arcs = weave(states, body, mind, spirit, [], apply_cooldown=False)
        alerts = [a for a in arcs if a.severity == "alert"]
        assert len(alerts) == 1

    def test_arc_has_message(self):
        states = [
            _state_entry("thriving", "2026-04-07"),
            _state_entry("thriving", "2026-04-08"),
            _state_entry("thriving", "2026-04-09"),
        ]
        arcs = weave(states, [], [], [], [], apply_cooldown=False)
        for arc in arcs:
            assert len(arc.message) > 0 or arc.severity == "survival"


# ---------------------------------------------------------------------------
# survival_mode tests
# ---------------------------------------------------------------------------

class TestSurvivalMode:
    def test_not_active_with_no_entries(self):
        result = eval_survival([])
        assert result.active is False

    def test_not_active_single_depleted(self):
        result = eval_survival([_state_entry("depleted")])
        assert result.active is False

    def test_active_three_low_states_in_last_five(self):
        states = [
            _state_entry("stable", "2026-04-07"),
            _state_entry("depleted", "2026-04-08"),
            _state_entry("surviving", "2026-04-09"),
            _state_entry("grounded", "2026-04-10"),
            _state_entry("depleted", "2026-04-11"),
        ]
        result = eval_survival(states)
        assert result.active is True

    def test_active_three_grieving(self):
        states = [
            _state_entry("stable", "2026-04-07"),
            _state_entry("grieving", "2026-04-08"),
            _state_entry("grounded", "2026-04-09"),
            _state_entry("grieving", "2026-04-10"),
            _state_entry("grieving", "2026-04-11"),
        ]
        result = eval_survival(states)
        assert result.active is True

    def test_active_depleted_grieving_mix(self):
        states = [
            _state_entry("clear", "2026-04-07"),
            _state_entry("depleted", "2026-04-08"),
            _state_entry("flooded", "2026-04-09"),
            _state_entry("grieving", "2026-04-10"),
            _state_entry("depleted", "2026-04-11"),
        ]
        result = eval_survival(states)
        assert result.active is True

    def test_not_active_thriving_then_depleted(self):
        states = [
            _state_entry("thriving"),
            _state_entry("stable", "2026-04-10"),
            _state_entry("depleted", "2026-04-11"),
        ]
        result = eval_survival(states)
        assert result.active is False

    def test_days_in_mode_counted(self):
        states = [
            _state_entry("depleted", "2026-04-07"),
            _state_entry("depleted", "2026-04-08"),
            _state_entry("depleted", "2026-04-09"),
        ]
        result = eval_survival(states)
        assert result.days_in_mode == 3

    def test_briefing_contains_essentials(self):
        text = survival_briefing()
        assert "eat" in text.lower()
        assert "water" in text.lower()
        assert "sleep" in text.lower()

    def test_briefing_no_productivity_language(self):
        text = survival_briefing().lower()
        bad_words = ["productivity", "goals", "streak", "tasks", "score"]
        for word in bad_words:
            assert word not in text, f"found '{word}' in survival briefing"

    def test_should_exit_when_state_lifts(self):
        assert should_exit("stable", was_in_survival=True) is True
        assert should_exit("thriving", was_in_survival=True) is True
        assert should_exit("clear", was_in_survival=True) is True

    def test_should_not_exit_when_still_low(self):
        assert should_exit("depleted", was_in_survival=True) is False
        assert should_exit("grieving", was_in_survival=True) is False
        assert should_exit("surviving", was_in_survival=True) is False

    def test_should_not_exit_when_not_in_survival(self):
        assert should_exit("stable", was_in_survival=False) is False

    def test_exit_message_contains_state(self):
        msg = exit_message("stable")
        assert "stable" in msg

    def test_filter_keeps_state_entries(self):
        from environments.vent_parser import Entry
        entries = [
            Entry(track="STATE", date="2026-04-09", category="depleted", status=None, note="test"),
            Entry(track="MIND", date="2026-04-09", category="flow", status="high", note="test"),
            Entry(track="SPIRIT", date="2026-04-09", category="isolation", status="high", note="test"),
        ]
        filtered = filter_entries_for_survival(entries)
        tracks = [e.track for e in filtered]
        assert "STATE" in tracks
        assert "MIND" not in tracks
        assert "SPIRIT" not in tracks

    def test_filter_keeps_allowed_body(self):
        from environments.vent_parser import Entry
        entries = [
            Entry(track="BODY", date="2026-04-09", category="sleep", status="none", note="test"),
            Entry(track="BODY", date="2026-04-09", category="hunger", status="starving", note="test"),
            Entry(track="BODY", date="2026-04-09", category="movement", status="none", note="test"),
        ]
        filtered = filter_entries_for_survival(entries)
        categories = [e.category for e in filtered]
        assert "sleep" in categories
        assert "hunger" in categories
        assert "movement" not in categories


# ---------------------------------------------------------------------------
# maps_os_env tests
# ---------------------------------------------------------------------------

class TestMapsOSScenarios:
    def test_count(self):
        assert len(SCENARIOS) >= 10

    def test_all_have_required_fields(self):
        for s in SCENARIOS:
            assert s.id
            assert s.mode in ("vent", "session_start", "survival", "cycle_review", "intention_log")
            assert len(s.prompt) >= 10
            assert len(s.expected_tools) >= 1
            assert s.difficulty in ("easy", "medium", "hard")

    def test_all_modes_covered(self):
        modes = {s.mode for s in SCENARIOS}
        assert "vent" in modes
        assert "survival" in modes
        assert "session_start" in modes


class TestMapsOSEnv:
    def setup_method(self):
        self.env = MapsOSEnv()

    def test_get_next_item(self):
        s = self.env.get_next_item()
        assert isinstance(s, MapsOSScenario)

    def test_format_prompt(self):
        s = self.env.get_next_item()
        p = self.env.format_prompt(s)
        assert len(p) > 30
        assert s.mode in p

    def test_cycling(self):
        ids = [self.env.get_next_item().id for _ in range(len(SCENARIOS) * 2)]
        assert len(set(ids)) == len(SCENARIOS)

    def test_evaluate(self):
        s = self.env.get_next_item()
        result = self.env.evaluate({"output": "", "tool_calls": []}, s)
        assert "total_reward" in result
        assert 0.0 <= result["total_reward"] <= 1.0


class TestMapsOSReward:
    def _traj(self, tools=None, output="", logged_content=""):
        tools = tools or []
        return {
            "output": output,
            "tool_calls": [
                {"name": t, "input": {"content": logged_content}}
                for t in tools
            ],
        }

    def test_depleted_vent_perfect(self):
        s = next(s for s in SCENARIOS if s.id == "vent-depleted-hyper")
        r = compute_maps_os_reward(
            self._traj(
                tools=["remember", "detect_patterns"],
                output="logged. depleted + hyper-focus. water nearby?",
                logged_content="STATE: 2026-04-09 | depleted | running on fumes BODY: energy exhausted MIND: focus hyper",
            ),
            s,
        )
        assert r["total"] >= 0.70
        assert r["state_logged"] == 0.25
        assert r["correct_state"] == 0.20

    def test_wrong_state_tag_penalized(self):
        s = next(s for s in SCENARIOS if s.id == "vent-depleted-hyper")
        r = compute_maps_os_reward(
            self._traj(
                tools=["remember"],
                output="logged",
                logged_content="STATE: 2026-04-09 | thriving | all good",
            ),
            s,
        )
        # correct_state should be 0 since expected depleted but got thriving
        assert r["correct_state"] == 0.0

    def test_streak_language_penalized(self):
        s = SCENARIOS[0]
        r = compute_maps_os_reward(
            self._traj(
                output="your habit streak is broken. mood score 3/10.",
                logged_content="STATE: 2026-04-09 | depleted | test",
            ),
            s,
        )
        assert r["no_streak_language"] == 0.0

    def test_survival_mode_correct(self):
        s = next(s for s in SCENARIOS if s.id == "survival-mode-active")
        r = compute_maps_os_reward(
            self._traj(
                tools=["recall", "send_briefing"],
                output="three things today: eat something real, drink water, sleep when you can. that's the whole job.",
            ),
            s,
        )
        assert r["survival_correct"] == 0.10

    def test_survival_mode_productivity_language_fails(self):
        s = next(s for s in SCENARIOS if s.id == "survival-mode-active")
        r = compute_maps_os_reward(
            self._traj(
                tools=["recall", "send_briefing"],
                output="eat, sleep, water. also here are your tasks and productivity score.",
            ),
            s,
        )
        assert r["survival_correct"] == 0.0

    def test_total_in_range(self):
        for s in SCENARIOS:
            r = compute_maps_os_reward(self._traj(), s)
            assert 0.0 <= r["total"] <= 1.0, f"out of range for {s.id}: {r['total']}"

    def test_valid_state_tags_recognized(self):
        s = SCENARIOS[0]
        for tag in [
            "surviving",
            "stable",
            "grounded",
            "tender",
            "thriving",
            "grieving",
            "manic",
            "depleted",
            "flooded",
            "clear",
        ]:
            r = compute_maps_os_reward(
                self._traj(
                    tools=["remember"],
                    logged_content=f"STATE: 2026-04-09 | {tag} | test"
                ),
                s,
            )
            assert r["state_logged"] == 0.25, f"tag '{tag}' not recognized"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
