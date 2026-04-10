# maps-os: Agent Build Guide — Phase 2.2–2.5
**Date:** 2026-04-10
**For:** codex / opencode agent
**Repo:** `/Users/maps/dev/hermes-maps-os/`

Read this whole document before starting. Each stage is self-contained. Do not start stage N+1 until stage N passes its tests. Run the existing test suite after each stage: `cd /Users/maps/dev/hermes-maps-os && python -m pytest tests/ -q`.

---

## Codebase orientation

```
environments/
  vent_parser.py      # Entry dataclass, parse_vent(), all _extract_*() functions
  pattern_weaver.py   # Arc functions (ARC 1–19), weave()
  nota_bridge.py      # nota action routing
  maps_os_config.py   # (may not exist yet) config loader for ~/.maps_os_config.yaml
  tui.py              # Rich TUI — dashboard, survival mode, input screens
  local_store.py      # SQLite offline queue
bin/
  maps                # CLI entry point — all top-level commands live here
tests/
  test_new_arcs.py    # Arcs 17–19 tests — follow this pattern for new arcs
  test_chat_tui_commands.py
  test_adapter_trigger_policy.py
```

**Schema format:** all garden entries use `TRACK: YYYY-MM-DD | field | field | note`.
**Garden writes:** `garden remember '{entry}' --graph cassette` — always short graph ID.
**Arc numbering:** next available is ARC 20. Document each arc in the function docstring.
**File header on new files:** `# maps · cassette.help · MIT`
**Non-TTY safety:** all new commands must work when stdout is not a terminal.

---

## Stage 1 — Enhanced vent parsing

**New entry types and schema:**

```
PERSON: YYYY-MM-DD | name | context | sentiment
DECISION: YYYY-MM-DD | framing | options
RESISTANCE: YYYY-MM-DD | source | intensity(low/medium/high)
TRIGGER: YYYY-MM-DD | source | reaction
GOAL: YYYY-MM-DD | description | due(YYYY-MM-DD or none) | status(open/in_progress/done)
```

**GOAL** is the new type not in MAPS_OS_FEATURE_SPEC.md. Include it in all Stage 1 work.

### 1a. Config loader (`environments/maps_os_config.py`)

Create if not present. Loads `~/.maps_os_config.yaml`. Provides:

```python
def load_config() -> dict:
    """Returns config dict. Returns {} if file missing — never raises."""

def known_people() -> list[str]:
    """Returns config.get('known_people', []) lowercased."""
```

### 1b. `environments/vent_parser.py`

Add to `Entry.to_garden()`:
```python
if self.track == "PERSON":
    return f"PERSON: {self.date} | {self.note}"   # note = "name | context | sentiment"
if self.track == "DECISION":
    return f"DECISION: {self.date} | {self.note}"
if self.track == "RESISTANCE":
    return f"RESISTANCE: {self.date} | {self.note}"
if self.track == "TRIGGER":
    return f"TRIGGER: {self.date} | {self.note}"
if self.track == "GOAL":
    return f"GOAL: {self.date} | {self.note}"
```

Add extraction functions:

**`_extract_person_entries(text, date)`**
- Keywords: "talked to", "called", "texted", "plans with", "saw", "reached out to"
- Also match names from `known_people()` config list (case-insensitive)
- Infer sentiment: positive if text near the match contains "good", "great", "loved", "nice", "fun"; negative if "hard", "difficult", "drained", "upset"; else neutral
- `note` = `"name | context phrase | sentiment"`

**`_extract_decision_entries(text, date)`**
- Triggers: "i don't know if i should", "should i", "can't decide between", "not sure whether to", "weighing"
- `note` = short phrase capturing the dilemma

**`_extract_resistance_entries(text, date)`**
- Triggers: "i don't want to", "i keep avoiding", "can't bring myself to", "dreading", "the thought of", "can't start"
- Intensity: "dreading"/"can't face" = high; "don't want to"/"not feeling it" = medium; "maybe later" = low
- `note` = `"source phrase | intensity"`

**`_extract_trigger_entries(text, date)`**
- Triggers: "because [x] happened", "[person] said", "when i saw", "triggered by", "set off by"
- `note` = `"source | reaction"`

**`_extract_goal_entries(text, date)`**
- Triggers: "i want to", "i'd like to", "my goal is", "planning to", "hoping to", "i need to make sure", "i should really"
- Extract goal text as the phrase following the trigger up to end of sentence
- Default status = `open`, due = `none`
- `note` = `"description | none | open"`

**Update `parse_vent()`** — append all new entry types after existing dedup logic. PERSON, DECISION, RESISTANCE, TRIGGER, GOAL are not deduped (each instance is meaningful). Pattern: same as WIN.

### 1c. Enhanced body signal detection (`environments/vent_parser.py`)

In `_infer_body_status` (sleep inference), expand to distinguish:
- `broken`: "kept waking", "woke up at 3", "broken sleep", "woke up in the night"
- `restless`: "couldn't fall asleep", "tossed and turned", "can't sleep"
- `deep`: "slept through", "actually rested", "best sleep in", "finally slept"
- `overslept`: "slept too long", "slept 12 hours", "can't get up", "slept all day"

Existing values (`none`, `poor`, `ok`) stay. New values slot in between — no breaking changes to existing tests.

Add to `_BODY_SIGNALS` (pain location keywords):
- `"back hurts"`, `"neck stiff"`, `"eye strain"`, `"tension headache"`, `"shoulder pain"`, `"jaw tight"`

Add substance context patterns:
- Quantities: `"on my (second|third|fourth) coffee"`, `"(second|third) glass"`, `"another [drink]"`
- Timing: `"first thing in the morning"` (substance + timing = flag for substance_coping arc)

### 1d. New arcs (`environments/pattern_weaver.py`)

**ARC 20 — decision_pile (`_arc_decision_pile`)**
- Input: entries of track `DECISION`
- Fires: 3+ DECISION entries in last 7 days
- Message: `"you had {n} unresolved decision points this week. want to revisit any of them?"`
- Surface oldest first in message

**ARC 21 — trigger_pattern (`_arc_trigger_pattern`)**
- Input: entries of track `TRIGGER`
- Fires: 3+ TRIGGER entries with same source in last 30 days
- Message: `"you've logged {n} triggers from {source}. that's a pattern worth knowing."`

**ARC 22 — goal_stall (`_arc_goal_stall`)**
- Input: entries of track `GOAL` with status `open`
- Fires: any GOAL entry older than 14 days with no follow-up entry updating it to `in_progress` or `done`
- Message: `"'{goal}' has been open for {n} days. still relevant?"`
- Surface one at a time (oldest first)

Add all three to `weave()` — same pattern as existing arcs.

### 1e. Tests

Add to `tests/test_new_arcs.py`:
- ≥3 tests each for ARC 20, 21, 22
- ≥2 tests for each new `_extract_*` function (match + no-match)
- ≥2 tests for GOAL extraction

---

## Stage 2 — Visualization

All rendering: Rich only. No matplotlib, plotext, or external charting libs.

### 2a. `environments/viz.py` (new)

**`render_trend(entries, days=90)`**
- Input: list of STATE entries (filtered to last N days)
- Output: Rich `Text` block — Unicode bar chart
- One row per STATE tag seen in data (depleted/heavy/mixed/stable/thriving/manic)
- Each row: tag name (padded) + filled/empty block characters (`█`/`░`) per day
- Color per tag: use `STATE_COLORS` from tui.py (import or duplicate constants)
- Bottom: month labels aligned to columns
- Arc event annotation line: pull any Arc fires from entries if metadata present

**`render_viz(body_entries, state_entries, arc_history)`**
- Panel 1: state sparkline — last 14 days, one colored char per day
- Panel 2: body presence — last 7 days, sleep/hunger/pain/movement/energy rows, `■`/`·` per day
- Panel 3: arc frequency — which arcs fired most in last 30 days, Rich column bar

### 2b. New commands in `bin/maps`

**`maps trend [--days N]`**
- Query garden for STATE entries: `garden recall-sparql 'STATE:' --graph cassette --limit 200`
- Parse into list of (date, tag) pairs
- Pass to `render_trend()`, print with Rich
- Flags: `--days 30` / `--days 90` / `--days 365`; default 90. `--full` = all-time.

**`maps viz`**
- Query garden for BODY + STATE entries (last 30 days)
- Render with `render_viz()`, print with Rich

### 2c. TUI key bindings (`environments/tui.py`)

In `_draw_dashboard()`, add to the key bar:
```
  \[t]rend  \[V]iz
```
(note capital V to avoid clash with lowercase vent `\[v]`)

In the main input loop (where keys are dispatched), add:
- `t` → call `render_trend()` and print inline, then wait for keypress to return
- `V` → call `render_viz()` and print inline, then wait for keypress to return

---

## Stage 3 — Social tracking

### 3a. `maps connect <person> [--note text]` (`bin/maps`)

```bash
maps connect emma --note "good call, plans for friday"
maps connect --status
```

`connect <person>` writes two entries to garden:
- `SPIRIT: {date} | connection | rising | with {name}: {note}`
- `PERSON: {date} | {name} | {note} | positive`

`connect --status`:
- Query garden for all PERSON entries, group by name, find most recent per person
- Output: `{name}: last connection {date} ({N} days ago)` — one line per person
- Pull known people from `maps_os_config.known_people()` as the base list; supplement with any names found in PERSON entries

### 3b. Arc update (`environments/pattern_weaver.py`)

In `_arc_isolation_creep()`:
- If PERSON entries are available and a name can be identified, use it: `"you haven't connected with {name} in {n} days"` instead of the generic form
- Fall back to generic if no PERSON data

---

## Stage 4 — Calendar / Event integration

### 4a. `environments/date_resolver.py` (new)

```python
def resolve_date(text: str, today: date) -> Optional[date]:
    """Convert relative date phrases to ISO date. Returns None if unresolvable."""
```

Handles: "tomorrow", "today", "monday"–"sunday" (next occurrence), "next week", "next [weekday]", "in N days/weeks".

### 4b. New entry types in `environments/vent_parser.py`

```
EVENT: YYYY-MM-DD | event_date | description
DEADLINE: YYYY-MM-DD | due_date | task | urgency(low/medium/high)
```

**`_extract_event_entries(text, date, today)`**
- Triggers: "therapy on [day]", "have [something] on [day]", "that thing [day]", "appointment [day]"
- Use `resolve_date()` for event_date
- `note` = `"resolved_date | description"`

**`_extract_deadline_entries(text, date, today)`**
- Triggers: "due by", "before [date]", "deadline", "need to finish by", "submit by"
- Urgency: "urgent"/"asap"/"today" = high; explicit near date (≤3 days) = high; 4–7 days = medium; else low
- Use `resolve_date()` for due_date

**Route to nota** (in `nota_bridge.py` or `bin/maps`):
- After vent parsing, for each EVENT/DEADLINE entry, call:
  `nota add "{description}" --project calendar --due {date}` (if nota available)
- Wrap in try/except — nota routing is always best-effort

### 4c. `maps goal` command (`bin/maps`)

```bash
maps goal "learn enough swedish to hold a conversation"
maps goal "finish the album demo" --due 2026-06-01
maps goal --list          # show open goals from garden
maps goal --done "phrase"  # mark matching goal done
```

`goal <text> [--due date]`:
- Writes `GOAL: {date} | {text} | {due_or_none} | open` to garden
- If `--due` given, resolve date via `resolve_date()` if relative

`goal --list`:
- Query garden for GOAL entries with status `open`
- Display: `{description}  [due: {date}]  ({days_open} days open)`

`goal --done <phrase>`:
- Query GOAL entries, find closest match to phrase
- Write a new GOAL entry with same description but status `done` and today's date

### 4d. `maps events` command (`bin/maps`)

```bash
maps events          # upcoming events
maps events --week   # this week only
```

Query garden for EVENT: entries, filter by event_date >= today, sort ascending, display with Rich.

### 4e. Tests

- ≥3 tests for `resolve_date()` (relative → ISO)
- ≥2 tests for EVENT extraction
- ≥2 tests for DEADLINE extraction
- ≥2 tests for `maps goal` command (smoke tests via subprocess or direct function call)

---

## GOAL schema reference

```
GOAL: YYYY-MM-DD | description | due(YYYY-MM-DD or none) | status(open/in_progress/done)
```

- `open` — logged, not started
- `in_progress` — explicitly updated via `maps goal --update`
- `done` — completed via `maps goal --done`

Goals are append-only in garden — never update in place. A new entry with same description + new status supersedes the old. `--list` deduplicates by description and takes the most recent status.

---

## Rules for the implementing agent

- Run `python -m pytest tests/ -q` after each stage. All existing tests must stay green.
- Do not modify the garden write format for existing entry types (STATE, BODY, MIND, SPIRIT, INTENTION, WIN, FLASH).
- All new `_extract_*` functions: return `[]` on no match, never raise.
- All new Arc functions: return `None` or `[]` on insufficient data, never raise.
- Config (`~/.maps_os_config.yaml`) is always optional — missing file = degraded gracefully, never crashed.
- nota routing is always wrapped in try/except and gated on `nota_available()`.
- New optional deps (aiohttp, pycrdt) document in requirements.txt as `# optional: <feature>`.
- No hardcoded names, people, or personal data anywhere in source.

---

*maps · cassette.help · MIT*
