# maps-os: Feature Specification
**Date:** 2026-04-10 (updated)
**Status:** Living document — updated after each build phase
**Maintainer:** maps · cassette.help

This document specifies features beyond the current Phase 2 build. Priority order is listed per section. Features marked **[SPEC]** need a design pass before build. Features marked **[READY]** have enough detail to build from this doc.

---

## Implemented — Phase 2 → 2.1

- ✅ nota integration in `maps vent` (action items extracted and routed to nota, same as tulpa)
- ✅ WIN entry extraction from vent text (pattern-based, conservative)
- ✅ ARC 17: substance_coping — STATE heavy + substances logged → silent flag, pattern-output only
- ✅ ARC 18: avoidance_language — 2+ avoidance phrases in recent vent notes → early detection
- ✅ ARC 19: habit_candidate — intention logged 5+ times at ≥60% met rate → suggest harsh habit
- ✅ Heavy emotion handling mode documented in SKILL.md
- ✅ `maps` symlinked to `~/.bin/maps`

## Implemented — Phase 2.2–2.5

- ✅ `environments/maps_os_config.py` — config loader for `~/.maps_os_config.yaml`, `known_people()`
- ✅ PERSON entry type — extracted from vent, sentiment-inferred, written to garden
- ✅ DECISION entry type — extracted from vent on decision-language triggers
- ✅ RESISTANCE entry type — extracted from vent on avoidance triggers, intensity-inferred
- ✅ TRIGGER entry type — extracted from vent on trigger-language (note: patterns still too broad, see Phase 2.6 bug fixes)
- ✅ GOAL entry type — extracted from vent on goal-language triggers; also writable via `maps goal`
- ✅ EVENT entry type — extracted from vent + date-resolved (note: NOT yet wired into parse_vent, see Phase 2.6 bug fixes)
- ✅ DEADLINE entry type — extracted from vent + urgency-inferred (note: NOT yet wired into parse_vent, see Phase 2.6 bug fixes)
- ✅ Enhanced body signal detection — sleep granularity (broken/restless/deep/overslept), pain locations, substance context
- ✅ ARC 20: decision_pile — 3+ DECISION entries in 7 days → surface for review
- ✅ ARC 21: trigger_pattern — 3+ TRIGGER entries from same source in 30 days (note: missing 30-day window filter, see Phase 2.6 bug fixes)
- ✅ ARC 22: goal_stall — GOAL open >14 days → prompt relevance check (note: field index bug, see Phase 2.6 bug fixes)
- ✅ `environments/viz.py` — `render_trend()`, `render_viz()`, `render_trend_simple()`
- ✅ `maps trend [--days N]` CLI command
- ✅ `maps viz` CLI command
- ✅ TUI `[t]`/`[V]` key bindings for trend and viz
- ✅ `maps connect <person> [--note text]` — logs SPIRIT.connection + PERSON entries
- ✅ `maps connect --status` — shows last connection date per known person
- ✅ `_arc_isolation_creep` updated to use PERSON data when available
- ✅ `environments/date_resolver.py` — relative date → ISO resolution
- ✅ `maps goal <text> [--due date]` — writes GOAL entry to garden
- ✅ `maps goal --list` — shows open goals
- ✅ `maps goal --done <phrase>` — marks goal done by appending new entry
- ✅ `maps events [--week]` — shows upcoming events from EVENT entries

## Known bugs (Phase 2.5 → 2.6 fixes)

See `AGENT_BUILD_GUIDE.md` Stage 0 for precise fix instructions.

1. **EVENT/DEADLINE not wired into parse_vent()** — extraction functions exist but are never called. Events and deadlines from vent text are silently dropped.
2. **ARC 22 goal_stall field index wrong** — checks `parts[2]` (the `due` field) for `"open"` instead of `parts[3]` (the `status` field). Arc will never fire.
3. **Trigger extraction too broad** — `"because"` and `"said"` as bare patterns match nearly all text. Generates constant noisy TRIGGER entries.
4. **Event extraction too broad** — `"have"` and `"on"` as bare patterns match nearly all text.
5. **Dead code in _arc_decision_pile** — ~30-line duplicate implementation block after first `return None` is unreachable.
6. **date_resolver.py duplicate tuple** — `if t in ("tomorrow", "tomorrow"):` — both strings identical.
7. **viz.py body panel date-blind** — per-day presence check ignores the day variable; every cell shows same value.

---

## Priority 1 — Enhanced vent parsing ✅ DONE

All entry types implemented. See "Known bugs" section above for two issues that still need fixing (trigger patterns too broad, EVENT/DEADLINE not wired into parse_vent).

---

## Priority 2 — Visualization ✅ DONE

`environments/viz.py`, `maps trend`, `maps viz`, TUI `[t]`/`[V]` bindings — all implemented.

Open issue: viz.py body panel date-blind bug (see Known bugs #7 above).

---

## Priority 3 — Social Tracking ✅ DONE

`maps connect`, `maps connect --status`, `_arc_isolation_creep` name-aware — all implemented.

---

## Priority 4 — Calendar / Event Integration ✅ DONE (partial)

`environments/date_resolver.py`, EVENT/DEADLINE entry types, nota routing in `maps vent`, `maps goal`, `maps events` — implemented.

Open issue: EVENT/DEADLINE extraction functions exist but are not called from `parse_vent()` (see Known bugs #1 above). Also `maps goal --update` is missing (see Phase 2.6 Stage 1b).

---

## Implemented — Phase 2.6 Stage 0 (codex, 2026-04-10)

All 7 documented bugs fixed. ARC 15 planning_hyperfocus also fixed as a bonus (date comparison now uses entry date instead of wall-clock today). Additional CLI schema fixes:
- `maps goal --list` and `maps goal --done` now read the correct GOAL status field (parts[3])
- `maps events` correctly reads stored EVENT rows and filters by --week
- `maps check` and `maps pattern` now pass DECISION/TRIGGER/GOAL/PERSON data into `weave()` so ARCs 20-22 can actually fire
- Test suite: 168 passing, 0 failing (was 152 passing, 1 failing)
- New test files: `tests/test_phase26_fixes.py`, `tests/test_cli_commands.py`

## Priority 4.5 — Phase 2.6 remaining [READY]

Stages 1-4 from `AGENT_BUILD_GUIDE.md` still pending:

- **`maps wins [--week] [--month]`** — surface WIN entries grouped by week (Stage 1a)
- **`maps goal --update <phrase>`** — mark goal in_progress (Stage 1b)
- **`maps eval`** — intention met rate + STATE distribution + arc count (Stage 1c)
- **ARC 23: resistance_pattern** — 3+ RESISTANCE entries, same source, 14 days (Stage 2)
- **ARC 24: negative_interaction_pattern** — 3+ negative PERSON entries for same name, 30 days (Stage 2)
- **Arc cooldown/suppression** — per-arc configurable suppress window, persisted to `~/.maps_os_cooldown.json` (Stage 3)
- **ARC 25: exec_dysfunction** — RESISTANCE high + GOAL stalled + STATE depleted/flooded/manic → cross-track correlation (Stage 4)

## Priority 4.6 — Person accumulation + astrolog profiles [READY]

See `AGENT_BUILD_GUIDE.md` Stage 6 for full spec.

Two parallel concerns:

**Relationship profiles** (`~/.hermes/people/{name}.json`) — accumulate from every PERSON entry written to garden. Last contact, sentiment history, context notes, contact count. Auto-updated from `maps vent` and `maps connect`. Surfaced via `maps person <name>`.

**Astrolog profiles** (`~/.hermes/astrolog/{name}_profile.json`) — require birth data for chart generation. Already exist for: ann, kadellyn, maggie, maps, max, sarah. Skeleton profiles (null birth data, flagged as needing info) should be created for all `known_people` who don't have one yet. Promoted to full profiles when birth data is provided via `maps person <name> --birth`.

Config extended with a `people:` section for seeding initial role/notes context without requiring PERSON entries to exist first.

---

## Priority 4.7 — Architecture / UX Improvements [SPEC]

These are not new tracking domains so much as cleanup and leverage improvements discovered while implementing Phase 2.6. They should reduce future bug volume and make the next round of features easier to build correctly.

### 1. Canonical people + aliases

**Current problem:** PERSON extraction and listing still use raw string names. Alias cases (`b` vs `brennan`) and short names (`ann`) are fragile. Distinct people with similar names are safer now (`emma` vs `emma-x`) but the system still lacks a canonical person identity.

**Proposed behavior:**
- Extend config `people:` entries with optional `aliases: []`
- Resolve all aliases to a canonical person id before writing PERSON entries
- Match names on word boundaries, not plain substring containment
- `maps person --list` should hide alias-only rows by default

**Why it matters:** This prevents duplicate identities, reduces false positives, and gives future arcs a stable person key instead of free-form text.

**Likely files:** `environments/maps_os_config.py`, `environments/vent_parser.py`, `bin/maps`

---

### 2. Shared entry codec / schema parser

**Current problem:** Many commands still hand-parse garden strings independently. This caused the GOAL/EVENT bugs fixed in Phase 2.6, and it leaves similar risks for PERSON, DEADLINE, WIN, and future entry types.

**Proposed behavior:**
- Create one schema-aware parser/formatter module for all track types
- Move string splitting logic out of `bin/maps`, `pattern_weaver.py`, and visualization helpers
- Keep `Entry.to_garden()` as the write path or wrap it behind the shared codec

**Why it matters:** New commands and arcs should not each rediscover where `status` or `due` lives in a pipe-delimited string.

**Likely files:** new `environments/entry_codec.py`, refactors in `bin/maps`, `environments/pattern_weaver.py`, `environments/viz.py`, `environments/vent_parser.py`

---

### 3. Real date-window filtering

**Current problem:** Several commands approximate "recent" using `limit=N` instead of an actual date window. This is good enough for smoke use but not for reliable `--week`, `--month`, review, or future arc logic.

**Proposed behavior:**
- Add shared date filtering helpers for recalled entries
- Use true date cutoffs for `maps wins`, `maps eval`, `maps review`, `maps events`, and future arcs
- Standardize "this week", "last 7 days", "this month", and custom range semantics

**Why it matters:** Time-based insights should be based on dates, not whatever happened to be in the last N recalled rows.

**Likely files:** new helper in `environments/`, updates in `bin/maps`, future use in `pattern_weaver.py`

---

### 4. Arc evidence + persisted arc history

**Current problem:** `maps pattern` surfaces arc names/messages, but there is no persisted arc history and no direct "why did this fire?" evidence trail. `maps eval` also cannot report arc frequency meaningfully yet.

**Proposed behavior:**
- Persist fired arcs locally or to garden in a lightweight `ARC:` history format
- Store supporting evidence snippets / counts in the payload
- Add `maps pattern --why` or similar verbose mode
- Upgrade `maps eval` and `maps report` to use real arc history

**Why it matters:** Visibility turns pattern output from a black box into something inspectable and reviewable over time.

**Likely files:** `environments/pattern_weaver.py`, `bin/maps`, optional new `environments/arc_history.py`

---

### 5. Safe garden subprocess wrapper

**Current problem:** Garden writes/recalls in `local_store.py` still use shell-quoted command strings. This is brittle for apostrophes in vent text and creates avoidable parsing/safety edge cases. The module also still uses deprecated `datetime.utcnow()`.

**Proposed behavior:**
- Replace shell command strings with argv-based subprocess calls
- Centralize garden invocation in one helper
- Use timezone-aware UTC timestamps for the local store

**Why it matters:** This is low-glamour infrastructure work that will remove a whole class of quoting bugs and future deprecation issues.

**Likely files:** `environments/local_store.py`

---

### 6. Config schema v2

**Current problem:** Stage 6 currently bridges some astrolog-init data from YAML comments. That works, but comment parsing is still a stopgap, not a clean long-term schema.

**Proposed behavior:**
- Keep comments human-readable only
- Add optional machine-readable fields under `people:` for birth date, birth place, current place, aliases, and relationship metadata
- Continue to degrade gracefully if those fields are absent

**Why it matters:** Structured config should be the source of truth for structured behavior. Comments should stay optional annotation.

**Likely files:** `environments/maps_os_config.py`, docs, maybe migration helper

---

### 7. `maps doctor`

**Current problem:** There is no single command to validate garden connectivity, pending local queue, config parsing, known people aliases, astrolog profile status, or schema drift.

**Proposed behavior:**
```bash
maps doctor
```

**Output should include:**
- garden reachable / unreachable
- pending local entries count
- config loaded / malformed
- duplicate people / alias collisions
- missing astrolog profiles
- possibly stale open goals or malformed entries

**Why it matters:** This is the fastest way to debug a personal system that spans config, local persistence, garden, and optional integrations.

**Likely files:** `bin/maps`, `environments/local_store.py`, `environments/maps_os_config.py`

---

### 8. `maps parse --dry-run`

**Current problem:** Parser tuning is awkward because the only way to inspect extracted entries is to log them or read code/tests.

**Proposed behavior:**
```bash
maps parse "therapy on thursday and i keep avoiding joe"
```

Print the entries that would be emitted, without writing to garden or local store.

**Why it matters:** This will speed up extractor debugging and make future pattern/parser iteration much less error-prone.

**Likely files:** `bin/maps`, `environments/vent_parser.py`

---

### 9. Person maintenance commands

**Current problem:** Stage 6 adds person viewing and astrolog skeleton init, but follow-up maintenance still requires config edits by hand.

**Proposed behavior:**
- `maps person <name> --birth "YYYY-MM-DD HH:MM City"` — update astrolog profile metadata
- `maps person <name> --alias foo` — attach alias to canonical person
- `maps person --merge alias canonical` — reconcile duplicate identities if alias support lands

**Why it matters:** The people system becomes much more useful once the CLI can evolve it directly instead of leaving all upkeep in YAML edits.

**Likely files:** `bin/maps`, `environments/maps_os_config.py`, astrolog profile helpers

---

### 10. Person/context filters for review + pattern output

**Current problem:** Review output is global. Once PERSON and EVENT data accumulate, there is no way to ask focused questions like "show me the Maggie pattern" or "what happens around therapy days?"

**Proposed behavior:**
```bash
maps review --person maggie
maps pattern --person chris
maps review --context work
```

**Why it matters:** Filtering turns maps-os from a broad personal dashboard into a tool for targeted reflection on relationships, work, family, or recurring contexts.

**Likely files:** `bin/maps`, future context tagging/parser work, shared date/filter helpers

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
- Surface as **ARC 26** (`cycle_prediction`) with low confidence warning if < 5 transitions
- Note: ARCs 20–25 are already allocated (20-22: Phase 2.2-2.5; 23-25: Phase 2.6)

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
