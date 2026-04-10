# maps-os

A qualitative life operating system for neurodivergent, hyperlexical brains.

Not a habit tracker. Not a mood journal. Not a productivity app.

maps-os tracks **narrative states**, detects **arc patterns** across days and weeks, and knows when to simplify everything down to three survival basics. It runs as a standalone CLI and TUI, logs to a garden knowledge graph (with local SQLite fallback), and feeds an Atropos RL training environment.

Built for maps. Forked from [hermes-life-os](https://github.com/nosleepcassette/hermes-life-os).

---

## What It Tracks

### STATE
The primary axis. One tag per log entry — the dominant emotional/psychological reality.

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
Three separate tracks that can diverge wildly from each other.

- **BODY** — sleep, pain, hunger, movement, substances, energy
- **MIND** — focus, clarity, overwhelm, flow
- **SPIRIT** — connection, creativity, purpose, isolation

### INTENTIONS
Not habits. Not streaks. Just honest tracking of what was tried.
`met` / `missed` / `partial` — no judgment in the schema.

---

## CLI Reference

```bash
# core tracking
maps vent "i'm exhausted and can't stop coding"   # full parser → auto-log
maps flash "emma"                                  # sub-threshold capture, no structure
maps state thriving "post-tender clarity"          # direct state log
maps body sleep none "up since 5am"               # direct body log
maps mind flow high "6hr build session"           # direct mind log
maps spirit connection rising "good call with emma"
maps intention water missed "forgot again"
maps intention movement met "dog park 45min"

# session + pattern
maps check                    # session start: context pull + pattern check
maps pattern                  # full pattern weaver output
maps review                   # cycle review (last 14 days)
maps survival                 # check / display survival mode

# extended capture
maps tulpa                    # multi-line stream capture (tulpa protocol)
                              # end with /done or Ctrl+D

# system
maps sync                     # flush local store to garden when it's back
maps sync --status            # show how many entries are waiting
maps eval                     # show cassette's maps-os performance trend
```

Running `maps` with no arguments in a TTY launches the TUI.

---

## TUI

```
python3 bin/maps
```

Requires `rich`. No Textual dependency — uses raw termios + Rich, same approach as [augury](https://github.com/nosleepcassette/augury) and [tsundoku](https://github.com/nosleepcassette/tsundoku).

**Warm amber palette.** STATE-specific colors. Dashboard, survival, vent, flash, state, body, mind, spirit, intention, review, help, and sync screens.

Key bindings:

| Key | Action |
|-----|--------|
| `v` | vent |
| `f` | flash |
| `s` | state |
| `b` | body |
| `m` | mind |
| `S` | spirit |
| `i` | intention |
| `r` | review |
| `c` | refresh / pattern check |
| `y` | sync local store to garden |
| `?` / `h` | help |
| `q` | quit |

---

## Pattern Weaving

After every vent and at session start, the pattern weaver runs across recent entries and surfaces arcs.

**Alert arcs** (one at a time, highest priority):

| Arc | Trigger | Message style |
|-----|---------|---------------|
| `manic_spike` | Manic/depleted + no sleep + high flow | "The crash is coming. What time do you want to stop?" |
| `body_neglect` | High flow + hunger ignored or no movement | "Your body is invisible right now. One thing: food or a walk." |
| `isolation_creep` | 3+ isolation logs or 5+ days no connection | "Who do you want to reach out to?" |
| `state_dip_holding` | 2+ low states in last 3 | Triggers survival mode |

**Insight arcs** (all that apply):

| Arc | Trigger |
|-----|---------|
| `spirit_rising` | Connection rising while state is low |
| `post_manic_drop` | Was manic, now depleted/stable |
| `thriving_streak` | 3 consecutive thriving |
| `productivity_spiral` | Manic/depleted + work language + no spirit tracked |
| `catastrophizing_spike` | Catastrophizing phrases in vent notes |
| `planning_hyperfocus` | Planning language + high mind + no intentions logged today |
| `intrusive_loop` | Same topic in 3+ flash entries |

**Behavioral-only arcs** (response calibration, not code):

- `avoidance_loop` — same task mentioned 3+ times without resolution
- `trust_rupture` — lied/betrayed/used in vent → suppress everything, just witness
- `context_inheritance` — session start state comparison
- `state_memory_loss` — nudge 48+ hours after a logged state with no follow-up

---

## Survival Mode

Triggers when STATE has been `depleted` or `grieving` for 2+ of the last 3 entries.

In survival mode:
- Logging collapses to STATE + BODY only
- All pattern alerts suppressed except body neglect
- Briefing is exactly three items: eat, sleep, water
- No productivity language anywhere

Exits softly when a non-low state is logged.

---

## Garden Failsafe

If garden (the knowledge graph) is unavailable, entries write to a local SQLite store at `~/.maps_os_local.db`. When garden comes back, `maps sync` flushes the queue.

The system never loses data. Garden downtime is transparent.

---

## Installation

```bash
git clone https://github.com/nosleepcassette/hermes-maps-os
cd hermes-maps-os
pip install rich   # only external dependency for TUI
chmod +x bin/maps
```

Optional: add `bin/` to PATH so `maps` works from anywhere.

```bash
export PATH="$PATH:/path/to/hermes-maps-os/bin"
```

**Dependencies:**
- Python 3.10+
- `rich` (TUI only — CLI works without it)
- `garden` (knowledge graph — optional, local store is the fallback)
- `nota` (task routing — optional, detected automatically)
- `eidetic` (verbatim logging — optional, detected automatically)

---

## RL Training

The `environments/maps_os_env.py` file is an Atropos-compatible RL training environment. 13 scenarios across vent, session start, survival, cycle review, and intention log modes.

Reward weights:

| Component | Weight | What it measures |
|-----------|--------|-----------------|
| `state_logged` | 0.25 | Did maps log STATE? |
| `correct_state` | 0.20 | Was the tag valid and contextually appropriate? |
| `track_coverage` | 0.20 | Were BODY/MIND/SPIRIT covered? |
| `tool_coverage` | 0.15 | Did cassette use expected tools? |
| `no_streak_language` | 0.10 | Did cassette avoid pressure vocabulary? |
| `survival_correct` | 0.10 | Was survival mode handled correctly? |

Passive evaluation: `~/.hermes/hooks/post_session_life_os.py` fires after sessions and logs to `~/.hermes/logs/.atropos-history.json`. View trends with `maps eval`.

---

## Tests

```bash
python3 -m pytest tests/ -v
```

150 tests covering: vent parser, pattern weaver (all 11 code arcs), survival mode, local store, RL environment, new arcs (9/12/13/15).

---

## Project Structure

```
hermes-maps-os/
├── bin/
│   └── maps                    — standalone CLI (human + agent facing)
├── environments/
│   ├── vent_parser.py          — free-form text → STATE/BODY/MIND/SPIRIT entries
│   ├── pattern_weaver.py       — arc detection (11 code arcs)
│   ├── survival_mode.py        — survival mode state machine
│   ├── maps_os_env.py          — Atropos RL training environment
│   ├── maps_os_config.yaml     — RL training config
│   ├── local_store.py          — SQLite garden failsafe
│   ├── nota_bridge.py          — optional nota integration
│   └── tui.py                  — Rich TUI
├── scripts/
│   └── migrate_legacy.py       — life-os → maps-os migrator
├── tests/
│   ├── test_maps_os_env.py     — 73 RL environment tests
│   ├── test_local_store.py     — 17 local store tests
│   └── test_new_arcs.py        — 30 new arc tests
└── docs/
    ├── WALKTHROUGH.md          — human usage guide
    ├── AGENT_GUIDE.md          — guide for cassette and other agents
    └── WRITEUP.md              — technical design document
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
