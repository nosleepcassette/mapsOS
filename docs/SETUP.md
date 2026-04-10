# mapsOS Setup Guide

## Requirements

- Python 3.10+
- `rich` — TUI rendering
- `pyyaml` — config file loading
- `nota` — optional, task/calendar routing

```bash
pip install -r requirements.txt
```

## Install

```bash
git clone https://github.com/nosleepcassette/mapsOS
cd mapsOS
chmod +x bin/maps
export PATH="$PATH:$(pwd)/bin"
```

Add that export to your `~/.zshrc` or `~/.bashrc` to make it permanent.

Verify:
```bash
maps --help
maps check
```

## Config file

Create `~/.maps_os_config.yaml`. This file is optional — the system degrades gracefully if absent, but PERSON extraction and `maps connect --status` will be blind to names that don't follow explicit interaction keywords.

```yaml
# ~/.maps_os_config.yaml

known_people:
  - alex          # add everyone you'd want connection tracking for
  - alex_nickname # add nicknames as separate entries

graph: <your-graph>   # optional remote backend graph name
```

**This file is private and should not be tracked in git.** Add `~/.maps_os_config.yaml` to your global gitignore.

Without `known_people` populated, PERSON entries will only be extracted when vent text uses explicit interaction keywords immediately before a name ("talked to X", "called X"). Names mentioned mid-sentence will be missed.

## Data locations

| Data | Location |
|------|----------|
| Local entry queue | `~/.maps_os_local.db` (SQLite, always written) |
| Personal config | `~/.maps_os_config.yaml` |
| Arc cooldown state | `~/.maps_os_cooldown.json` |
| RL history | `~/.hermes/logs/.atropos-history.json` |

## Offline / local-only mode

All entries write to `~/.maps_os_local.db` automatically. No data is lost if no remote backend is configured. If you later add a backend:

```bash
maps sync          # flush queue to remote
maps sync --status # see how many entries are waiting
```

## Running tests

```bash
cd mapsOS
python3 -m pytest tests/ -q
```

Expected: 170 passing.

## TUI

```bash
maps          # launches TUI if stdin is a terminal
maps check    # non-interactive session start (agent-safe)
```

Key bindings: `[v]` vent · `[t]` tulpa · `[f]` flash · `[s]` state · `[b]` body · `[m]` mind · `[S]` spirit · `[i]` intention · `[r]` review · `[c]` check · `[y]` sync · `[T]` trend · `[V]` viz · `[?]` help · `[q]` quit

## Verifying visualization

After logging some STATE entries:

```bash
maps trend --days 30      # renders a Unicode bar chart
maps viz                  # state sparkline + body panel + arc frequency
```

If there are no STATE entries yet, both commands will output "no state data" — that's correct, not a bug.

---

*maps · cassette.help · MIT*
