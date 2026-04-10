# maps-os: Agent Build Guide — Phase 2.8
**Date:** 2026-04-10
**For:** codex / opencode agent
**Repo:** `/Users/maps/dev/hermes-maps-os/`

Read this whole document before starting. Do not start stage N+1 until stage N passes its tests. Run the existing test suite after each stage: `cd /Users/maps/dev/hermes-maps-os && python -m pytest tests/ -q`.

**Current test state: 196 passing, 0 failing.**

## ✅ Phases 2.6 + 2.7 — COMPLETE

All prior work done. 196 tests passing. Key completed items:
- Stage 0: 7 correctness bugs fixed, ARC 15 fixed, CLI schema fixes
- Stage 1: `maps wins`, `maps eval`, `maps goal --update`
- Stage 2: ARC 23 `resistance_pattern`, ARC 24 `negative_interaction_pattern`
- Stage 3: `environments/arc_cooldown.py`, per-arc suppression to `~/.maps_os_cooldown.json`
- Stage 4: ARC 25 `exec_dysfunction` (cross-track)
- Stage 6: `person_context()`, `person_birth_hint()`, `maps person` commands, 16 astrolog skeletons
- TUI: `t` key → tulpa screen (multi-line stream), `T` → trend (key swap)

---

## Codebase orientation

```
environments/
  vent_parser.py      # Entry dataclass, parse_vent(), all _extract_*() functions
  pattern_weaver.py   # Arc functions (ARC 1–25), weave()
  arc_cooldown.py     # Per-arc suppression, persists to ~/.maps_os_cooldown.json
  maps_os_config.py   # config loader for ~/.maps_os_config.yaml
  tui.py              # Rich TUI — dashboard, survival mode, input screens
  local_store.py      # SQLite offline queue
  viz.py              # Rich visualizations: render_trend, render_viz
  date_resolver.py    # Relative date → ISO date conversion
bin/
  maps                # CLI entry point — all top-level commands live here
tests/
  test_new_arcs.py        # Arc tests — follow this pattern for new arc tests
  test_arc_cooldown.py    # Cooldown suppression tests
  test_cli_commands.py    # CLI integration tests
  test_maps_os_config.py  # Config + person context tests
```

**Schema format:** all garden entries use `TRACK: YYYY-MM-DD | field | field | note`.
**Garden writes:** `garden remember '{entry}' --graph cassette` — always short graph ID.
**Arc numbering:** next available is ARC 26.
**File header on new files:** `# maps · cassette.help · MIT`
**Non-TTY safety:** all new commands must work when stdout is not a terminal.

---

## Stage 1 — New STATE tags

### 1a. Add `grounded` and `tender` to the STATE tag set

**Rationale:**
- `grounded` — anchored, present, not drifting. Active quality distinct from `stable` (neutral-flat). The "I actually feel okay and here" state.
- `tender` — emotionally soft, open, post-connection warmth. The state after something meaningful — a good cry, a close conversation, vulnerability-as-positive. Not forward momentum (`thriving`). Still, soft, open.

Both appear in maps's natural language already. Neither has a current tag home.

**File: `environments/vent_parser.py`**

Find `VALID_STATE_TAGS` (set or list). Add:
```python
"grounded",
"tender",
```

Find the STATE keyword extraction (the table or dict that maps phrases to STATE tags). Add entries:
```python
# grounded
"feel grounded": "grounded",
"feeling grounded": "grounded",
"feel present": "grounded",
"feeling present": "grounded",
"feel anchored": "grounded",
"actually okay": "grounded",

# tender
"feel tender": "tender",
"feeling tender": "tender",
"tender": "tender",       # single word match — only if it appears as a sentiment signal
"emotionally open": "tender",
"soft today": "tender",
"feel soft": "tender",
```

**Note:** "tender" as a bare word may over-trigger. Implement as a word-boundary check — only if "tender" appears without a preceding object ("chicken tender", "tender offer" etc.). If the existing extraction logic doesn't support this level of specificity, add `"feel tender"` and `"feeling tender"` only and skip the bare word match.

**File: `environments/tui.py`**

Add to `STATE_COLORS`:
```python
"grounded": "#80cbc4",   # soft teal — present, earthy
"tender":   "#f48fb1",   # dusty rose — soft, warm, open
```

Add to `STATE_SYMBOLS`:
```python
"grounded": "◇",
"tender":   "♡",
```

**File: `environments/maps_os_env.py`**

Find any hard-coded valid STATE tag list and add `"grounded"` and `"tender"`.

**File: `docs/AGENT_GUIDE.md`**

In the STATE schema section, add to the tag disambiguation list:
```
- `grounded` = anchored and present — distinct from `stable` (grounded has active quality, not flat neutral)
- `tender` = emotionally soft and open — distinct from `thriving` (tender is still, not momentum)
```

**Tests:** ≥2 tests in `tests/test_maps_os_env.py` or `tests/test_new_arcs.py`:
- `grounded` and `tender` are accepted as valid STATE tags (no validation error)
- STATE extraction from vent text: "feeling grounded today" → parses to STATE `grounded`
- STATE extraction from vent text: "feel tender after that call" → parses to STATE `tender`

---

## Stage 2 — TUI visual upgrades

All changes in `environments/tui.py`. Run `python3 -m pytest tests/ -q` after this stage — no behavioral changes to parsing or arc logic, so all 196 tests should still pass. Visual changes are not testable via pytest; manual smoke test by running `python3 bin/maps` in a TTY.

### 2a. Responsive centering

**Current:** all content uses a fixed 2-space indent.

**Target:** banner and Rule dividers center to terminal width. Content panels stay left-aligned within a centered container.

Add a helper near the top of the module (after palette constants):

```python
def _term_width() -> int:
    """Terminal width, defaulting to 80 if not detectable."""
    try:
        return os.get_terminal_size().columns
    except (OSError, AttributeError):
        return 80
```

Update `_draw_banner()` to center the ASCII logo lines and tagline relative to `_term_width()`. Use `" " * pad + line` where `pad = max(0, (_term_width() - len(plain_line)) // 2)`. The logo is already in `LOGO_LINES` — iterate and pad each line.

Update `rule()` calls: `Rule` from Rich already fills terminal width, no change needed there. But any manually drawn separator lines should use the terminal width.

Fallback: if terminal width < 80, skip the ASCII logo entirely and just show `"maps-os"` centered.

### 2b. j/k navigation in list screens

Add a simple paginator to screens that can produce more output than fits in a terminal.

**Affected screens:** the output of `maps goal --list` (when called from TUI), wins output in `_screen_review`, person list if called from TUI.

**Implementation:** within any screen that produces a list longer than `_term_width() // 2` lines, offer pagination:

```python
PAGE_SIZE = max(5, (_term_width() // 2) - 4)
```

After rendering the current page:
```
  [dim]j next · k prev · ↩ back[/dim]
```

Read a key. `j` → increment page. `k` → decrement page. Any other key → return from screen.

Keep it simple: if the list fits on one screen, don't show pagination at all.

### 2c. Transient status during operations

**Affected:** sync screen, tulpa parse step, any multi-step operation that currently prints static "loading..." lines.

Replace static `rp(f"  [dim]parsing...[/dim]")` style lines with in-place updates using:

```python
def _status(msg: str) -> None:
    """Overwrite the current line with a status message."""
    if sys.stdout.isatty():
        sys.stdout.write(f"\r\033[2K  {msg}")
        sys.stdout.flush()
    else:
        rp(f"  {msg}")
```

Use this in:
- `_screen_tulpa()`: during parse step
- `_screen_sync()`: while flushing entries, update `_status(f"[dim]flushing {i}/{total}...[/dim]")`
- After operation completes, call `rp("")` to move to next line (clears the transient line)

### 2f. Tulpa line counter

In `_screen_tulpa()`, the current continuation prompt is `·`. Replace it with the current line count:

```python
prompt_sym = ">" if not lines else str(len(lines) + 1)
```

So the prompt sequence reads:
```
  >  first line
  2  second line
  3  /done
```

The `>` marks entry. Numbers mark continuation. `/done` to finish.

---

## Out of scope for Phase 2.8

**Priority 4.7 architecture block** — deferred. Do not implement:
- Shared entry codec / schema parser
- Canonical alias resolution (`brennan` / `b` formal dedup)
- Real date-window filtering (replace `limit=N` with true date cutoffs)
- Arc evidence + persisted arc history
- Safe garden subprocess wrapper (argv-based)
- Config schema v2 with structured birth/location fields
- `maps doctor` — system health check command
- `maps parse --dry-run`

**TUI upgrades 10d and 10e** — marked [SPEC], not [READY]. Do not implement:
- Dashboard two-column layout (10d) — layout math not fully specced
- STATE-colored header Rule (10e) — interaction with survival mode not specced

**nota deduplication** — still explicitly deferred.

---

## Rules for the implementing agent

- Run `python -m pytest tests/ -q` after each stage. All 196 green tests must stay green.
- Do not modify the garden write format for existing entry types.
- All new `_extract_*` functions: return `[]` on no match, never raise.
- All new Arc functions: return `None` or `[]` on insufficient data, never raise.
- Config (`~/.maps_os_config.yaml`) is always optional — missing file = degrades gracefully.
- Cooldown file missing or malformed: degrade gracefully, do not raise.
- No hardcoded names, people, or personal data anywhere in source.
- TUI changes: must remain non-TTY safe. All new `sys.stdout.write()` calls must be gated on `sys.stdout.isatty()`.

---

*maps · cassette.help · MIT*
