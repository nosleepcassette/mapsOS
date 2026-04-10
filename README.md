# mapsOS

![mapsOS](mapsOS.png)

`mapsOS` is a qualitative life-tracking CLI/TUI built around narrative state instead of scores, streaks, or rigid check-in schedules.

It is designed to capture what is actually happening, structure it just enough to be useful, and surface recurring arcs across recent sessions.

## What mapsOS tracks

- `STATE`: the dominant emotional or psychological reality for a session
- `BODY`, `MIND`, `SPIRIT`: three tracks that can diverge sharply
- `INTENTION`: honest tracking without shame loops
- `WIN`, `PERSON`, `DECISION`, `RESISTANCE`, `TRIGGER`, `GOAL`, `EVENT`, `DEADLINE`, `FLASH`: longer-arc and context signals extracted from free-form text or logged directly

## Core commands

```bash
# free-form capture
maps vent "i'm exhausted but i can't stop coding"
maps tulpa
maps flash "laundry"

# direct logging
maps state thriving "post-storm clarity"
maps body sleep none "up since 5am"
maps mind flow high "six hour build session"
maps spirit connection rising "good call"
maps intention water missed "forgot again"

# review + patterning
maps check
maps pattern
maps review
maps survival
maps trend --days 7
maps viz

# people, goals, wins, events
maps connect alex "good catch-up"
maps person --list
maps goal "sort housing" --due 2026-05-24
maps goal --list
maps wins --week
maps events --week

# evaluation
maps eval --days 7
```

Running `maps` with no arguments in a TTY launches the Rich-based TUI.

## Pattern system

mapsOS includes a pattern weaver that runs after vents and at session start. It looks for multi-day arcs such as:

- `manic_spike`
- `body_neglect`
- `isolation_creep`
- `post_manic_drop`
- `resistance_pattern`
- `negative_interaction_pattern`
- `exec_dysfunction`
- `intrusive_loop`

Survival mode contracts the system when recent state has stayed low: logging narrows, prompts get shorter, and productivity language drops out.

## Installation

```bash
git clone https://github.com/nosleepcassette/mapsOS
cd mapsOS
pip install -r requirements.txt
chmod +x bin/maps
export PATH="$PATH:$(pwd)/bin"
```

Local entries are stored in `~/.maps_os_local.db`.

**Requirements:**
- Python 3.10+
- `rich` for the TUI
- `pyyaml` for config loading

**Agent integration:** [`SKILL.md`](https://gist.github.com/nosleepcassette/6644b13147a064c234a20b2642a4809e) — Hermes operator guide covering session protocol, vent parsing, arc response calibration, and tulpa capture mode.

## Tests

```bash
python3 -m pytest tests/ -v
```

The public branch keeps the runnable code, the test suite, and the operator skill source while dropping legacy demo and internal planning material.

## Project structure

```text
mapsOS/
├── bin/
│   └── maps
├── docs/
│   └── SKILL.md
├── environments/
│   ├── arc_cooldown.py
│   ├── date_resolver.py
│   ├── local_store.py
│   ├── maps_os_config.py
│   ├── maps_os_config.yaml
│   ├── maps_os_env.py
│   ├── nota_bridge.py
│   ├── pattern_weaver.py
│   ├── survival_mode.py
│   ├── tui.py
│   ├── vent_parser.py
│   └── viz.py
└── tests/
    ├── test_arc_cooldown.py
    ├── test_cli_commands.py
    ├── test_local_store.py
    ├── test_maps_os_config.py
    ├── test_maps_os_env.py
    ├── test_new_arcs.py
    └── test_phase26_fixes.py
```

*maps · cassette.help · MIT*
