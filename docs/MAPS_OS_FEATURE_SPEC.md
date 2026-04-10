# maps-os: Feature Specification
**Date:** 2026-04-09
**Status:** Spec — pending implementation by assigned agent
**Maintainer:** maps · cassette.help

This document specifies features beyond the current Phase 2 build. Priority order is listed per section. Features marked **[SPEC]** need a design pass before build. Features marked **[READY]** have enough detail to build from this doc.

---

## Already implemented in this session (Phase 2 → 2.1)

- ✅ nota integration in `maps vent` (action items extracted and routed to nota, same as tulpa)
- ✅ WIN entry extraction from vent text (pattern-based, conservative)
- ✅ ARC 17: substance_coping — STATE heavy + substances logged → silent flag, pattern-output only
- ✅ ARC 18: avoidance_language — 2+ avoidance phrases in recent vent notes → early detection
- ✅ ARC 19: habit_candidate — intention logged 5+ times at ≥60% met rate → suggest harsh habit
- ✅ Heavy emotion handling mode documented in SKILL.md
- ✅ `maps` symlinked to `~/.bin/maps`

---

## Priority 1 — Enhanced vent parsing [READY]

### Person/Name Tracking
**New entry type:** `PERSON: {date} | {name} | {context} | {sentiment}`

**Detection:** Named persons in connection/spirit context. Configurable name list at `~/.maps_os_config.yaml` under `known_people`. Fallback: proper nouns following "talked to", "called", "texted", "plans with", "saw", "reached out to".

**Implementation:**
- Add `_extract_person_entries()` to `vent_parser.py`
- Config file: `known_people: [emma, lior, maggie, ...]` — must be user-configured, never hardcoded
- `to_garden()` format: `PERSON: 2026-04-09 | emma | called, plans for friday | positive`
- Update `_arc_isolation_creep` in `pattern_weaver.py` to use PERSON data: "you haven't connected with emma in 12 days" instead of generic

**File:** `environments/vent_parser.py`, `environments/pattern_weaver.py`, new `environments/maps_os_config.py`

---

### Enhanced Body Signal Detection
**Expand `_BODY_SIGNALS` keyword lists:**
- Sleep granularity: distinguish `none` / `broken` / `restless` / `poor` / `ok` / `deep` / `overslept` in `_infer_body_status`
  - broken: "kept waking", "woke up at 3", "broken sleep"
  - restless: "couldn't fall asleep", "tossed and turned"
  - deep: "slept through", "actually rested", "best sleep in"
  - overslept: "slept too long", "slept 12 hours", "can't get up"
- Pain specificity: add location keywords ("back hurts", "neck stiff", "eye strain", "tension headache")
- Substance context: add quantities ("on my third coffee", "second glass") and timing ("first thing in the morning")

**File:** `environments/vent_parser.py`

---

### Decision Point Logging
**New entry type:** `DECISION: {date} | {framing} | {options}`

**Detection:** "i don't know if i should", "should i", "can't decide between", "not sure whether to", "weighing"

**Pattern arc:** If 3+ unresolved DECISION entries in last 7 days → "you had 3 unresolved decision points this week. want to revisit any of them?" Surface oldest first.

**File:** `environments/vent_parser.py`, new arc in `environments/pattern_weaver.py`

---

### RESISTANCE Logging
**New entry type:** `RESISTANCE: {date} | {source} | {intensity: low/medium/high}`

**Detection:** "i don't want to", "i keep avoiding", "can't bring myself to", "dreading", "the thought of", "can't start"

**Intensity inference:** "dreading" / "can't face" = high; "don't want to" / "not feeling it" = medium; "maybe later" = low

**Relationship to ARC 18:** ARC 18 fires on language patterns. RESISTANCE entries are structured data that builds the domain neglect picture over time.

**File:** `environments/vent_parser.py`

---

### TRIGGER Logging
**New entry type:** `TRIGGER: {date} | {source} | {reaction}`

**Detection:** "because [x] happened", "[person] said", "when i saw", "triggered by", "set off by"

**Pattern arc:** N triggers from same source in 30 days → "you've logged [N] triggers from [source]. that's a pattern worth knowing."

**File:** `environments/vent_parser.py`, new arc

---

## Priority 2 — Visualization [SPEC]

### `maps trend` — Long-term STATE timeline

**Output (TUI, Rich-rendered):**
```
STATE timeline — last 90 days

  depleted  ████░░░░░░░░░░░░████████░░░░░
  grieving  ░░░░██░░░░░░░░░░░░░░░░░░░░░░░
  stable    ░░░░░░██████░░░░░░░░░░████░░░
  thriving  ░░░░░░░░░░░░████░░░░░░░░░░░░░
            Jan          Feb          Mar

arc events: ↑ manic_spike (jan 14) · ↓ survival mode (jan 28–feb 3)
```

**Implementation notes:**
- Query: `garden recall-sparql 'STATE:' --graph cassette --limit 200`
- Parse date from `STATE: YYYY-MM-DD | tag | ...` format
- Render using Rich `Table` + colored block characters (no external charting lib)
- Timeframe flags: `--days 30` / `--days 90` / `--days 365`
- `maps trend --full` = all-time

**Files:** new `environments/viz.py`, new command in `bin/maps`

---

### `maps viz` — Session-scoped dashboard

Shows BODY/MIND/SPIRIT balance as a TUI panel alongside state. Supplements the main TUI.

**Panels:**
1. State strip: last 14 days of STATE tags (colored sparkline)
2. Body radar: sleep/hunger/pain/movement/energy — last 7 days, presence/absence
3. Arc frequency: which arcs have fired most in last 30 days (bar chart, Rich columns)

**Implementation notes:**
- Use Rich `Columns` and `Panel` — same as existing TUI aesthetic
- Run as separate command (`maps viz`) or toggled in TUI with `v` key
- All data from SPARQL fallback — no semantic search needed

**Files:** `environments/viz.py`, `environments/tui.py` (add `v` toggle)

---

### TUI Enhancements

**`maps trend` and `maps viz` should be navigable from within the TUI:**
- `t` → trend view (or toggle inline)
- `v` → viz dashboard
- `h` → help/keymap

**Rich-based palette:** Keep the warm amber aesthetic. State colors already defined in `tui.py STATE_COLORS`. Extend to trend renders.

**Design principle:** No external viz libs (matplotlib, plotext, etc). Rich `Text`, `Panel`, `Table`, and Unicode block characters only. Looks better on fixed-width terminals, no install friction.

---

## Priority 3 — Social Tracking [READY]

### `maps connect <person> [--note text]`

New top-level command. Logs a SPIRIT.connection entry with the named person.

```bash
maps connect emma --note "good call, plans for friday"
maps connect --status
# → emma: last connection 2026-04-07 (2 days ago) · plans pending
# → lior: last connection 2026-03-28 (12 days ago)
```

**Implementation:**
- `connect` command logs: `SPIRIT: {date} | connection | rising | with {name}: {note}`
  *and* `PERSON: {date} | {name} | {note} | positive`
- `connect --status` queries garden for last PERSON entry per known person, computes days-ago
- Arc update: `_arc_isolation_creep` uses PERSON entries when available — names the person instead of generic "haven't logged connection"

**Known people list:** from `~/.maps_os_config.yaml` `known_people` key. Fallback: extract from all PERSON entries in garden.

**Files:** `bin/maps` (new command), `environments/pattern_weaver.py` (arc update), `environments/maps_os_config.py` (new)

---

## Priority 4 — Calendar / Event Integration [SPEC]

### EVENT and DEADLINE entries from vent

**New entry types:**
- `EVENT: {date} | {event_date} | {description}`
- `DEADLINE: {date} | {due_date} | {task} | {urgency: low/medium/high}`

**Detection:**
- EVENT: "therapy on tuesday", "that thing tomorrow", "have [something] on [day]"
- DEADLINE: "due by", "before [date/day]", "deadline", "need to finish by", "submit by"
- Relative date resolution: "tomorrow" / "friday" / "next week" → ISO date (from today's date)

**Implementation notes:**
- Date resolution utility: `environments/date_resolver.py` — converts relative dates to ISO
- EVENT/DEADLINE entries flow to nota via a new `route_events_to_nota()` in `nota_bridge.py`
- nota has `caltask` and `calpull` in PATH — these are the integration point
- Format for nota: `nota add "therapy" --project calendar --due {resolved_date}`

**Calendar backend decision:**
- nota task calendar (`caltask`/`calpull`/`calpush`) is the current best integration target
- No iCal/CalDAV dependency — keeps it offline-capable
- If maps adds a proper calendar later, the EVENT: schema persists and a new bridge handles export

**Files:** new `environments/date_resolver.py`, `environments/vent_parser.py`, `environments/nota_bridge.py`

---

### `maps events` command

```bash
maps events           # show upcoming events from EVENT: entries
maps events --week    # this week only
maps events --add "therapy thursday 3pm"  # manual entry
```

Query: SPARQL for `EVENT:` entries, sort by event_date.

---

## Priority 5 — Cycle Prediction [SPEC]

After 90+ days of STATE data:

```
→ you're in a manic spike now.
  historically, you drop to depleted 2-3 days after.
  plan for it: what's the one thing to do before the drop?
```

**Implementation approach:**
- Requires sufficient historical data (90+ STATE entries)
- Pattern: find manic → depleted transitions in history, compute median gap
- Surface as ARC 20 (`cycle_prediction`) with low confidence warning if < 5 transitions

**Files:** `environments/pattern_weaver.py` (new arc), query SPARQL for historical STATE entries

---

## Priority 6 — Retroactive Logging [READY]

### `--date` flag already exists on most commands

Extend to explicit retroactive logging with processing delay tracking:

```bash
maps state grieving --date 2026-04-01 --note "realized i was grieving this"
# → logs STATE + RETROACTIVE: entry with processing_delay = N days
```

**New entry type:** `RETROACTIVE: {log_date} | {event_date} | {processing_delay_days}`

Pattern arc: "your average processing delay is N days" after 5+ retroactive entries. Not surfaced until data is sufficient.

**Files:** `bin/maps` (minor), `environments/vent_parser.py` (RETROACTIVE entry type)

---

## Priority 7 — `maps report` Export [SPEC]

```bash
maps report --month april
maps report --range 2026-03-01/2026-04-09
maps report --format text    # default, terminal-printable
maps report --format markdown # for therapy/review docs
```

**Content:** STATE summary by week, dominant arcs, intention completion rate, wins, key events.

**Implementation:**
- No PDF generation (avoids wkhtmltopdf/weasyprint dep hell)
- Markdown output → user can convert with pandoc if needed
- Rich terminal output with section headers

**Files:** new `environments/report.py`, new command in `bin/maps`

---

## Priority 8 — Voice Input [SPEC]

```bash
maps speak        # record → transcribe → vent
maps speak --5s   # short clip
```

**Implementation:**
- macOS: `say` for TTS already exists. For STT: `whisper.cpp` or OpenAI Whisper API
- Record via `sounddevice` + `scipy` OR system `afrecord` (macOS)
- Pipe transcription to `parse_vent()` — no other changes needed
- Optional: `MAPS_WHISPER_API_KEY` env var for OpenAI path; fall back to `whisper.cpp` if available

**Files:** new `bin/maps-speak` wrapper, optional `environments/transcribe.py`

---

## Priority 9 — Trusted Contact Alert [SPEC]

**Trigger:** survival mode active for 7+ consecutive days with no exit.

**Behavior:**
- Prompt ONCE: "survival mode has been active for 7 days. want to let someone know?"
- If yes: `maps contact --alert` → shows configured contact, confirms before any action
- Never automatic. Requires explicit MAPS_TRUSTED_CONTACT config and user confirmation each time.
- No automatic messaging. Only: display contact info + optional copy-to-clipboard message.

**Files:** `environments/survival_mode.py`, `bin/maps` (new contact command)

---

## Notes for implementing agents

- All new entry types (PERSON, WIN, DECISION, RESISTANCE, TRIGGER, RETROACTIVE, EVENT, DEADLINE) follow the same `TRACK: date | field | field | note` format
- All new garden remember calls use `--graph cassette` (default)
- New arcs get numbers 20+ — document in pattern_weaver.py header
- All new commands must work in non-TTY mode (pipe-safe, no interactive prompts without TTY check)
- New optional dependencies: document in `requirements.txt` as optional with `# optional: <feature>`
- Test coverage: each new arc gets ≥3 tests in `tests/test_new_arcs.py`; new commands get smoke tests

---

*maps · cassette.help · MIT*
