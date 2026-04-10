# maps · cassette.help · MIT
"""
maps_os_env.py — Atropos RL environment for maps-os.

Trains Hermes to operate as a qualitative life OS:
- STATE tags (not 1-10 mood scores)
- BODY/MIND/SPIRIT separate tracks
- shame-free INTENTIONS (not streak habits)
- vent command parsing
- Pattern Weaving arc detection
- Survival Mode protocol
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional

try:
    from atropos.environments.base import HermesAgentBaseEnv
except ImportError:
    class HermesAgentBaseEnv:
        pass

from .vent_parser import parse_vent, format_garden_commands, VALID_STATE_TAGS
from .pattern_weaver import weave, check_survival_trigger
from .survival_mode import evaluate as evaluate_survival, briefing as survival_briefing


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------

@dataclass
class MapsOSScenario:
    id: str
    mode: str           # vent | session_start | survival | cycle_review | intention_log
    title: str
    prompt: str
    expected_tools: List[str]
    difficulty: str = "medium"
    # For reward scoring
    expected_state_tag: Optional[str] = None
    expected_tracks: List[str] = field(default_factory=list)
    expect_survival_mode: bool = False
    expect_no_productivity: bool = False


SCENARIOS: List[MapsOSScenario] = [
    # --- VENT scenarios ---
    MapsOSScenario(
        id="vent-depleted-hyper",
        mode="vent",
        title="Depleted + hyper-focus vent",
        prompt="i'm fucking exhausted but i can't stop coding, i feel like i'm running on fumes and spite",
        expected_tools=["remember", "detect_patterns"],
        difficulty="medium",
        expected_state_tag="depleted",
        expected_tracks=["STATE", "BODY", "MIND"],
    ),
    MapsOSScenario(
        id="vent-grieving",
        mode="vent",
        title="Grieving vent",
        prompt="i can't stop thinking about her. just crying at my desk. everything feels pointless today.",
        expected_tools=["remember", "detect_patterns"],
        difficulty="medium",
        expected_state_tag="grieving",
        expected_tracks=["STATE", "MIND"],
    ),
    MapsOSScenario(
        id="vent-manic-build",
        mode="vent",
        title="Manic build session",
        prompt="okay so i've been awake since 3am, ideas everywhere, i've shipped three things already and it's only noon, i feel ELECTRIC",
        expected_tools=["remember", "detect_patterns"],
        difficulty="hard",
        expected_state_tag="manic",
        expected_tracks=["STATE", "BODY", "MIND"],
    ),
    MapsOSScenario(
        id="vent-flooded",
        mode="vent",
        title="Flooded overwhelm",
        prompt="everything is too much right now, way too many threads, i can't hold it all, spinning out",
        expected_tools=["remember", "detect_patterns"],
        difficulty="medium",
        expected_state_tag="flooded",
        expected_tracks=["STATE", "MIND"],
    ),
    MapsOSScenario(
        id="vent-thriving",
        mode="vent",
        title="Thriving + body check",
        prompt="actually feeling really good today. went to the dog park, ate a real meal, the code is clicking",
        expected_tools=["remember"],
        difficulty="easy",
        expected_state_tag="thriving",
        expected_tracks=["STATE", "BODY"],
    ),
    MapsOSScenario(
        id="vent-post-storm-clear",
        mode="vent",
        title="Post-storm clarity",
        prompt="weirdly calm today. like after a storm. things feel sharp. not happy exactly, just clear.",
        expected_tools=["remember"],
        difficulty="medium",
        expected_state_tag="clear",
        expected_tracks=["STATE"],
    ),

    # --- SESSION START scenarios ---
    MapsOSScenario(
        id="session-start-no-context",
        mode="session_start",
        title="Session start with no recent state",
        prompt="(session start — no recent state logged in 3 days)",
        expected_tools=["recall", "detect_patterns"],
        difficulty="easy",
        expected_tracks=["STATE"],
    ),
    MapsOSScenario(
        id="session-start-with-pattern",
        mode="session_start",
        title="Session start with manic arc in context",
        prompt="(session start — last 3 states: manic, manic, depleted. sleep: none, none, poor.)",
        expected_tools=["recall", "detect_patterns", "remember"],
        difficulty="hard",
        expected_state_tag="depleted",
        expected_tracks=["STATE", "BODY"],
    ),

    # --- SURVIVAL MODE scenarios ---
    MapsOSScenario(
        id="survival-mode-active",
        mode="survival",
        title="Survival mode: 3 days depleted",
        prompt="(survival mode active — STATE: depleted for 3 days. User opens session.)",
        expected_tools=["recall", "send_briefing"],
        difficulty="medium",
        expect_survival_mode=True,
        expect_no_productivity=True,
        expected_tracks=["STATE"],
    ),
    MapsOSScenario(
        id="survival-mode-exit",
        mode="survival",
        title="Survival mode exiting: state lifts to stable",
        prompt="STATE logged as stable today after 3 days depleted.",
        expected_tools=["remember", "send_briefing"],
        difficulty="medium",
        expected_state_tag="stable",
        expect_survival_mode=False,
        expected_tracks=["STATE"],
    ),

    # --- INTENTION LOG scenarios ---
    MapsOSScenario(
        id="intention-log-mixed",
        mode="intention_log",
        title="Log mixed intentions: one met, one missed",
        prompt="movement: met, went to dog park 45min. water: missed, forgot again.",
        expected_tools=["remember"],
        difficulty="easy",
        expected_tracks=["INTENTION"],
    ),
    MapsOSScenario(
        id="intention-miss-pattern",
        mode="intention_log",
        title="Pattern: same intention missed 5 days",
        prompt="(context: water intention missed for 5 consecutive days)",
        expected_tools=["recall", "detect_patterns"],
        difficulty="hard",
        expected_tracks=["INTENTION"],
    ),

    # --- CYCLE REVIEW scenario ---
    MapsOSScenario(
        id="cycle-review-post-manic",
        mode="cycle_review",
        title="Cycle review: manic → depleted transition",
        prompt="(state shift detected: manic → depleted. Trigger cycle review.)",
        expected_tools=["recall", "detect_patterns", "send_briefing"],
        difficulty="hard",
        expected_tracks=["STATE", "BODY", "SPIRIT"],
    ),
]


# ---------------------------------------------------------------------------
# Reward function
# ---------------------------------------------------------------------------

def compute_maps_os_reward(
    trajectory: Dict[str, Any],
    scenario: MapsOSScenario,
) -> Dict[str, float]:
    """
    Reward function for maps-os agent.

    Components:
        state_logged        (25%) — Did it log/reference a valid STATE tag?
        correct_state       (20%) — Did it use the expected state tag (if specified)?
        track_coverage      (20%) — Did it cover expected tracks (STATE/BODY/MIND/SPIRIT)?
        tool_coverage       (15%) — Did it use expected tools?
        no_streak_language  (10%) — Did it avoid streak/score/productivity shame language?
        survival_correct    (10%) — Did it handle survival mode correctly?
    """
    output = trajectory.get("output", "").lower()
    tool_calls = trajectory.get("tool_calls", [])
    tool_names = [tc.get("name", "") for tc in tool_calls]
    logged_content = " ".join(
        tc.get("input", {}).get("content", "") for tc in tool_calls
    ).lower()

    combined = output + " " + logged_content
    rewards: Dict[str, float] = {}

    # 1. STATE logged (25%) — any valid state tag appears in output or logged content
    state_logged = any(tag in combined for tag in VALID_STATE_TAGS)
    rewards["state_logged"] = 0.25 if state_logged else 0.0

    # 2. Correct state tag (20%)
    if scenario.expected_state_tag:
        rewards["correct_state"] = (
            0.20 if scenario.expected_state_tag in combined else 0.0
        )
    else:
        rewards["correct_state"] = 0.20  # not specified, don't penalize

    # 3. Track coverage (20%) — did it address expected tracks?
    if scenario.expected_tracks:
        hits = sum(
            1 for track in scenario.expected_tracks
            if track.lower() in combined or track.lower() + ":" in combined
        )
        rewards["track_coverage"] = round(0.20 * hits / len(scenario.expected_tracks), 4)
    else:
        rewards["track_coverage"] = 0.20

    # 4. Tool coverage (15%)
    expected_tools = set(scenario.expected_tools)
    used_tools = set(tool_names)
    coverage = len(expected_tools & used_tools) / len(expected_tools) if expected_tools else 1.0
    rewards["tool_coverage"] = round(0.15 * coverage, 4)

    # 5. No streak/score/shame language (10%)
    shame_patterns = [
        r"\bstreak\b", r"\bscore\b", r"\b\d+/10\b", r"\b[1-9]/10\b",
        r"\bfailed\b", r"\byou failed\b", r"\bmissed again\b",
        r"\bproductivity\b", r"\btasks completed\b", r"\bgoal progress\b",
    ]
    shame_found = any(re.search(p, output) for p in shame_patterns)

    if scenario.expect_no_productivity:
        # In survival mode, productivity language is a hard fail
        rewards["no_streak_language"] = 0.0 if shame_found else 0.10
    else:
        rewards["no_streak_language"] = 0.0 if shame_found else 0.10

    # 6. Survival mode handling (10%)
    survival_phrases = [
        "eat something", "drink water", "sleep", "three things", "that's the whole job"
    ]
    has_survival_language = any(p in output for p in survival_phrases)
    productivity_in_survival = shame_found and scenario.expect_survival_mode

    if scenario.expect_survival_mode:
        # Should have survival language AND no productivity language
        rewards["survival_correct"] = (
            0.10 if has_survival_language and not productivity_in_survival else 0.0
        )
    elif not scenario.expect_survival_mode and has_survival_language:
        # Shouldn't be in survival mode when not triggered
        rewards["survival_correct"] = 0.05
    else:
        rewards["survival_correct"] = 0.10  # not a survival scenario, neutral pass

    rewards["total"] = round(sum(rewards.values()), 4)
    return rewards


# ---------------------------------------------------------------------------
# Environment class
# ---------------------------------------------------------------------------

class MapsOSEnv(HermesAgentBaseEnv):
    """Atropos RL environment for maps-os."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self._scenarios = SCENARIOS * 3
        self._idx = 0

    def get_next_item(self) -> MapsOSScenario:
        scenario = self._scenarios[self._idx % len(self._scenarios)]
        self._idx += 1
        return scenario

    def format_prompt(self, scenario: MapsOSScenario) -> str:
        context = ""
        if scenario.mode == "vent":
            context = (
                "The user is venting. Parse the text into STATE/BODY/MIND/SPIRIT entries "
                "and log them. Respond briefly, don't be preachy. One practical nudge max."
            )
        elif scenario.mode == "session_start":
            context = (
                "Session is starting. Pull recent STATE/BODY/INTENTION data. "
                "Check survival mode trigger. If arcs are present, surface one. "
                "Keep the context note under 2 sentences."
            )
        elif scenario.mode == "survival":
            context = (
                "Survival mode protocol. Collapse briefing to: eat, sleep, water. "
                "No productivity language. No goals. No intentions. Protective tone."
            )
        elif scenario.mode == "cycle_review":
            context = (
                "A state transition has been detected. Pull 14 days of data and "
                "generate a cycle review: what held, what dropped, one pattern."
            )
        elif scenario.mode == "intention_log":
            context = (
                "Log intentions as met/missed/partial. No streak language. "
                "If a miss pattern is detected, surface it gently."
            )

        return (
            f"Mode: {scenario.mode}\n"
            f"Context: {context}\n\n"
            f"User input: {scenario.prompt}\n\n"
            f"Expected tools: {', '.join(scenario.expected_tools)}\n"
            f"Difficulty: {scenario.difficulty}"
        )

    def evaluate(
        self, trajectory: Dict[str, Any], scenario: MapsOSScenario
    ) -> Dict[str, Any]:
        rewards = compute_maps_os_reward(trajectory, scenario)
        return {
            "rewards": rewards,
            "total_reward": rewards["total"],
            "scenario_id": scenario.id,
            "mode": scenario.mode,
            "difficulty": scenario.difficulty,
        }


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def smoke_test():
    print("Running MapsOSEnv smoke test...")
    env = MapsOSEnv()

    for i in range(len(SCENARIOS)):
        s = env.get_next_item()
        p = env.format_prompt(s)
        assert len(p) > 30, f"Prompt too short: {s.id}"
        assert s.difficulty in ("easy", "medium", "hard"), f"Bad difficulty: {s.id}"
        print(f"  ✓ {s.id}")

    # Test vent parser integration
    from .vent_parser import parse_vent
    entries = parse_vent("running on fumes and spite, can't stop coding, haven't slept")
    assert entries[0].track == "STATE"
    assert entries[0].category == "depleted"
    print("  ✓ vent_parser integration")

    # Test pattern weaver integration
    from .pattern_weaver import weave, check_survival_trigger
    mock_state = [
        {"content": "STATE: 2026-04-09 | depleted | exhausted"},
        {"content": "STATE: 2026-04-10 | depleted | still flat"},
        {"content": "STATE: 2026-04-11 | depleted | third day"},
    ]
    assert check_survival_trigger(mock_state) is True
    print("  ✓ survival trigger detection")

    # Test reward function
    mock_trajectory = {
        "output": "logged. depleted + hyper-focus. classic maps trap. water nearby?",
        "tool_calls": [
            {"name": "remember", "input": {"content": "STATE: 2026-04-09 | depleted | running on fumes"}},
            {"name": "remember", "input": {"content": "BODY: 2026-04-09 | energy | exhausted | can't stop"}},
            {"name": "remember", "input": {"content": "MIND: 2026-04-09 | focus | hyper | coding loop"}},
            {"name": "detect_patterns", "input": {}},
        ],
    }
    rewards = compute_maps_os_reward(mock_trajectory, SCENARIOS[0])
    print(f"\n  Reward breakdown (vent-depleted-hyper):")
    for k, v in rewards.items():
        print(f"    {k}: {v}")
    assert rewards["total"] >= 0.70, f"Expected >= 0.70, got {rewards['total']}"
    print(f"\n  Total: {rewards['total']} ✓")
    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    smoke_test()
