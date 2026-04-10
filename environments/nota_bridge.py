# maps · cassette.help · MIT
"""
nota_bridge.py — Optional integration between maps-os and nota.

This module is intentionally NOT a hard dependency.
If nota is unavailable, all functions degrade gracefully.

Two integration points:
  1. Intention → harsh log: write maps-os INTENTIONS to harsh's log format
     so nota habits and maps-os intentions stay loosely synchronized.
  2. Vent → task extraction: scan vent text for action items and optionally
     route them to nota braindump (action items) vs. maps-os (state signals).

nota is NOT structurally required. This bridge activates only when:
  - nota is installed and on PATH, OR
  - NOTA_PATH env var is set
"""
from __future__ import annotations

import os
import re
import subprocess
from datetime import date
from pathlib import Path
from typing import Optional


def nota_available() -> bool:
    """Check if nota CLI is available."""
    nota_path = os.environ.get("NOTA_PATH", "nota")
    try:
        result = subprocess.run(
            [nota_path, "--help"],
            capture_output=True, timeout=3
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ---------------------------------------------------------------------------
# Intention → harsh sync
# ---------------------------------------------------------------------------

# Maps maps-os intention status to harsh log symbols
# harsh uses: . = done, o = skipped, - = partial
_INTENTION_TO_HARSH = {
    "met": ".",
    "missed": "o",
    "partial": "-",
}


def sync_intention_to_harsh(
    name: str,
    status: str,
    log_date: Optional[str] = None,
    dry_run: bool = False,
) -> bool:
    """
    Write a maps-os intention to harsh's log without using streak UI.

    Args:
        name:     Intention name (must match a harsh habit name)
        status:   met | missed | partial
        log_date: ISO date (default: today)
        dry_run:  Print command without running

    Returns:
        True if written, False if nota/harsh not available or habit not found.
    """
    if not nota_available() and not dry_run:
        return False

    log_date = log_date or date.today().isoformat()
    harsh_symbol = _INTENTION_TO_HARSH.get(status.lower(), "o")

    # harsh log format: `nota did <habit_name>` for done, `nota log <habit_name>` for count
    # For missed/partial we use the harsh log file directly
    harsh_log_path = _find_harsh_log()
    if not harsh_log_path and not dry_run:
        return False

    if dry_run:
        print(f"  [dry] harsh log: {log_date} {name} → {harsh_symbol}")
        return True

    return _write_harsh_log_entry(harsh_log_path, name, log_date, harsh_symbol)


def _find_harsh_log() -> Optional[Path]:
    """Find harsh's log file."""
    candidates = [
        Path.home() / ".config" / "harsh" / "log",
        Path.home() / ".local" / "share" / "harsh" / "log",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _write_harsh_log_entry(
    log_path: Path, habit_name: str, log_date: str, symbol: str
) -> bool:
    """
    Write a single entry to harsh's log.
    harsh log format: date:YYYY-MM-DD,habit_name:symbol
    This is a no-streak write — we append data without touching streak counts.
    """
    try:
        existing = log_path.read_text(encoding="utf-8") if log_path.exists() else ""
        # Check if this habit+date already exists
        if f"{log_date}:{habit_name}" in existing:
            return False  # already logged, don't duplicate
        with log_path.open("a", encoding="utf-8") as f:
            f.write(f"{log_date}:{habit_name}:{symbol}\n")
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Vent → task extraction (dual-parse)
# ---------------------------------------------------------------------------

# Patterns that suggest an action item exists in vent text
_ACTION_PATTERNS = [
    r"\bi (?:need to|should|have to|want to|gotta|must)\s+(\w[^.,!?]{3,40})",
    r"\b(?:call|email|text|message|reply to|buy|pick up|clean|fix|send|schedule|book|cancel|pay)\s+(\w[^.,!?]{2,40})",
    r"\b(?:don't forget|remember to|note to self)\s*[:-]?\s*(\w[^.,!?]{3,40})",
]


def extract_action_items(text: str) -> list[str]:
    """
    Find likely action items in vent text.
    Returns list of short action phrases.
    These are candidates for nota braindump, not maps-os state logs.
    """
    actions = []
    t_lower = text.lower()
    for pattern in _ACTION_PATTERNS:
        for m in re.finditer(pattern, t_lower):
            action = m.group(1).strip().rstrip(".,!?")
            if len(action) > 3:
                actions.append(action)
    # Deduplicate while preserving order
    seen = set()
    deduped = []
    for a in actions:
        if a not in seen:
            seen.add(a)
            deduped.append(a)
    return deduped


def route_vent_to_nota(
    text: str,
    project: str = "inbox",
    dry_run: bool = False,
) -> list[str]:
    """
    Extract action items from vent text and route to nota braindump.

    Returns list of action items that were (or would be) routed.
    Does nothing if nota is not available.
    """
    if not nota_available() and not dry_run:
        return []

    actions = extract_action_items(text)
    if not actions:
        return []

    if dry_run:
        for a in actions:
            print(f"  [dry] nota add '{a}' --project {project} --scope self")
        return actions

    nota_path = os.environ.get("NOTA_PATH", "nota")
    routed = []
    for action in actions:
        try:
            result = subprocess.run(
                [nota_path, "add", action, "--project", project, "--scope", "self"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                routed.append(action)
        except Exception:
            pass
    return routed


# ---------------------------------------------------------------------------
# Survival mode signal to nota
# ---------------------------------------------------------------------------

def set_nota_survival_mode(active: bool, dry_run: bool = False) -> bool:
    """
    Signal survival mode to nota via a tag on pending tasks.
    When active, nota braindump will use 'survival' project.
    This is done by writing to ~/.maps_os_state (read by nota hooks if configured).
    """
    state_file = Path.home() / ".maps_os_state"
    if dry_run:
        print(f"  [dry] write {state_file}: survival_mode={'1' if active else '0'}")
        return True
    try:
        state_file.write_text(f"survival_mode={'1' if active else '0'}\n")
        return True
    except Exception:
        return False


def get_survival_mode_active() -> bool:
    """Read survival mode state from ~/.maps_os_state."""
    state_file = Path.home() / ".maps_os_state"
    try:
        content = state_file.read_text()
        return "survival_mode=1" in content
    except Exception:
        return False
