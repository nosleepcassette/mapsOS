# maps-os

![maps-os](mapsOS.png)

A qualitative life operating system for neurodivergent, hyperlexical brains.

Not a habit tracker. Not a mood journal. Not a productivity app.

maps-os tracks **narrative states**, detects **arc patterns** across days and weeks, and knows when to collapse everything to survival basics. It runs as a standalone CLI and TUI, logs to a garden knowledge graph (with local SQLite fallback), and feeds an Atropos RL training environment.

Built for maps. Forked from [hermes-life-os](https://github.com/nosleepcassette/hermes-life-os).

---

## What It Tracks

### STATE
The primary axis. One tag per session — the dominant emotional/psychological reality.

| Tag | Meaning |
|-----|---------|
| `surviving` | minimal function, getting through |
| `stable` | neutral baseline, nothing wrong, nothing lit |
| `thriving` | genuine forward momentum, things clicking |
| `grieving` | loss-adjacent (person, phase, possibility) |
| `manic` | elevated, fast, possibly unsustainable |
| `depleted` | tank empty, may still be functional |
| `flooded` | emotionally overwhelmed, nervous system loud |
| `clear` | post-storm clarity, unusual perceptual sharpness |

### BODY / MIND / SPIRIT
Three tracks that can diverge wildly from each other.

- **BODY** — sleep, pain, hunger, movement, substances, energy
- **MIND** — focus, clarity, overwhelm, flow
- **SPIRIT** — connection, creativity, purpose, isolation

### Extended Tracking
Extracted automatically from vent text or logged via CLI:

| Track | What it captures |
|-------|-----------------|
| `WIN` | Executive function wins — things done despite resistance |
| `PERSON` | People in orbit — contact, context, sentiment |
| `DECISION` | Unresolved choice points |
| `RESISTANCE` | Internal friction — knowing what to do but not being able to start |
| `TRIGGER` | Events that shifted state |
| `GOAL` | Longer-arc intentions with status tracking |
| `EVENT` | Upcoming calendar events, auto-extracted from vent |
| `DEADLINE` | Time-sensitive obligations |
| `FLASH` | Sub-threshold signals — no structure, just capture |

### INTENTIONS
Not habits. Not streaks. Just honest tracking of what was tried.
`met` / `missed` / `partial` — no judgment in the schema.

---

## CLI Reference

```bash
# core tracking
maps vent "i'm exhausted but i can't sleep"   # full parser → auto-log
maps flash "laundry"                                  # sub-threshold capture, no structure
maps state thriving "post-tender clarity"          # direct state log
maps body sleep none "up since 5am"               # direct body log
maps mind flow high "6hr build session"           # direct mind log
maps spirit connection rising "good call"
maps intention water missed "forgot again"
maps intention movement met "dog park 45min"

# session + pattern
maps check                    # session start: context pull + arc check
maps pattern                  # full pattern weaver output
maps review                   # cycle review (last 14 days)
maps survival                 # check / display survival mode

# extended capture
maps tulpa                    # multi-line stream capture
                              # end with /done or Ctrl+D

# wins + goals
maps wins                     # recent wins, grouped by week
maps wins --week              # this week only
maps wins --month             # this month only
maps goal "sort housing"      # log a new goal
maps goal --due 2026-05-24 "housing"
maps goal --list              # open goals
maps goal --done <phrase>     # mark complete
maps goal --update <phrase>   # mark in_progress

# events + deadlines
maps events                   # upcoming events
maps events --week            # this week only

# people
maps person chungus           # profile + recent interactions + astrolog status
maps person --list            # all known people + last contact
maps person --init-astrolog   # create skeleton profiles for everyone without one

# visualization
maps trend                    # STATE trend (last 30 days)
maps trend --days 7           # shorter window
maps viz                      # body/state/arc dashboard

# system
maps eval                     # cassette performance trend (last 30 days)
maps eval --days 7
maps connect <name>           # log connection + PERSON entry
maps connect --status         # last contact per known person
maps sync                     # flush local store to garden
maps sync --status            # pending entry count
```

Running `maps` with no arguments in a TTY launches the TUI.

---

## TUI

```bash
python3 bin/maps
```

Requires `rich`. No Textual dependency — raw termios + Rich.

Warm amber palette. STATE-specific colors. Dashboard, survival, vent, flash, state, body, mind, spirit, intention, review, help, and sync screens.

| Key | Action                  |
|-----|-------------------------|
| `v` | vent                    |
| `f` | flash                   |
| `s` | state                   |
| `b` | body                    |
| `m` | mind                    |
| `S` | spirit                  |
| `i` | intention               |
| `r` | review                  |
| `c` | refresh / pattern check |
| `y` | sync local store        |
| `?` / `h` | help              |
| `q` | quit                    |

---

## Pattern Weaving — 25 Arcs

After every vent and at session start, the pattern weaver runs across recent entries and surfaces arcs. Each arc has a suppression cooldown — arcs don't repeat every session while conditions persist.

### Alert arcs (one at a time, highest priority)

| Arc | Trigger | Cooldown |
|-----|---------|---------|
| `manic_spike` | Manic/depleted + no sleep + high flow | 1 day |
| `body_neglect` | High flow + hunger ignored or no movement | 1 day |
| `isolation_creep` | 3+ isolation logs or 5+ days no connection | 2 days |
| `state_dip_holding` | 2+ low states in last 3 — triggers survival mode | never suppressed |

### Insight arcs (all that apply)

| Arc | Trigger | Cooldown |
|-----|---------|---------|
| `spirit_rising` | Connection rising while state is low | 3 days |
| `post_manic_drop` | Was manic, now depleted/stable | 2 days |
| `thriving_streak` | 3 consecutive thriving | 3 days |
| `productivity_spiral` | Manic/depleted + work language + no spirit tracked | 2 days |
| `catastrophizing_spike` | Catastrophizing phrases in vent notes | 1 day |
| `planning_hyperfocus` | Planning language + high mind + no intentions today | 1 day |
| `substance_coping` | Substances logged during heavy state | 3 days |
| `avoidance_language` | 2+ avoidance phrases in recent vents | 2 days |
| `habit_candidate` | Intention logged 5+ times at ≥60% met rate | — |
| `decision_pile` | 3+ unresolved DECISION entries in 7 days | 3 days |
| `trigger_pattern` | 3+ TRIGGER entries from same source in 30 days | 7 days |
| `goal_stall` | GOAL open >14 days | 7 days |
| `resistance_pattern` | 3+ RESISTANCE entries, same source, 14 days | 5 days |
| `negative_interaction_pattern` | 3+ negative PERSON entries, same person, 30 days | 7 days |
| `exec_dysfunction` | High RESISTANCE + stalled GOAL + low/dysregulated STATE simultaneously | — |
| `intrusive_loop` | Same topic in 3+ flash entries | — |

### Behavioral arcs (response calibration, not code)

- `avoidance_loop` — same task mentioned 3+ times without resolution
- `trust_rupture` — lied/betrayed in vent → suppress everything, just witness
- `context_inheritance` — session start state comparison
- `state_memory_loss` — nudge 48+ hours after logged state with no follow-up

---

## Survival Mode

Triggers when STATE has been `depleted` or `grieving` for 2+ of the last 3 entries.

In survival mode:
- Logging collapses to STATE + BODY only
- All arcs suppressed except body neglect
- Briefing is exactly three items: eat, sleep, water
- No productivity language anywhere

Exits when a non-low state is logged.

---

## Arc Cooldown

Arcs are suppressed after firing to prevent alert fatigue. A `manic_spike` that lasts three days won't fire three sessions in a row. Cooldowns persist to `~/.maps_os_cooldown.json`.

Survival-severity arcs (`state_dip_holding`) are never suppressed.

---

## Garden Failsafe

If garden is unavailable, entries write to `~/.maps_os_local.db`. When garden comes back, `maps sync` flushes the queue. The system never loses data.

---

## Person Context

`~/.maps_os_config.yaml` maintains a `known_people` list for name extraction from vent text, plus a `people:` section with role/notes for each person.

```bash
maps person --list            # everyone + last contact
maps person maggie            # recent interactions, role, astrolog status
maps person --init-astrolog   # scaffold ~/.hermes/astrolog/{name}_profile.json
```

Astrolog skeleton profiles at `~/.hermes/astrolog/` link relational context to birth chart data. Birth data filled in separately when known.

---

## Installation

```bash
git clone https://github.com/nosleepcassette/hermes-maps-os
cd hermes-maps-os
pip install rich
chmod +x bin/maps
export PATH="$PATH:$(pwd)/bin"
```

**Dependencies:**
- Python 3.10+
- `rich` (TUI only — CLI works without it)
- `garden` (knowledge graph — optional, local store is the fallback)
- `nota` (task routing — optional, detected automatically)
- `eidetic` (verbatim logging — optional, detected automatically)

---

## RL Training

`environments/maps_os_env.py` is an Atropos-compatible RL training environment. 13 scenarios across vent, session start, survival, cycle review, and intention log modes.

Reward weights:

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| `state_logged` | 0.25 | Did maps log STATE? |
| `correct_state` | 0.20 | Valid and contextually appropriate tag |
| `track_coverage` | 0.20 | BODY/MIND/SPIRIT covered |
| `tool_coverage` | 0.15 | Expected tools used |
| `no_streak_language` | 0.10 | No pressure vocabulary |
| `survival_correct` | 0.10 | Survival mode handled correctly |

Passive evaluation: `~/.hermes/hooks/post_session_life_os.py` fires after sessions and logs to `~/.hermes/logs/.atropos-history.json`. View trends with `maps eval`.

---

## Tests

```bash
python3 -m pytest tests/ -v
```

196 tests covering: vent parser, pattern weaver (ARCs 1–25), arc cooldown, survival mode, CLI commands, local store, RL environment.

---

## Project Structure

```
hermes-maps-os/
├── bin/
│   └── maps                    — CLI entry point (human + agent facing)
├── environments/
│   ├── vent_parser.py          — free-form text → structured entries
│   ├── pattern_weaver.py       — arc detection (ARCs 1–25)
│   ├── arc_cooldown.py         — per-arc suppression, ~/.maps_os_cooldown.json
│   ├── survival_mode.py        — survival mode state machine
│   ├── maps_os_env.py          — Atropos RL training environment
│   ├── maps_os_config.py       — config loader, person_context(), person_birth_hint()
│   ├── local_store.py          — SQLite garden failsafe
│   ├── nota_bridge.py          — optional nota integration
│   ├── viz.py                  — Rich visualizations: trend, body/arc dashboard
│   ├── date_resolver.py        — relative date → ISO date
│   └── tui.py                  — Rich TUI
├── tests/
│   ├── test_maps_os_env.py     — RL environment tests
│   ├── test_new_arcs.py        — ARCs 9–25 tests
│   ├── test_arc_cooldown.py    — arc suppression tests
│   ├── test_cli_commands.py    — CLI command integration tests
│   ├── test_phase26_fixes.py   — regression tests (Phase 2.6 bug fixes)
│   ├── test_maps_os_config.py  — config loader + person_context tests
│   └── test_local_store.py     — local SQLite store tests
├── scripts/
│   └── migrate_legacy.py       — life-os → maps-os migrator
└── docs/
    ├── SETUP.md                — install + configuration guide
    ├── AGENT_GUIDE.md          — guide for cassette and other agents
    ├── MAPS_OS_FEATURE_SPEC.md — feature spec + roadmap
    └── WALKTHROUGH.md          — human usage walkthrough
```

---

## Migration from life-os

```bash
python3 scripts/migrate_legacy.py --dry-run   # preview
python3 scripts/migrate_legacy.py             # migrate
```

Converts: `MOOD` (1–10) → `STATE` tag, `ENERGY` → `BODY`, `HABIT` → `INTENTION`. Original values preserved in `legacy_` fields.

---

*maps · cassette.help · MIT*
