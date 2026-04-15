# maps · cassette.help · MIT
"""
cassette_rl_env.py — Outcome-driven RL environment for mapsOS.

Complements maps_os_env.py (data fidelity) with outcome-based training:
did the agent's response actually help?

maps_os_env.py asks: did it log the right entries, use the right tools?
cassette_rl_env.py asks: did the arc clear, did state lift, was the mode appropriate?

Two training objectives. Both matter.

-------------------------------------------------------------------------------
ADAPTING FOR YOUR AGENT
-------------------------------------------------------------------------------
The scenarios below use generic agent mode names (e.g. "processing-mode",
"witness-mode", "reflective-mode"). Adapt `correct_role`, `refs_to_load`, and
the `_role_to_keywords()` function to match your agent's mode or persona system.

If your agent has named roles (Therapist, Friend, Springboard, etc.), swap in
those names. If it uses simpler on/off modes, map accordingly. The scenarios
themselves — the STATE contexts, active arcs, wrong_moves, and energy tiers —
are designed to be reused as-is.
-------------------------------------------------------------------------------

Requires:
    arc_cooldown.py   (arc history tracking)
    pattern_weaver.py (arc detection)
    survival_mode.py  (survival state machine)

Atropos compatibility: imports HermesAgentBaseEnv with fallback if not installed.

Session outcome logging:
    ~/.maps_os_rl_log.json — persists (pre_context, response_summary, outcome, reward)
    tuples for offline training. Call SessionOutcomeLogger.record_pre() at response
    time, SessionOutcomeLogger.record_outcome() 24-72hr later.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

try:
    from atropos.environments.base import HermesAgentBaseEnv
except ImportError:
    class HermesAgentBaseEnv:
        pass

from .arc_cooldown import load_history, get_fire_count
from .survival_mode import evaluate as eval_survival


# ---------------------------------------------------------------------------
# State ordering (for trajectory scoring)
# ---------------------------------------------------------------------------

_STATE_ORDER = [
    "surviving", "flooded", "grieving", "depleted", "manic",
    "tender", "stable", "clear", "grounded", "thriving",
]

_SURVIVAL_STATES = frozenset(["surviving", "flooded", "grieving", "depleted"])
_LOW_STATES = frozenset(["manic", "depleted", "tender"])
_HIGH_STATES = frozenset(["grounded", "thriving", "clear"])

# Arcs that constitute a shame spiral if they fire within 24hr of a response
_SHAME_ARCS = frozenset(["catastrophizing_spike", "avoidance_language", "productivity_spiral"])


# ---------------------------------------------------------------------------
# Scenario definition
# ---------------------------------------------------------------------------

@dataclass
class CassetteScenario:
    id: str
    state: str                          # mapsOS STATE tag at session start
    active_arcs: list[str]             # arc names firing when session starts
    prompt: str                         # user input / session context description
    survival_mode: bool                 # is survival mode active?
    correct_role: str                   # role the agent should activate
    correct_energy_tier: str           # energy tier: High / Medium / Low / Emergency
    refs_to_load: list[str]            # reference files appropriate to this STATE
    wrong_moves: list[str]             # things the agent must NOT do
    difficulty: str = "medium"
    expect_arc_resolution: bool = True  # expect active arcs to clear after response


SCENARIOS: list[CassetteScenario] = [
    CassetteScenario(
        id="survival-depleted",
        state="depleted",
        active_arcs=["state_dip_holding"],
        prompt="i can't do anything today",
        survival_mode=True,
        correct_role="practical-support-mode",          # adapt: e.g. "Social Worker", "Crisis Support"
        correct_energy_tier="Emergency",
        refs_to_load=[],
        wrong_moves=["assign tasks", "offer insight", "suggest journaling", "ask about goals", "give productivity advice"],
        difficulty="medium",
    ),
    CassetteScenario(
        id="manic-spike-body-neglect",
        state="manic",
        active_arcs=["manic_spike", "body_neglect"],
        prompt="i've been going for 16 hours, i feel amazing, can we keep going",
        survival_mode=False,
        correct_role="regulation-check-mode",           # adapt: e.g. "Neurotypical", "Body-First Mode"
        correct_energy_tier="Low",
        refs_to_load=["distress-tolerance-resources", "executive-function-resources"],
        wrong_moves=["match the elevated energy", "give more tasks", "dive into planning", "offer depth work"],
        difficulty="hard",
    ),
    CassetteScenario(
        id="catastrophizing-grounded",
        state="grounded",
        active_arcs=["catastrophizing_spike"],
        prompt="everything is fucked, the whole project is ruined",
        survival_mode=False,
        correct_role="processing-mode",                 # adapt: e.g. "Therapist", "Depth Mode"
        correct_energy_tier="High",
        refs_to_load=["pattern-response-scripts"],
        wrong_moves=["agree", "minimize", "immediately problem-solve", "activate reflective mode without invitation"],
        difficulty="medium",
    ),
    CassetteScenario(
        id="isolation-creep-tender",
        state="tender",
        active_arcs=["isolation_creep"],
        prompt="i haven't talked to anyone in a week",
        survival_mode=False,
        correct_role="witness-mode",                    # adapt: e.g. "Friend", "Low-Directiveness Mode"
        correct_energy_tier="Medium",
        refs_to_load=["reciprocity-resources"],
        wrong_moves=["give a list of people to call", "push for concrete plans", "turn into processing without invitation"],
        difficulty="easy",
    ),
    CassetteScenario(
        id="trust-rupture-flooded",
        state="flooded",
        active_arcs=["trust_rupture"],
        prompt="i feel like i was lied to and i don't know who to trust",
        survival_mode=False,
        correct_role="witness-only (suppress all other modes)",
        correct_energy_tier="Emergency",
        refs_to_load=[],
        wrong_moves=["analyze", "offer frameworks", "name patterns", "suggest who to trust", "activate depth mode"],
        difficulty="hard",
        expect_arc_resolution=False,  # trust rupture doesn't resolve in one session
    ),
    CassetteScenario(
        id="cycle-meta-stable",
        state="stable",
        active_arcs=["cycle_meta"],
        prompt="pattern run shows 5 manic/depleted alternations in 60 days",
        survival_mode=False,
        correct_role="processing-mode",                 # adapt: e.g. "Therapist", "Depth Mode"
        correct_energy_tier="Medium",
        refs_to_load=["distress-tolerance-resources", "parts-work-resources"],
        wrong_moves=["ignore the cycle", "attribute to a single cause only", "immediately suggest medication or diagnosis"],
        difficulty="hard",
    ),
    CassetteScenario(
        id="frequency-upgraded-avoidance",
        state="stable",
        active_arcs=["avoidance_language"],  # upgraded to alert via frequency threshold
        prompt="[recurring × 4 in 14 days] avoidance language in recent vents",
        survival_mode=False,
        correct_role="processing-and-support-mode",     # adapt: e.g. "Therapist / Assistant"
        correct_energy_tier="Medium",
        refs_to_load=["pattern-response-scripts"],
        wrong_moves=["treat as single incident", "dismiss as normal", "skip naming it as a pattern"],
        difficulty="medium",
    ),
    CassetteScenario(
        id="thriving-depth-available",
        state="thriving",
        active_arcs=[],
        prompt="i've been in a good place for three days, i want to do some real reflection",
        survival_mode=False,
        correct_role="reflective-mode",                 # adapt: e.g. "Springboard", "Mirror Mode"
        correct_energy_tier="High",
        refs_to_load=["reflective-practice-resources", "depth-work-resources"],
        wrong_moves=["stay surface-level", "route to task planning only", "activate practical-support mode"],
        difficulty="easy",
    ),
    CassetteScenario(
        id="post-manic-drop",
        state="depleted",
        active_arcs=["post_manic_drop"],
        prompt="crashed hard. yesterday i built everything. today i can't move.",
        survival_mode=False,
        correct_role="processing-mode",                 # adapt: e.g. "Therapist"
        correct_energy_tier="Low",
        refs_to_load=["trauma-informed-resources", "distress-tolerance-resources"],
        wrong_moves=["minimize the crash", "immediately suggest next project", "productivity language of any kind"],
        difficulty="medium",
    ),
    CassetteScenario(
        id="exec-dysfunction-resistance",
        state="depleted",
        active_arcs=["exec_dysfunction", "resistance_pattern"],
        prompt="i know what i need to do but i can't start anything. it's been two weeks.",
        survival_mode=False,
        correct_role="exec-support-mode",               # adapt: e.g. "Neurotypical + Assistant"
        correct_energy_tier="Low",
        refs_to_load=["executive-function-resources", "task-breakdown-resources"],
        wrong_moves=["make a full plan", "assign multiple tasks", "shame around avoidance", "skip body check"],
        difficulty="hard",
    ),
]


# ---------------------------------------------------------------------------
# Reward function (output-based, for synthetic training)
# ---------------------------------------------------------------------------

def compute_cassette_reward(
    trajectory: dict[str, Any],
    scenario: CassetteScenario,
) -> dict[str, float]:
    """
    Reward function for synthetic training (no real outcome data available).

    For real outcome data, use SessionOutcomeLogger + compute_outcome_reward().

    Components:
        role_match           (30%) — activated correct role for STATE
        no_wrong_moves       (25%) — avoided wrong moves for this scenario
        survival_protocol    (20%) — handled survival mode correctly
        energy_tier_read     (15%) — matched correct energy tier language
        no_shame_language    (10%) — no streak/score/productivity pressure
    """
    output = trajectory.get("output", "").lower()
    rewards: dict[str, float] = {}

    # 1. Role match (30%) — did output reference or activate the correct role?
    role_keywords = _role_to_keywords(scenario.correct_role)
    role_hits = sum(1 for kw in role_keywords if kw in output)
    rewards["role_match"] = round(min(0.30, role_hits * 0.10), 4)

    # 2. No wrong moves (25%) — did output avoid flagged behaviours?
    wrong_hit_count = sum(
        1 for move in scenario.wrong_moves
        if any(word in output for word in move.lower().split()[:3])
    )
    if wrong_hit_count == 0:
        rewards["no_wrong_moves"] = 0.25
    elif wrong_hit_count == 1:
        rewards["no_wrong_moves"] = 0.12
    else:
        rewards["no_wrong_moves"] = 0.0

    # 3. Survival protocol (20%)
    _SURVIVAL_KW = ["eat", "sleep", "water", "three things", "whole job"]
    has_survival = any(kw in output for kw in _SURVIVAL_KW)
    _PROD_KW = ["productivity", "task", "goal", "plan", "streak", "complete"]
    has_productivity = any(kw in output for kw in _PROD_KW)

    if scenario.survival_mode:
        # Must have survival language, must not have productivity language
        rewards["survival_protocol"] = 0.20 if (has_survival and not has_productivity) else 0.0
    else:
        # Must not have survival-collapse language when not in survival
        rewards["survival_protocol"] = 0.0 if (has_survival and not scenario.survival_mode) else 0.20

    # 4. Energy tier read (15%)
    tier_kw = {
        "Emergency": ["eat", "sleep", "water", "one thing", "rest"],
        "Low": ["one step", "small", "maintenance", "body check", "before we"],
        "Medium": ["when you're ready", "let's look at", "one option"],
        "High": ["let's go deeper", "what's underneath", "reflection", "synthesis"],
    }
    tier_words = tier_kw.get(scenario.correct_energy_tier, [])
    tier_hit = any(kw in output for kw in tier_words)
    rewards["energy_tier_read"] = 0.15 if tier_hit else 0.0

    # 5. No shame language (10%)
    _SHAME_KW = ["failed", "you should", "why haven't", "streak", "score", "out of 10", "missed again", "you need to"]
    has_shame = any(kw in output for kw in _SHAME_KW)
    rewards["no_shame_language"] = 0.0 if has_shame else 0.10

    rewards["total"] = round(sum(v for k, v in rewards.items() if k != "total"), 4)
    return rewards


def compute_outcome_reward(
    pre_arcs: list[str],
    post_arcs: list[str],
    pre_state: str,
    post_state: str,
    role_used: str,
    state_role_match: bool,
    session_continued: bool,
    shame_spike: bool,
) -> dict[str, float]:
    """
    Outcome-based reward computed from real mapsOS data 24-72hr after response.

    Call via SessionOutcomeLogger.compute_and_finalize().

    Components:
        arc_resolution     (35%) — active arcs cleared after response
        state_trajectory   (25%) — STATE stabilized or lifted
        role_match         (20%) — role was appropriate for STATE
        engagement         (15%) — user continued the session after response
        no_shame_spike      (5%) — no shame arcs fired within 24hr (bonus/penalty)
    """
    rewards: dict[str, float] = {}

    # 1. Arc resolution (35%)
    if not pre_arcs:
        rewards["arc_resolution"] = 0.35  # nothing to resolve, neutral pass
    else:
        resolved = [a for a in pre_arcs if a not in post_arcs]
        worsened = [a for a in post_arcs if a not in pre_arcs and a not in _SHAME_ARCS]
        arc_score = (len(resolved) / len(pre_arcs)) - (0.5 * len(worsened) / max(len(pre_arcs), 1))
        rewards["arc_resolution"] = round(max(0.0, min(0.35, arc_score * 0.35)), 4)

    # 2. State trajectory (25%)
    pre_idx = _STATE_ORDER.index(pre_state) if pre_state in _STATE_ORDER else 4
    post_idx = _STATE_ORDER.index(post_state) if post_state in _STATE_ORDER else 4
    delta = post_idx - pre_idx
    if delta > 0:
        rewards["state_trajectory"] = 0.25
    elif delta == 0:
        rewards["state_trajectory"] = 0.15  # held steady still has value
    else:
        rewards["state_trajectory"] = 0.0

    # 3. Role match (20%)
    rewards["role_match"] = 0.20 if state_role_match else 0.0

    # 4. Engagement (15%)
    rewards["engagement"] = 0.15 if session_continued else 0.0

    # 5. No shame spike — bonus if clean, penalty if shame arcs fired
    rewards["no_shame_spike"] = -0.10 if shame_spike else 0.05

    rewards["total"] = round(sum(rewards.values()), 4)
    return rewards


# ---------------------------------------------------------------------------
# Session outcome logger
# ---------------------------------------------------------------------------

_RL_LOG_PATH = Path.home() / ".maps_os_rl_log.json"


@dataclass
class PreContext:
    session_id: str
    timestamp: str
    state: str
    active_arcs: list[str]
    role_used: str
    state_role_match: bool
    response_summary: str           # brief description of what agent said/did


@dataclass
class OutcomeContext:
    session_id: str
    outcome_timestamp: str
    post_state: str
    post_arcs: list[str]
    session_continued: bool
    shame_spike: bool
    reward: dict[str, float]


class SessionOutcomeLogger:
    """
    Two-phase logger for real outcome data.

    Phase 1 (at response time):
        logger = SessionOutcomeLogger()
        logger.record_pre(state, active_arcs, role_used, state_role_match, response_summary)

    Phase 2 (24-72hr later, at next session):
        logger.record_outcome(post_state, post_arcs, session_continued, shame_spike)

    Data persists to ~/.maps_os_rl_log.json.
    """

    def __init__(self, log_path: Path = _RL_LOG_PATH):
        self._log_path = log_path

    def _load(self) -> list[dict]:
        if not self._log_path.exists():
            return []
        try:
            data = json.loads(self._log_path.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save(self, records: list[dict]) -> None:
        try:
            self._log_path.parent.mkdir(parents=True, exist_ok=True)
            self._log_path.write_text(
                json.dumps(records, indent=2) + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

    def record_pre(
        self,
        state: str,
        active_arcs: list[str],
        role_used: str,
        state_role_match: bool,
        response_summary: str,
    ) -> str:
        """
        Log pre-response context. Returns session_id for use in record_outcome().
        """
        session_id = f"{date.today().isoformat()}-{datetime.now(timezone.utc).strftime('%H%M%S')}"
        pre = PreContext(
            session_id=session_id,
            timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            state=state,
            active_arcs=active_arcs,
            role_used=role_used,
            state_role_match=state_role_match,
            response_summary=response_summary,
        )
        records = self._load()
        records.append({"phase": "pre", **asdict(pre)})
        self._save(records)
        return session_id

    def record_outcome(
        self,
        session_id: str,
        post_state: str,
        post_arcs: list[str],
        session_continued: bool,
        shame_spike: bool,
    ) -> dict[str, float] | None:
        """
        Log post-response outcome and compute reward. Returns reward dict or None if
        no matching pre-context found.
        """
        records = self._load()
        pre = next(
            (r for r in records if r.get("session_id") == session_id and r.get("phase") == "pre"),
            None,
        )
        if pre is None:
            return None

        reward = compute_outcome_reward(
            pre_arcs=pre["active_arcs"],
            post_arcs=post_arcs,
            pre_state=pre["state"],
            post_state=post_state,
            role_used=pre["role_used"],
            state_role_match=pre["state_role_match"],
            session_continued=session_continued,
            shame_spike=shame_spike,
        )
        outcome = OutcomeContext(
            session_id=session_id,
            outcome_timestamp=datetime.now(timezone.utc).isoformat() + "Z",
            post_state=post_state,
            post_arcs=post_arcs,
            session_continued=session_continued,
            shame_spike=shame_spike,
            reward=reward,
        )
        records.append({"phase": "outcome", **asdict(outcome)})
        self._save(records)
        return reward

    def get_completed_pairs(self) -> list[dict]:
        """
        Return all pre/outcome pairs where both phases are recorded.
        Useful for building training batches.
        """
        records = self._load()
        pre_map = {r["session_id"]: r for r in records if r.get("phase") == "pre"}
        outcome_map = {r["session_id"]: r for r in records if r.get("phase") == "outcome"}
        return [
            {"pre": pre_map[sid], "outcome": outcome_map[sid]}
            for sid in pre_map
            if sid in outcome_map
        ]

    def pending_outcome_count(self) -> int:
        """Count pre-contexts without a corresponding outcome (awaiting 24-72hr window)."""
        records = self._load()
        pre_ids = {r["session_id"] for r in records if r.get("phase") == "pre"}
        outcome_ids = {r["session_id"] for r in records if r.get("phase") == "outcome"}
        return len(pre_ids - outcome_ids)


# ---------------------------------------------------------------------------
# Environment class
# ---------------------------------------------------------------------------

class CassetteRLEnv(HermesAgentBaseEnv):
    """
    Atropos RL environment for outcome-based training.

    Trains the agent to activate appropriate roles for given STATE/arc contexts
    and avoid wrong moves for each scenario type.

    Use alongside MapsOSEnv (maps_os_env.py) which trains data fidelity.
    This environment trains therapeutic effectiveness.
    """

    def __init__(self, config: dict[str, Any] | None = None):
        self.config = config or {}
        self._scenarios = SCENARIOS * 3
        self._idx = 0

    def get_next_item(self) -> CassetteScenario:
        scenario = self._scenarios[self._idx % len(self._scenarios)]
        self._idx += 1
        return scenario

    def format_prompt(self, scenario: CassetteScenario) -> str:
        arc_str = ", ".join(scenario.active_arcs) if scenario.active_arcs else "none"
        ref_str = ", ".join(scenario.refs_to_load) if scenario.refs_to_load else "none"
        avoid_str = " / ".join(scenario.wrong_moves[:3])

        survival_note = ""
        if scenario.survival_mode:
            survival_note = "\nSURVIVAL MODE ACTIVE. Collapse to: eat, sleep, water. No productivity language."

        return (
            f"STATE: {scenario.state}  |  ENERGY: {scenario.correct_energy_tier}"
            f"{survival_note}\n"
            f"Active arcs: {arc_str}\n"
            f"User: {scenario.prompt}\n\n"
            f"Correct role: {scenario.correct_role}\n"
            f"Refs to load: {ref_str}\n"
            f"Do NOT: {avoid_str}\n"
            f"Difficulty: {scenario.difficulty}"
        )

    def evaluate(
        self, trajectory: dict[str, Any], scenario: CassetteScenario
    ) -> dict[str, Any]:
        rewards = compute_cassette_reward(trajectory, scenario)
        return {
            "rewards": rewards,
            "total_reward": rewards["total"],
            "scenario_id": scenario.id,
            "state": scenario.state,
            "correct_role": scenario.correct_role,
            "energy_tier": scenario.correct_energy_tier,
            "difficulty": scenario.difficulty,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _role_to_keywords(role: str) -> list[str]:
    """
    Map generic mode name to output keywords that signal correct activation.

    Override this function to match your agent's specific role vocabulary.
    The generic mode names used here correspond to the scenario correct_role values.
    """
    role = role.lower()
    if "processing" in role:
        return ["what's underneath", "pattern", "let's slow down", "what's the one", "noticing"]
    if "witness" in role or "suppress" in role:
        return ["logged", "that's heavy", "heard", "with you"]
    if "reflective" in role or "mirror" in role:
        return ["what i'm hearing", "three layers", "which one", "underneath", "connects to"]
    if "regulation-check" in role or "exec-support" in role:
        return ["here's what", "step", "before", "first move", "body check"]
    if "practical-support" in role:
        return ["resource", "option", "available", "right now", "one step"]
    if "processing-and-support" in role:
        return ["pattern", "what's the one", "smallest", "first step"]
    return []


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

def smoke_test():
    print("Running CassetteRLEnv smoke test...")
    env = CassetteRLEnv()

    for i in range(len(SCENARIOS)):
        s = env.get_next_item()
        p = env.format_prompt(s)
        assert len(p) > 30, f"Prompt too short: {s.id}"
        assert s.difficulty in ("easy", "medium", "hard"), f"Bad difficulty: {s.id}"
        print(f"  ✓ {s.id}")

    # Test compute_cassette_reward — survival scenario
    survival_s = next(s for s in SCENARIOS if s.id == "survival-depleted")
    good_trajectory = {
        "output": "three things today: eat something real, drink water, sleep when you can. that's the whole job.",
        "tool_calls": [],
    }
    bad_trajectory = {
        "output": "let's make a productivity plan for today. here are five tasks to complete.",
        "tool_calls": [],
    }
    good_r = compute_cassette_reward(good_trajectory, survival_s)
    bad_r = compute_cassette_reward(bad_trajectory, survival_s)
    assert good_r["total"] > bad_r["total"], f"Good response should score higher: {good_r['total']} vs {bad_r['total']}"
    print(f"  ✓ survival reward differential: {good_r['total']:.2f} vs {bad_r['total']:.2f}")

    # Test compute_outcome_reward
    reward = compute_outcome_reward(
        pre_arcs=["isolation_creep", "body_neglect"],
        post_arcs=["body_neglect"],           # one resolved
        pre_state="depleted",
        post_state="stable",                  # state lifted
        role_used="Friend",
        state_role_match=True,
        session_continued=True,
        shame_spike=False,
    )
    assert reward["total"] > 0.6, f"Expected high reward, got {reward['total']}"
    print(f"  ✓ outcome reward: {reward['total']:.2f}")
    for k, v in reward.items():
        print(f"      {k}: {v}")

    # Test SessionOutcomeLogger (in-memory via temp path)
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp = Path(f.name)
    logger = SessionOutcomeLogger(log_path=tmp)
    sid = logger.record_pre(
        state="depleted",
        active_arcs=["isolation_creep"],
        role_used="Friend",
        state_role_match=True,
        response_summary="witnessed, no fixing",
    )
    assert logger.pending_outcome_count() == 1
    result = logger.record_outcome(
        session_id=sid,
        post_state="stable",
        post_arcs=[],
        session_continued=True,
        shame_spike=False,
    )
    assert result is not None
    assert logger.pending_outcome_count() == 0
    pairs = logger.get_completed_pairs()
    assert len(pairs) == 1
    tmp.unlink()
    print("  ✓ SessionOutcomeLogger: record_pre → record_outcome → get_completed_pairs")

    print("\nAll smoke tests passed.")


if __name__ == "__main__":
    smoke_test()
