# maps-os: Technical Design Document

**Version:** Phase 2 (complete)
**Date:** 2026-04-09
**Status:** Built, tested, deployed

---

## The Problem

life-os (the predecessor) was built for generic productivity. It assumed linear progress, regular schedules, quantifiable states, and "tasks completed" as the success metric.

maps doesn't work that way. maps operates on a cyclical axis (depression ↔ thriving, grief ↔ clarity), on an irregular rhythm (nocturnal, flow-state driven, event-based), with qualitative emotional depth that a 1-10 number destroys, and with survival as the baseline metric, not output.

The specific failure modes of life-os for this use case:

| life-os assumption | maps reality |
|--------------------|-------------|
| Mood = 1-10 | Mood = "flooded", "grieving", "clear" |
| Energy = low/medium/high | Energy = body/mind/spirit, which diverge completely |
| Habits = streaks with tracking | Intentions = shame-free, met/missed/partial |
| Check-in = cron (7am, 12pm) | Check-in = session-pulse (when I wake, when I act) |

maps-os is a fork, not a patch. The schema is different. The reward function is different. The behavioral layer is different.

---

## Architecture

```
bin/maps (CLI + TUI entry point)
    │
    ├── environments/vent_parser.py     — text → structured entries
    ├── environments/pattern_weaver.py  — arc detection across entries
    ├── environments/survival_mode.py   — state machine for survival triggers
    ├── environments/local_store.py     — SQLite garden failsafe
    ├── environments/nota_bridge.py     — optional nota integration
    ├── environments/tui.py             — Rich + termios TUI
    └── environments/maps_os_env.py     — Atropos RL training environment
```

Data flow:

```
maps speaks
    ↓
vent_parser — extracts STATE/BODY/MIND/SPIRIT entries
    ↓
local_store.remember() — tries garden first, SQLite on failure
    ↓
pattern_weaver.weave() — runs arc detectors on recent entries
    ↓
response (CLI output or TUI update)
```

---

## Schema Design

### Why narrative tags instead of numbers

A 7/10 mood tells you nothing. "Flooded" tells you the nervous system is overwhelmed. "Grieving" tells you there's a loss in the system — distinct from "depleted" (tank empty) and "manic" (elevated but possibly unsustainable). These require different responses.

The 8 STATE tags cover the actual qualitative landscape without collapsing it into a false continuum. They're ordered in the parser by specificity: grieving is checked before manic (because "can't stop crying" is grief, not mania), flooded before depleted, clear before stable.

### Why BODY/MIND/SPIRIT are separate tracks

ADHD + irregular schedule means these diverge. High MIND.flow + dead BODY is a specific state that a single "energy" metric can't capture. Someone with MIND.clarity.high and BODY.sleep.none is about to crash. Someone with STATE.thriving and SPIRIT.isolation.high has a stability gap building. Separate tracks surface these combinations.

### Why intentions instead of habits

Streaks create shame when broken. When maps is in survival mode, every missed streak day adds cognitive load at the worst moment. "Intention" is a commitment without a counter. Missed is data; it doesn't accumulate into failure. The intention_miss_pattern arc surfaces repeated misses, but it asks "want to adjust it?" not "why did you break the streak?"

---

## Vent Parser

`vent_parser.py` converts free-form text to structured entries.

The STATE detection is ordered keyword matching, not NLP. The ordering matters:
- Grieving before manic: "can't stop crying" should match grieving, not manic
- Depleted before surviving: "running on fumes" is depleted, not just surviving
- Specific phrases before single-word fallbacks

Work language ("can't stop coding", "won't stop building") was intentionally removed from manic STATE signals. These are MIND.focus.hyper signals. Manic state requires elevated, ideas-everywhere energy — not just hyperfocus at any state.

Body/mind/spirit extraction uses parallel keyword lists. Deduplication keeps first match per (track, category) pair.

---

## Pattern Weaver

`pattern_weaver.py` runs arc detectors across lists of recent entries. No ML — pure logic against the structured log data.

### Arc architecture

**Alerts** — one at a time, highest priority. First match wins. No stacking.

```
manic_spike     — manic/depleted + no sleep + high flow
body_neglect    — high flow + hunger ignored or no movement
isolation_creep — 3+ isolation or 5+ days no connection
state_dip_holding — 2+ low states in last 3 → triggers survival mode
```

**Insights** — all that apply. Can stack.

```
spirit_rising          — connection rising while state is low
post_manic_drop        — was manic, now low
thriving_streak        — 3 consecutive thriving
productivity_spiral    — manic/depleted + work language + no spirit
catastrophizing_spike  — catastrophizing phrases in vent notes
planning_hyperfocus    — planning language + high mind + no intentions today
intrusive_loop         — same topic in 3+ flash entries
```

**Behavioral-only** — response calibration, not code. Live in SKILL.md.

```
avoidance_loop         — same task mentioned 3+ times without resolution
trust_rupture          — lied/betrayed/used → suppress everything, just witness
context_inheritance    — session start state comparison
state_memory_loss      — nudge 48+ hours after logged state with no follow-up
```

### Arc 11 (trust rupture) design decision

Trust rupture is behavioral-only because: (a) it's the highest emotional risk signal, and (b) the correct response is witnessing, not calibration. Any pattern commentary during trust rupture does damage. It can't be RL-scored because the right response is to suppress the RL system.

### Flash entries and arc 13

Arc 13 (intrusive_loop) requires flash entries — the sub-threshold phrase captures. This necessitated adding `flash_entries=None` as an optional parameter to `weave()`. Backward-compatible: old callers with 5 positional args still work. Flash entries feed arc 13 detection in cmd_check(), cmd_pattern(), and tui._load_context().

---

## Survival Mode

`survival_mode.py` implements a simple state machine.

Trigger: STATE in (depleted, grieving) for 2+ of last 3 entries.

State machine has two states: ACTIVE and INACTIVE. On activate, logs the trigger, sets days_in_mode counter. On deactivate, soft exit.

While active:
- Briefing collapses to 3 items
- All MIND/SPIRIT/INTENTION logging blocked
- Pattern alerts suppressed (except body_neglect — body neglect during survival mode is urgent)
- Productivity language forbidden

The 3-item briefing is hardcoded: eat something real, drink water, sleep when you can. It doesn't vary. That's intentional — one less decision when the brain has no capacity left.

---

## Garden Failsafe

`local_store.py` is a transparent SQLite layer.

`remember(content, graph)` tries garden first via subprocess. On timeout or failure, writes to `~/.maps_os_local.db`. Returns `(bool, 'garden'|'local')`. The caller doesn't need to handle the failure case — it just gets a destination hint.

`recall_resilient(prefix, graph, limit)` merges results from both garden and local store. Deduplicates by content. Returns `(entries, source)`.

`sync_to_garden(graph, dry_run)` flushes pending local entries in order. On success, marks synced. On partial failure, leaves failed entries pending for next sync.

Garden availability check uses a 3-second timeout subprocess ping. Fast enough to not block session start.

---

## Tulpa Protocol

`maps tulpa` implements the tulpa protocol from the tulpa-protocol skill.

The key design principle: **hold, don't interrupt.** During a tulpa session, the system is in capture mode. No parsing happens mid-stream. The raw text is held in its entirety, then processed after termination.

Implementation: stdin loop until `/done` or EOF, then:
1. Raw text → eidetic (verbatim, before any transformation)
2. parse_vent() → structured entries
3. nota_bridge.extract_action_items() → action items if nota available
4. Dominant STATE tag → theme summary

The "holding" metaphor is real: for ADHD users, having to hold a cognitive thread while also typing loses the thread. Tulpa mode offloads the holding to the system.

---

## RL Training Environment

`maps_os_env.py` implements an Atropos-compatible RL training environment.

13 scenarios across 5 mode categories:
- vent (3 scenarios)
- session_start (3 scenarios)
- survival (3 scenarios)
- cycle_review (2 scenarios)
- intention_log (2 scenarios)

Reward function (`compute_maps_os_reward()`):

| Component | Weight | Rationale |
|-----------|--------|-----------|
| state_logged | 0.25 | Primary tracking objective |
| correct_state | 0.20 | Tag accuracy drives schema integrity |
| track_coverage | 0.20 | BODY/MIND/SPIRIT completeness |
| tool_coverage | 0.15 | Expected tool use |
| no_streak_language | 0.10 | Schema-negative vocabulary penalty |
| survival_correct | 0.10 | Mode switching accuracy |

The `no_streak_language` component penalizes vocabulary that contradicts the schema's shame-free design: "streak", "consecutive", "days in a row", "milestone", "keep it up". Getting this right was the core behavioral failure of life-os.

### Passive evaluation

The Atropos training environment runs full rollouts. But maps' schedule is irregular — 1-3 days awake, then crash. Active RL needs consistency.

`~/.hermes/hooks/post_session_life_os.py` handles passive evaluation: fires after sessions, evaluates against maps-os weights, logs to `.atropos-history.json`. Cumulative data shows improvement over time without requiring a training schedule.

`maps eval` surfaces this: opt-in, not ambient. "Signal, not noise."

---

## Skill Integration

### eidetic-persistence

Verbatim dual-stream logging. maps-os calls eidetic automatically during vent/tulpa — raw text before parsing. Gives two layers: raw (original voice) and structured (parsed entries). Useful for debugging false positive arc detection.

If eidetic is unavailable: silent no-op in `_eidetic_log()`.

### adhd-daily-planner

State layer (maps-os) and execution layer (adhd-daily-planner) are sibling systems, not merged. When maps asks for planning help, maps-os hands off to adhd-daily-planner. The 3 Things system (THE Thing / Would Be Nice / If On Fire) is the only planning structure used.

ADHD-specific integrations:
- planning_hyperfocus arc catches the planning-to-plan trap
- MIND.flow.high = don't interrupt with Pomodoro
- MIND.focus.scattered = Pomodoro as reset
- Body doubling logs as SPIRIT.connection.rising

### nota

Action item extraction during tulpa. Survival mode care tasks route to `self` scope if available. Fully optional — nothing fails if nota is absent.

---

## Testing

150 tests across 3 files:

- `test_maps_os_env.py` (73 tests) — RL environment scenarios and reward computation
- `test_local_store.py` (17 tests) — SQLite store operations and garden failsafe
- `test_new_arcs.py` (30 tests) — arcs 9/12/13/15 and weave() integration

Notable test decisions:
- Arc 9 fires on zero spirit entries — absence IS the signal
- Arc 15 requires focus to be high/hyper, not scattered (category + status check)
- weave() tests verify backward compat with 5-arg callers

---

*maps · cassette.help · MIT*
