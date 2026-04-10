# maps-os: Agent Build Guide — Phase 2.7
**Date:** 2026-04-10
**For:** codex / opencode agent
**Repo:** `/Users/maps/dev/hermes-maps-os/`

Read this whole document before starting. Do not start stage N+1 until stage N passes its tests. Run the existing test suite after each stage: `cd /Users/maps/dev/hermes-maps-os && python -m pytest tests/ -q`.

**Current test state: 196 passing, 0 failing.**

## ✅ Stage 0 — COMPLETE (2026-04-10)

7 correctness bugs fixed (EVENT/DEADLINE wiring, goal_stall field index, trigger/event patterns, dead code, date_resolver duplicate, viz body panel date-blind). ARC 15 planning_hyperfocus fixed. CLI schema fixes for `maps goal`, `maps events`, `maps check`, `maps pattern`. Tests: `tests/test_phase26_fixes.py`, `tests/test_cli_commands.py`.

## ✅ Stage 6 — COMPLETE (2026-04-10)

`person_context()` and `person_birth_hint()` added to `environments/maps_os_config.py`. `maps person <name>`, `maps person --list`, `maps person --init-astrolog` implemented in `bin/maps`. 16 astrolog skeleton profiles created at `~/.hermes/astrolog/`. Tests in `tests/test_cli_commands.py`.

---

## Codebase orientation

```
environments/
  vent_parser.py      # Entry dataclass, parse_vent(), all _extract_*() functions
  pattern_weaver.py   # Arc functions (ARC 1–22), weave()
  nota_bridge.py      # nota action routing
  maps_os_config.py   # config loader for ~/.maps_os_config.yaml
  tui.py              # Rich TUI — dashboard, survival mode, input screens
  local_store.py      # SQLite offline queue
  viz.py              # Rich-only visualizations: render_trend, render_viz
  date_resolver.py    # Relative date → ISO date conversion
bin/
  maps                # CLI entry point — all top-level commands live here
tests/
  test_new_arcs.py    # Arcs 17–22 tests — follow this pattern for new arcs
```

**Schema format:** all garden entries use `TRACK: YYYY-MM-DD | field | field | note`.
**Garden writes:** `garden remember '{entry}' --graph cassette` — always short graph ID.
**Arc numbering:** next available is ARC 23. Document each arc in the function docstring.
**File header on new files:** `# maps · cassette.help · MIT`
**Non-TTY safety:** all new commands must work when stdout is not a terminal.

---

## ✅ Stage 1 — COMPLETE (2026-04-10)

### 1a. `maps wins [--week] [--month]`

Query garden for WIN entries, display grouped by week.

```bash
maps wins           # all wins, most recent 30 days
maps wins --week    # this week only
maps wins --month   # this month only
```

**Implementation:**
- Query: `recall_resilient("WIN:", graph=args.graph, limit=50)`
- Parse each entry: `WIN: date | note`
- Group by ISO week (`date.isocalendar().week`)
- Display with Rich: week header, bulleted win notes under it
- No wins in range: `"no wins logged in this period."`
- Non-TTY safe: plain text output, no Rich Panel required

**Tests:** ≥2 smoke tests (no garden required — test the grouping/parsing logic directly with mock entries)

### 1b. `maps goal --update <phrase>`

Update a matching GOAL's status to `in_progress`. The GOAL schema includes three states (`open` / `in_progress` / `done`) but `--update` was never implemented.

```bash
maps goal --update "learn swedish"
```

**Implementation:**
- Same pattern as `maps goal --done`: query GOAL entries, find closest match to phrase
- Write a new GOAL entry: same description + status `in_progress` + today's date
- Print: `  ↻ goal updated: in_progress`
- Garden is append-only: never modify existing entries

### 1c. `maps eval`

`maps eval` is referenced in the CLI docstring and AGENT_GUIDE.md quick reference but not implemented. Implement it.

```bash
maps eval           # cassette performance trend (last 30 days)
maps eval --days 7  # shorter window
```

**Output:**
- Intention met rate: count met/missed/partial INTENTION entries for the period, compute rate
- STATE distribution: count of each STATE tag
- Arc fire count: query arc history if available (or note "arc history not persisted yet")
- Format: plain Rich table, non-TTY safe

**Query:** `recall_resilient("INTENTION:", limit=60)` + `recall_resilient("STATE:", limit=30)`

**Tests:** ≥2 smoke tests for the parsing/rate computation logic

---

## ✅ Stage 2 — COMPLETE (2026-04-10)

Add to `environments/pattern_weaver.py`. Add all new arcs to `weave()`.

### ARC 23 — resistance_pattern (`_arc_resistance_pattern`)

- Input: entries of track `RESISTANCE`
- Fires: 3+ RESISTANCE entries mentioning the same source phrase within 14 days
- Matching: extract the source phrase (text before the ` | intensity` separator), lowercase, check if any two entries share a word ≥5 chars (rough dedup — not exact match required)
- Message: `"you've been resisting {source} for {n} days. worth naming why?"`
- Severity: `"insight"`
- Surface: most-repeated source, oldest first for the date count

Add to `weave()` signature: already receives `decision_entries` etc. RESISTANCE entries need to be added as a parameter if not already present.

**Tests:** ≥3 tests in `tests/test_new_arcs.py`
- fires on 3+ resistance entries with same-source word match
- does not fire on 2 resistance entries
- does not fire when sources are unrelated

### ARC 24 — negative_interaction_pattern (`_arc_negative_interaction_pattern`)

- Input: entries of track `PERSON`
- Fires: 3+ PERSON entries for the same name with sentiment `negative` within 30 days
- Name matching: extract name from `PERSON: date | name | context | sentiment` format (parts[1] after split by `|`)
- Message: `"{name} is consistently showing up as draining. pattern worth noticing."`
- Severity: `"insight"`
- Surface one arc per most-frequent negative-sentiment person

**Tests:** ≥3 tests
- fires when same person has 3+ negative entries in 30 days
- does not fire if only 2 negative entries
- does not fire when sentiment is neutral even if person logged many times

---

## ✅ Stage 3 — COMPLETE (2026-04-10)

**Problem:** Insight arcs can fire on every `maps check` call as long as conditions persist. This creates alert fatigue. A manic spike that lasts 3 days will trigger `manic_spike` three sessions in a row.

**Implementation:**

Add `environments/arc_cooldown.py` (new file):

```python
# maps · cassette.help · MIT
"""
arc_cooldown.py — Per-arc suppression tracking.

Cooldown state is persisted to ~/.maps_os_cooldown.json.
An arc that fires is suppressed for its cooldown window (in days).
"""
```

Public API:
```python
def cooldown_path() -> Path:
    """Returns ~/.maps_os_cooldown.json"""

def load_cooldowns() -> dict:
    """Load {arc_name: last_fired_iso_date}. Returns {} on missing file."""

def save_cooldowns(cooldowns: dict) -> None:
    """Persist cooldown state. Never raises."""

def is_suppressed(arc_name: str, cooldowns: dict, cooldown_days: int) -> bool:
    """Returns True if arc fired within cooldown_days."""

def record_fired(arc_name: str, cooldowns: dict) -> dict:
    """Returns updated cooldowns dict with arc_name set to today."""
```

Default cooldown windows (in `arc_cooldown.py`):
```python
ARC_COOLDOWNS: dict[str, int] = {
    "manic_spike": 1,         # alert — allow daily
    "body_neglect": 1,
    "isolation_creep": 2,
    "state_dip_holding": 0,   # never suppress (survival trigger)
    "spirit_rising": 3,
    "post_manic_drop": 2,
    "thriving_streak": 3,
    "productivity_spiral": 2,
    "catastrophizing_spike": 1,
    "planning_hyperfocus": 1,
    "substance_coping": 3,
    "avoidance_language": 2,
    "decision_pile": 3,
    "trigger_pattern": 7,
    "goal_stall": 7,
    "resistance_pattern": 5,
    "negative_interaction_pattern": 7,
    # default for unlisted arcs: 0 (never suppress)
}
```

**Integration in `weave()`:**

Add optional `apply_cooldown: bool = True` parameter. When `True`:
1. Load cooldowns at the start of `weave()`
2. After running all detectors, filter result arcs: remove any arc whose name is in cooldowns and `is_suppressed(arc.name, cooldowns, ARC_COOLDOWNS.get(arc.name, 0))`
3. For each arc that survives the filter, call `record_fired(arc.name, cooldowns)`
4. Save updated cooldowns

Alert arcs with `severity == "survival"` are never suppressed regardless of cooldown state.

**Tests:** ≥3 tests
- arc not in cooldowns: fires
- arc in cooldowns but cooldown expired: fires
- arc in cooldowns within window: suppressed
- survival arcs never suppressed

---

## ✅ Stage 4 — COMPLETE (2026-04-10)

### ARC 25 — exec_dysfunction (`_arc_exec_dysfunction`)

**Rationale:** The most debilitating ADHD/dysregulation pattern is when resistance + goal stall + low state co-occur. No single arc catches this combination. It needs its own detector.

- Input: `state_entries`, `resistance_entries`, `goal_entries`
- Fires when ALL of:
  - Current STATE in (`depleted`, `flooded`, `manic`)
  - ≥1 RESISTANCE entry with intensity `high` in last 7 days
  - ≥1 GOAL with status `open` older than 14 days
- Message: `"resistance is high and {goal} has been stalled. exec dysfunction pattern. what's the one thing that doesn't require starting?"`
- Severity: `"insight"`
- Surface the oldest stalled goal in the message
- Does not fire in survival mode (state == `grieving` or `surviving` counts as survival, not exec dysfunction)

Add to `weave()` after existing insight detectors.

**Tests:** ≥4 tests
- all three conditions met → fires
- state is stable (not depleted/flooded/manic) → does not fire
- resistance is low intensity → does not fire
- goal is recent (< 14 days) → does not fire

---

## Stage 4e — Tests

After each stage, run full test suite. Confirm:
- 174 originally passing tests still pass
- New tests added for each stage as noted above
- `python -m pytest tests/ -q` exits 0

---

## Stage 5 — Smoke tests for existing visualization (✅ partially done)

`tests/test_phase26_fixes.py` includes one viz smoke test (`test_render_viz_body_panel_tracks_presence_per_day`). If additional coverage is needed:

**`render_trend()`** — call with ≥5 STATE dict entries spanning 3 different tags. Assert result is not None and contains `█`.

Use synthetic entry dicts: `{"content": "STATE: 2026-04-01 | thriving | test"}`.

---

## Out of scope for Phase 2.7

**nota task deduplication** — explicitly deferred. Do not add deduplication logic to `nota_bridge.py`.

**Priority 4.7 architecture items** — deferred to Phase 2.8. Do not implement: shared entry codec, canonical alias resolution, real date-window filtering, arc evidence persistence, safe garden subprocess wrapper, `maps doctor`, `maps parse --dry-run`, config schema v2. The current Stages 1-4 are clean feature additions that don't require architecture refactors first.

---

## Rules for the implementing agent

- Run `python -m pytest tests/ -q` after each stage. All existing green tests must stay green.
- Do not modify the garden write format for existing entry types.
- All new `_extract_*` functions: return `[]` on no match, never raise.
- All new Arc functions: return `None` or `[]` on insufficient data, never raise.
- Config (`~/.maps_os_config.yaml`) is always optional — missing file = degrades gracefully.
- nota routing is always wrapped in try/except and gated on `nota_available()`.
- Cooldown file missing or malformed: degrade gracefully, do not raise.
- No hardcoded names, people, or personal data anywhere in source.

---

*maps · cassette.help · MIT*
