# mapsOS Handover — Phase 5 / 5.5
# maps · cassette.help · MIT
# updated: 2026-04-17
# primary owner: OpenCode

---

## Current State

Phase 5 is no longer mostly TODO.

Implemented:

- splash screen and loading polish
- survival threshold overhaul and opt-out behavior
- in-app docs / help surfaces
- embedded role guidance
- about screen
- viz formatting fixes
- `maps export`
- automatic structured export on TUI exit
- `maps check --load-brief <file>`
- atlas carry-over task hints in `maps check`

The cartographer bridge is now usable end to end.

---

## Closed Loop

```text
cart daily-brief -> maps check --load-brief -> maps session -> maps export / TUI exit -> cart mapsos ingest-exports --latest
```

Use that as the real smoke test path.

---

## Commands

```bash
maps check --load-brief ~/atlas/daily/brief-$(date +%F).md
maps export
python3 -m pytest tests/ -q
```

Bridge verification from the cartographer side:

```bash
cart mapsos ingest-exports --latest
cart mapsos patterns --field state
```

---

## Files That Matter

- `bin/maps`
- `environments/export.py`
- `tests/test_cli_commands.py`
- `tests/test_export.py`
- `README.md`

---

## Remaining OpenCode Work

These are the remaining mapsOS-forward pieces after the shipped bridge:

1. richer brief UX inside the TUI
   - current brief handling is CLI/session-start text, not a dedicated panel

2. deeper atlas arc sync
   - current bridge surfaces carry-over task hints
   - a fuller task / arc reconciliation layer is still open

3. knowledge-map screen
   - consume future `cart graph --export` output once cartographer exposes it

4. export schema hardening
   - add explicit schema versioning if the payload starts changing quickly

---

## Notes

- `maps export` should stay fast even when the garden backend is unavailable.
- Atlas is the downstream synthesis substrate; mapsOS should not try to duplicate atlas’s summarization role.
- Keep the export surface simple and structured so `cart mapsos ingest-exports` stays deterministic.
