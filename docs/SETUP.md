# maps-os Setup Guide

## Requirements

- Python 3.11+
- `rich` — TUI rendering
- `pyyaml` — config file loading
- `garden` — in PATH (primary persistence layer)
- `nota` — optional, task/calendar routing

```bash
pip install rich pyyaml
```

## Install

```bash
cd ~/dev/hermes-maps-os
pip install -e .            # or just add bin/ to PATH directly

# Symlink the CLI
ln -sf ~/dev/hermes-maps-os/bin/maps ~/.local/bin/maps
```

Verify:
```bash
maps --help
maps check
```

## Config file

Create `~/.maps_os_config.yaml`. This file is optional — the system degrades gracefully if absent, but PERSON extraction and `maps connect --status` will be blind to names that don't follow interaction keywords.

```yaml
# ~/.maps_os_config.yaml
# maps-os personal configuration

known_people:
  - name          # add everyone you'd want connection tracking for
  - nickname      # add nicknames as separate entries

graph: cassette   # default garden graph
```

**This file is private and not tracked in git.** `~/.maps_os_config.yaml` should be in your global gitignore.

Without `known_people` populated, PERSON entries will only be extracted when vent text uses explicit interaction keywords immediately followed by a name ("talked to X", "called X"). Names mentioned mid-sentence will be missed. The config file has been created for this installation.

## Data locations

| Data | Location |
|------|----------|
| Primary entries | `garden --graph cassette` (remote) |
| Offline queue | `~/.maps_os_local.db` (SQLite, auto-synced) |
| Personal config | `~/.maps_os_config.yaml` |
| Arc cooldown state | `~/.maps_os_cooldown.json` (Phase 2.6+) |
| RL history | `~/.hermes/logs/.atropos-history.json` |

## Offline mode

If garden is unavailable, all entries queue to `~/.maps_os_local.db` automatically. No data is lost. When garden returns:

```bash
maps sync          # flush queue to garden
maps sync --status # see how many entries are waiting
```

## Running tests

```bash
cd ~/dev/hermes-maps-os
python -m pytest tests/ -q
```

Expected: 152 passing, 1 pre-existing failure (ARC 15 planning_hyperfocus date edge case).

## TUI

```bash
maps          # launches TUI if stdin is a terminal
maps check    # non-interactive session start (agent-safe)
```

Key bindings in TUI: `[v]` vent · `[f]` flash · `[c]` check · `[s]` survival · `[t]` trend · `[V]` viz · `[q]` quit

## Verifying visualization

After logging some STATE entries, test the visualization stack:

```bash
maps trend --days 30      # should render a Unicode bar chart with Rich
maps viz                  # should show state sparkline + body panel + arc frequency
```

If garden has no STATE entries yet, both commands will output "no state data" — that's correct, not a bug.

---

*maps · cassette.help · MIT*
