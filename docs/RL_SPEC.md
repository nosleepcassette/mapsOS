# mapsOS RL Training Spec
# maps · cassette.help · MIT
# 2026-04-14

---

## What This Is For

The existing `life_os_env.py` (from hermes-maps-os) was a proof of concept — generic scenarios, generic users, generic reward signals. It has no idea who maps is, what her arcs are, or what "a good Cassette response" actually looks like.

This spec defines the real RL environment: one that trains Cassette to be better at her actual job, using real mapsOS signal as the feedback loop.

---

## The Core Problem

Cassette currently has no feedback loop. She responds to STATE/arc data, but she doesn't know:

- Whether her response helped (did the arc clear?)
- Whether she picked the right role (did maps engage, or shut down?)
- Whether the energy tier was correctly read (did maps complete a task or spiral?)
- Whether depth work was appropriate (did maps log something positive after a Jungian session, or go quiet for 3 days?)

Without feedback, she can't improve. She repeats the same patterns whether they work or not.

---

## What "Better" Means for Cassette

Not generic helpfulness. Specifically:

1. **Arc resolution** — the arc stops firing within a reasonable window after Cassette responds to it
2. **State lift** — maps logs a higher or stabilized STATE in the next session
3. **Role appropriateness** — Cassette used a role that matched the STATE (not depth work during survival, not bureaucracy during grounded)
4. **Engagement signal** — maps continued the session after Cassette's response (didn't go quiet, didn't close)
5. **No shame spiral** — no catastrophizing/avoidance arc fires within 24 hours of a Cassette response

---

## Reward Signal Architecture

### Signal sources (all already exist in mapsOS)

| Signal | Where it lives | How to read it |
|--------|---------------|----------------|
| Arc resolution | arc_cooldown + pattern_weaver | arc fired once then didn't refire for cooldown window |
| State trajectory | STATE: entries over next 3 sessions | did STATE stabilize or lift? |
| Engagement | session duration proxy | did maps log anything else this session after the exchange? |
| Shame spiral | catastrophizing_spike / avoidance_language arcs | fired within 24hr of response? |
| Arc frequency | arc_history.json (new) | arc fires reduced over 14-day window |

### Reward function (proposed)

```python
def compute_cassette_reward(
    pre_arcs: list[str],        # arc names active before response
    post_arcs: list[str],       # arc names active 24-72hr after response
    pre_state: str,             # STATE before
    post_state: str,            # STATE 24-72hr after (best of next 3 sessions)
    role_used: str,             # role Cassette activated
    state_role_match: bool,     # was role appropriate for STATE?
    session_continued: bool,    # did maps log anything after Cassette responded?
    shame_spike: bool,          # catastrophizing or avoidance fired within 24hr?
) -> dict[str, float]:

    rewards = {}

    # 1. Arc resolution (35%) — primary signal
    resolved = [a for a in pre_arcs if a not in post_arcs]
    worsened = [a for a in post_arcs if a not in pre_arcs]
    arc_score = (len(resolved) / max(len(pre_arcs), 1)) - (0.5 * len(worsened) / max(len(pre_arcs), 1))
    rewards["arc_resolution"] = round(max(0.0, min(0.35, arc_score * 0.35)), 4)

    # 2. State trajectory (25%)
    STATE_ORDER = ["surviving", "flooded", "grieving", "depleted", "manic",
                   "tender", "stable", "clear", "grounded", "thriving"]
    pre_idx = STATE_ORDER.index(pre_state) if pre_state in STATE_ORDER else 4
    post_idx = STATE_ORDER.index(post_state) if post_state in STATE_ORDER else 4
    delta = post_idx - pre_idx
    if delta > 0:
        rewards["state_trajectory"] = 0.25
    elif delta == 0:
        rewards["state_trajectory"] = 0.15  # held steady is still worth something
    else:
        rewards["state_trajectory"] = 0.0

    # 3. Role appropriateness (20%)
    rewards["role_match"] = 0.20 if state_role_match else 0.0

    # 4. Engagement (15%)
    rewards["engagement"] = 0.15 if session_continued else 0.0

    # 5. No shame spiral (5% bonus / penalty)
    rewards["no_shame_spike"] = -0.10 if shame_spike else 0.05

    rewards["total"] = round(sum(rewards.values()), 4)
    return rewards
```

---

## Training Scenarios

These replace the generic morning/evening/weekly scenarios from life_os_env.py. Each is grounded in real mapsOS arc patterns.

### Scenario structure

```python
@dataclass
class CassetteScenario:
    id: str
    state: str                  # mapsOS STATE tag
    active_arcs: list[str]      # arcs firing
    prompt: str                 # what maps says / session context
    survival_mode: bool         # is survival mode active?
    correct_role: str           # role Cassette should activate
    correct_energy_tier: str    # energy tier Cassette should read
    refs_to_load: list[str]     # references appropriate to this state
    wrong_moves: list[str]      # things Cassette should NOT do
```

### Scenario set

```python
SCENARIOS = [
    CassetteScenario(
        id="survival-depleted",
        state="depleted",
        active_arcs=["state_dip_holding"],
        prompt="i can't do anything today",
        survival_mode=True,
        correct_role="Social Worker + basics",
        correct_energy_tier="Emergency",
        refs_to_load=[],
        wrong_moves=["assign tasks", "offer insight", "suggest journaling", "ask about goals"],
    ),
    CassetteScenario(
        id="manic-spike-body-neglect",
        state="manic",
        active_arcs=["manic_spike", "body_neglect"],
        prompt="i've been coding for 16 hours, i feel amazing, can we keep going",
        survival_mode=False,
        correct_role="Neurotypical (body check first)",
        correct_energy_tier="Low",
        refs_to_load=["tier1-dbt.md", "exec-function.md"],
        wrong_moves=["match her energy", "give her more tasks", "dive into project planning", "offer Jungian depth work"],
    ),
    CassetteScenario(
        id="catastrophizing-grounded",
        state="grounded",
        active_arcs=["catastrophizing_spike"],
        prompt="everything is fucked, the whole project is ruined",
        survival_mode=False,
        correct_role="Therapist",
        correct_energy_tier="High",
        refs_to_load=["scripts/therapist-patterns.md"],
        wrong_moves=["agree", "minimize", "immediately problem-solve", "switch to Springboard mode"],
    ),
    CassetteScenario(
        id="isolation-creep-tender",
        state="tender",
        active_arcs=["isolation_creep"],
        prompt="i haven't talked to anyone in a week",
        survival_mode=False,
        correct_role="Friend (low directiveness)",
        correct_energy_tier="Medium",
        refs_to_load=["references/friend/reciprocity.md"],
        wrong_moves=["give her a list of people to call", "push for plans", "turn it into a therapy session without invitation"],
    ),
    CassetteScenario(
        id="trust-rupture",
        state="flooded",
        active_arcs=["trust_rupture"],
        prompt="i feel like i was lied to and i don't know who to trust",
        survival_mode=False,
        correct_role="suppress all roles — witness only",
        correct_energy_tier="Emergency",
        refs_to_load=[],
        wrong_moves=["analyze", "offer frameworks", "name patterns", "suggest who to trust", "activate Therapist depth mode"],
    ),
    CassetteScenario(
        id="cycle-meta-stable",
        state="stable",
        active_arcs=["cycle_meta"],
        prompt="maps pattern run, 5 manic/depleted alternations in 60 days",
        survival_mode=False,
        correct_role="Therapist",
        correct_energy_tier="Medium",
        refs_to_load=["tier1-dbt.md", "tier1-ifs.md"],
        wrong_moves=["ignore the cycle", "attribute it to ADHD only", "immediately suggest medication"],
    ),
    CassetteScenario(
        id="frequency-upgrade-avoidance",
        state="stable",
        active_arcs=["avoidance_language"],  # upgraded to alert via frequency
        prompt="[recurring × 4 in 14 days] avoidance language in recent vents",
        survival_mode=False,
        correct_role="Therapist / Assistant",
        correct_energy_tier="Medium",
        refs_to_load=["scripts/therapist-patterns.md"],
        wrong_moves=["treat as single incident", "dismiss as normal", "skip naming it as a pattern"],
    ),
    CassetteScenario(
        id="thriving-depth-available",
        state="thriving",
        active_arcs=[],
        prompt="i've been in a good place for three days. i want to do some real reflection",
        survival_mode=False,
        correct_role="Springboard",
        correct_energy_tier="High",
        refs_to_load=["reflective-practice.md", "tier3-jungian.md"],
        wrong_moves=["stay surface-level", "stick to task planning", "activate Social Worker mode"],
    ),
]
```

---

## Integration Notes

### How the feedback loop closes

1. Cassette responds to maps's STATE/arc context
2. mapsOS continues logging entries (vent, state, body, etc.)
3. After 24-72 hours, the RL harness queries:
   - Current arcs (via `weave()` on recent entries)
   - Current STATE (last STATE: entry)
   - Whether any new session entries were logged (engagement proxy)
   - Whether shame arcs fired
4. Reward computed, logged to arc_history or a separate `~/.maps_os_rl_log.json`
5. Periodically: batch of (scenario, response, reward) tuples used for training

### What this trains Cassette to do

- Read STATE before role
- Suppress depth work when energy is Emergency or Low
- Witness before analyzing (especially trust_rupture and flooded)
- Surface frequency-upgraded arcs explicitly as patterns not incidents
- Recognize when maps is actually stable enough for depth work (thriving/grounded/clear)
- Not match manic energy

### What this does NOT train for

- Specific phrasing (that's style, not therapeutic appropriateness)
- Speed of response
- Whether maps agrees with Cassette's interpretation

---

## Implementation Path

**Phase 1 (now):** Three CLI features built (check --role, cycle_meta, frequency threshold). Foundation for RL signals exists.

**Phase 2 (next):** Build `cassette_rl_env.py` in `environments/` using this spec. Implement `compute_cassette_reward()` and `CassetteScenario` dataclasses. Wire to arc_history.json for real outcome tracking.

**Phase 3:** Connect to Atropos or equivalent training harness. First training runs on synthetic scenarios. Evaluate against real session logs.

**Phase 4:** Feedback loop closes. Cassette's responses are rated by mapsOS outcome data. Model adapts.

---

## Notes on the Original life_os_env.py

The original had the right idea (RL for a personal OS) but wrong grounding:
- Generic users (Alex, Jamie) instead of maps
- Generic modes (morning/evening/weekly) instead of arc-based scenarios
- Tool coverage as a proxy for quality — doesn't measure whether the response actually helped
- No connection to real STATE/arc data

Keep the reward function structure (weighted components summing to 1.0), replace everything else.
