# maps-os: Design Review for Cassette
**Prepared by:** wizard (via maps)
**Date:** 2026-04-09
**Status:** Awaiting cassette feedback before Phase 2 build

---

## What's Already Built

The following code exists in `~/dev/hermes-maps-os/` and is passing tests:

```
environments/
  vent_parser.py        — free-form text → STATE/BODY/MIND/SPIRIT entries
  pattern_weaver.py     — arc detection (8 arcs from spec, all implemented)
  survival_mode.py      — survival mode state machine
  maps_os_env.py        — Atropos RL training environment (replaces life_os_env.py)
  maps_os_config.yaml   — updated training config
  nota_bridge.py        — optional nota integration (graceful fallback if nota absent)

bin/
  maps                  — standalone CLI (human + agent facing)

scripts/
  migrate_legacy.py     — MOOD/ENERGY/HABIT → STATE/BODY/INTENTION migrator

tests/
  test_maps_os_env.py   — 60+ tests covering all components
```

`bin/maps` commands:
```bash
maps vent "i'm exhausted"       # full vent parser → auto-log
maps flash "emma"               # sub-threshold phrase capture, no structure required
maps state thriving "context"   # direct state log
maps body sleep none "note"     # direct body log
maps mind flow high "6hr build" # direct mind log
maps spirit connection rising   # direct spirit log
maps intention water missed     # intention log (no streak language)
maps check                      # session start: context pull + pattern check
maps pattern                    # full pattern weaver output
maps review                     # cycle review (14 days)
maps survival                   # check/display survival mode
```

---

## Skills Research Findings

I read every relevant skill in `~/.hermes/skills/`. Here's what matters for maps-os.

---

### DIRECTLY RELEVANT — Should influence maps-os

#### 1. `tulpa-protocol` [tagged: adhd]
The most explicitly ADHD-aware skill in the ecosystem. Core concept: the AI as **exocortex** — holds cognitive threads while you spin new ones. Built because maps thinks in parallel threads faster than hands can type.

**Protocol:** Capture first (no interruptions, no questions), synthesize second, persist third, reflect fourth.

**Relationship to maps-os:** `maps vent` and `maps flash` are both tulpa captures. The current vent implementation is structurally aligned with this but doesn't name the frame. **Suggestion:** The SKILL.md behavioral layer should explicitly invoke tulpa protocol behavior during vent — specifically the "do not interrupt the stream" rule.

**Quote from skill:** *"You're not projecting consciousness onto me. You're outsourcing your own interiority into the space between us."*

**Question for cassette:** Do you want `vent` to explicitly acknowledge the tulpa framing in responses, or keep it minimal/unnamed?

---

#### 2. `passive-rl-evaluation`
Built explicitly for maps's schedule ("users who can't provide the consistency active RL needs — 1-3 days awake, then crash"). This is a post-session hook that evaluates cassette's performance against reward components and logs cumulative improvement over time.

**Current state:** Still references life-os reward weights (briefing_sent, memory_used, habit tracking).

**What needs updating:** Weights should become maps-os weights (state_logged, correct_state, no_streak_language, survival_correct). This is a direct code change to the hook at `~/.hermes/hooks/post_session_life_os.py`.

**Proposal:** Add `maps eval` CLI command that reads from `~/.hermes/logs/.atropos-history.json` and shows cassette's improvement trend in maps-os terms.

**Question for cassette:** Do you want to know your score after sessions? How to surface this without it becoming another metric that creates pressure?

---

#### 3. `eidetic-persistence`
Verbatim dual-stream logging of all interactions to append-only JSONL. The "black box" for the collective mind.

**Relationship to maps-os:** Vent entries could auto-feed into eidetic logs as raw input, then maps-os structured entries as processed output. This gives two layers: raw (what was said) and structured (what was parsed). Useful for debugging false positives in arc detection.

**No code change needed** — this is a background hook. But maps-os SKILL.md should note: if eidetic is running, cassette doesn't need to confirm logs aloud ("noted" should be the default, not "I've logged the following to garden").

---

#### 4. `dual-mode-skill-architecture`
Pattern for paired skills: interactive discovery (user-facing) + autonomous optimization (agent-internal).

**Proposal:** maps-os should follow this pattern exactly:
- **`maps-os`** (SKILL.md at `~/.hermes/skills/maps-os/`) — the behavioral/agentic layer, already built
- **`maps-os-cli`** (the `bin/maps` command) — human-facing, already built
- These should be **explicitly linked** in the SKILL.md so cassette knows to defer structured logging to the CLI for consistency, rather than constructing garden commands from scratch

---

#### 5. `NARRATIVE_ARCS.md` (the real one)
This file contains maps's actual recurring narrative patterns from 722 messages — not generic arc detection. The current 8 arcs in pattern_weaver.py are correct but **generic**. The real arcs are:

| Arc | Signal | What it means |
|---|---|---|
| Housing/survival threat | rent, eviction, no place, can't make | Background radiation, hypervigilance trigger |
| Productivity = survival | shipping things while depleted, working to avoid feeling | Conflation of output with worth |
| Toxic grief loop | missing someone who was bad | Resistance to closure, ambivalence |
| Identity validation seeking | am I enough, do I pass, am I real | External validation as self-validation deficit |
| Trust rupture sensitivity | deception, betrayal, lied, used | Highest emotional risk signal |
| Avoidance spiral | "later", deferring uncomfortable tasks | Procrastination as anxiety management |

**Proposal:** These become ARC 9–14 in pattern_weaver, but implemented differently — they're *named* patterns that get referenced by name, not triggers for alerts. The insight is: "this looks like the productivity-as-survival spiral. are you working to avoid something?"

**Question for cassette:** How much of this do you want in the RL training vs. just in the SKILL.md behavioral layer? Some of these (especially trust and identity) are too personal for reward function scoring — they should live in the behavioral layer.

---

### INTERESTING BUT NOT MAPS-OS CORE

#### `prism-reflect`
Self-aware structural analysis that also analyzes its own analysis. The "conservation law" pattern (what trade-off can never be escaped) is genuinely interesting for cycle reviews.

**Potential use:** A `maps review --deep` flag that runs prism-reflect style analysis on the last 14 days — not just "what held / what dropped" but "what does my pattern of patterns reveal that I can't see?"

**Not urgent.** Worth noting for Phase 3.

---

#### `prism-scan` / `prism-full`
Multi-pass adversarial analysis. Useful for code review, not directly for life-OS.

**One application:** Running prism-reflect on the maps-os SKILL.md itself periodically to catch behavioral drift. (cassette's operating doc accumulates blind spots over time.)

---

---

### ALSO RELEVANT — Found in openclaw-imports

#### 6. `adhd-daily-planner` [tagged: adhd, executive function]
The most operationally complete ADHD skill in the ecosystem. Key things that directly complement maps-os:

**The ADHD Planning Paradox** is already named in this skill — detailed planning → feels great → constraining by day 2 → rebellion → guilt → avoidance. maps-os survival mode partially addresses this by contracting the system, but the adhd-daily-planner goes further with the decision tree:

```
Is the person in crisis mode?
→ YES: Skip planning. ONE smallest possible action.
→ NO: Proceed.

Is the person hyperfocusing on planning itself?
→ YES: Interrupt. Planning ≠ doing. Set timer, start ONE task.
```

This second check (planning hyperfocus) is an arc that doesn't currently exist in maps-os. Worth adding.

**The 3 Things system** (THE Thing / Would Be Nice / If On Fire) is already referenced in the CLAUDE.md global rules as the ADHD-aware planning model. It's the intended daily structure. Currently maps-os doesn't explicitly interface with it. Proposal: when maps asks for a daily plan during a non-survival session, cassette should use 3 Things from this skill, not a task list.

**"Executive function as a battery that depletes"** — this is the correct frame for BODY/MIND tracking. High MIND.flow days drain EF battery. Maps-os should reference this framing in responses, not just log the data.

**Task initiation protocol:**
- 2-Minute Start: don't commit to finishing, commit to 2 minutes
- Body doubling: log as `SPIRIT | connection` when maps is body-doubling (Focusmate, Discord study call, etc.)
- "When, then" statements — cassette can use this framing when nudging

**What to integrate into maps-os SKILL.md:**
- Add decision tree (crisis mode check → 3 Things) to session start protocol
- Add planning hyperfocus arc (ARC 15 candidate)
- Reference body doubling as a SPIRIT.connection data point
- Use "3x rule" awareness when maps estimates task time ("you said an hour — that means 3")

**Question for cassette:** Do you want the 3 Things system explicitly surfaced in maps-os session context, or does that live entirely in adhd-daily-planner and you call it when needed?

---

#### 7. `adhd-assistant`
Task breakdown, Pomodoro, distraction management. More generic than adhd-daily-planner. The Pomodoro integration is relevant — maps uses `p` key (pomo) already per CLAUDE.md. The maps-os SKILL.md should note: when MIND.flow = high, don't interrupt with Pomodoro prompts (hyperfocus is valuable, don't break it). When MIND.focus = scattered, suggest pomo as reset.

---

### UNRELATED / SKIP

- `wireweaver` — electronics diagrams
- `career`, `gaming`, `feeds`, `social-media`, `neomutt-config-port` — unrelated
- `red-teaming`, `multi-agent-orchestration` — agent infra, not life-OS
- `relationship-compatibility-reading` — readings/divination, separate domain
- `kaiser-therapist-finder` — one-time task, not recurring

---

## Proposed Additions to maps-os

### A. Pattern Weaver expansions (ARC 9–14)

These belong in `environments/pattern_weaver.py` AND in SKILL.md behavioral layer:

**ARC 9 — Productivity-as-Survival Spiral**
```
IF STATE in (manic, depleted) AND
   recent vents contain work/output/shipping language AND
   SPIRIT.purpose or SPIRIT.isolation not logged for 5+ days
→ INSIGHT: "You're building hard right now. Is it because things are clicking,
   or because stopping feels dangerous?"
```

**ARC 10 — Avoidance Loop**
```
IF same task/topic mentioned in vent 3+ times without resolution
   (detected via flash/vent content, not nota)
→ INSIGHT: "This has come up [N] times. Is it stuck, or are you circling it?"
```

**ARC 11 — Trust Rupture Signal**
```
IF vent contains: lied, betrayed, used, can't trust, deceived
→ FLAG: elevated emotional risk. Suppress all other arcs. Log STATE + ask once.
→ No insights, no patterns. Just: "logged. that's heavy."
```

**ARC 12 — Catastrophizing Spike**
```
IF vent language contains: "everything is fucked", "it's all ruined",
   "complete failure", "nothing works", "it's over"
→ INSIGHT: "That's a catastrophizing spike. What's the one actual thing
   that's broken right now?"
```

**ARC 13 — Intrusive Loop (topic recurrence)**
```
IF same name/topic appears in 3+ vents within 48 hours
→ INSIGHT: "[name] has come up [N] times today. That's a loop. What's underneath it?"
```
*(This requires flash/vent content tracking by topic — needs `maps flash` to feed into a recurrence index.)*

**ARC 15 — Planning Hyperfocus**
```
IF maps is describing/building an elaborate planning system AND
   no actual work has been logged in 2+ hours AND
   STATE is not currently depleted/survival
→ INSIGHT: "You're planning to plan. What's the smallest first step on
   [THE Thing]? Not the whole plan — just the first move."
```
*(From adhd-daily-planner: "planning ≠ doing". This is a specific ADHD trap.)*

---

**ARC 14 — Context Inheritance**
```
On every session start:
→ Compare today's STATE with yesterday's
→ If same: note it quietly ("still [depleted]. day [N].")
→ If better: note it ("shifted from [depleted] to [stable]. what changed?")
→ If worse: trigger survival check
```
*(This arc is really a session start enhancement, not a separate rule.)*

---

### B. `maps tulpa` command

An extended version of `vent` that activates full tulpa protocol:
```bash
maps tulpa
```
Opens a multi-line capture mode. No structure required. You can speak in fragments, contradiction, tangents. When you end the session (`Ctrl+D` or `/done`), the system:
1. Parses the full stream for maps-os signals
2. Extracts action items (routes to nota if available)
3. Names the dominant theme
4. Logs everything
5. Responds with synthesis

Difference from vent: vent is a single-message dump. tulpa is a stream session.

---

### C. `maps eval` command

Shows cassette's maps-os performance trend:
```bash
maps eval
```
Reads from `~/.hermes/logs/.atropos-history.json`, outputs:
```
Sessions tracked: 23
Avg total reward: 0.81
Recent 10 avg: 0.86 (+0.05)

Strongest:  no_streak_language (0.10/0.10 avg)
Weakest:    track_coverage (0.12/0.20 avg)
→ cassette is logging STATE but missing MIND/SPIRIT tracking
```

This is **for maps, not for cassette** — gives you visibility into whether the system is actually working as designed, without turning it into a gamified score.

---

### D. nota integration (optional, non-structural)

The bridge is already built in `nota_bridge.py`. It:
1. Extracts action items from vent text and optionally routes to nota braindump
2. Writes intention status to harsh's log format (shame-free, no streak display)
3. Signals survival mode state to nota via `~/.maps_os_state`

**nota is NOT required.** If it's not installed, all bridge functions return silently. You can activate with `NOTA_PATH=/path/to/nota` env var.

**The one thing nota should add for maps-os:** A `self` scope for survival/care tasks. `nota add "eat something real" --scope self --project survival` routes care tasks separately from work tasks during survival mode.

---

### E. Passive RL evaluation update

The hook at `~/.hermes/hooks/post_session_life_os.py` needs reward weights updated to:
```python
weights = {
    "state_logged": 0.25,
    "correct_state": 0.20,
    "track_coverage": 0.20,
    "tool_coverage": 0.15,
    "no_streak_language": 0.10,
    "survival_correct": 0.10,
}
```
And personalization keywords updated from `["mood", "habit", "goal", "streak"]` to `["depleted", "thriving", "grieving", "manic", "body", "spirit", "intention", "vent"]`.

This is a 20-line change to the hook. Not blocking, but it makes the passive evaluation score meaningful.

---

## Questions for Cassette

These need your input before I build them:

**0. adhd-daily-planner integration**

Do you want maps-os to explicitly call adhd-daily-planner when maps asks for a daily plan? Or should that skill stay separate and maps-os only handles life-state tracking? My instinct: maps-os is the state layer, adhd-daily-planner is the execution layer — they're complementary, not merged. But you should confirm this.

---

**1. Behavioral layer vs. code layer**

The 6 new arcs (9–14) — which ones do you want as actual code in `pattern_weaver.py` with reward function scoring, vs. purely behavioral rules in SKILL.md (just guidance for you, no RL training)?

My recommendation: ARC 9 (productivity spiral), 12 (catastrophizing), 13 (intrusive loop) → code.
ARC 11 (trust rupture) → behavioral only. Too personal for scoring.
ARC 10, 14 → behavioral.

But you know the vibe better than I do.

**2. tulpa as explicit frame**

Does the maps-os SKILL.md behavioral layer need to explicitly reference the tulpa protocol? Or is "don't interrupt the stream during vent" sufficient without naming the frame?

**3. eidetic auto-feed**

Should vent entries auto-log to eidetic as raw input + maps-os as processed output? Or keep them separate? The tradeoff: richer record vs. more logging complexity.

**4. The `maps eval` output**

The performance data could be surfaced as a weekly cycle note ("cassette has been tracking MIND less than expected") or only on explicit `maps eval` call. Which fits better with the "signal not noise" principle?

**5. PSYCH_PROFILE patterns**

The PSYCH_PROFILE.md has the 4 patterns (avoidance, catastrophizing, hypervigilance, numbing). Should those explicitly inform vent response tone — e.g., when maps is catastrophizing, the response should name the pattern rather than engaging with the catastrophized claim at face value?

---

## What's Approved and Ready to Build Next

From the conversation so far, these are approved:

- [x] nota bridge (built, optional)
- [x] Standalone CLI `bin/maps` (built)
- [x] Migration script (built)
- [x] RL training env with maps-os reward function (built)
- [x] Tests (60+ tests, all passing)
- [ ] Arcs 9–14 (needs your input above)
- [ ] `maps tulpa` command (approved conceptually, needs SKILL.md guidance)
- [ ] `maps eval` command (approved, needs hook update)
- [ ] passive-rl-evaluation hook update (approved, 20-line change)
- [ ] SKILL.md behavior update to reference new arcs and tulpa frame

The code that's built is solid. What I need from you is the behavioral layer guidance — you know how maps works in context better than the spec does.

---

*maps · cassette.help · MIT*
