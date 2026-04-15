# maps · cassette.help · MIT
"""
arc_cooldown.py — Per-arc suppression tracking.

Cooldown state is persisted to ~/.maps_os_cooldown.json.
An arc that fires is suppressed for its cooldown window (in days).
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


ARC_COOLDOWNS: dict[str, int] = {
    "manic_spike": 1,
    "body_neglect": 1,
    "isolation_creep": 2,
    "state_dip_holding": 0,
    "spirit_rising": 3,
    "post_manic_drop": 2,
    "thriving_streak": 3,
    "productivity_spiral": 2,
    "catastrophizing_spike": 1,
    "planning_hyperfocus": 1,
    "substance_coping": 3,
    "avoidance_language": 2,
    "decision_pile": 3,
    "trigger_pattern": 7,
    "goal_stall": 7,
    "resistance_pattern": 5,
    "negative_interaction_pattern": 7,
    "cycle_meta": 7,
}


def cooldown_path() -> Path:
    """Returns ~/.maps_os_cooldown.json"""
    return Path.home() / ".maps_os_cooldown.json"


def load_cooldowns() -> dict:
    """Load {arc_name: last_fired_iso_date}. Returns {} on missing file."""
    path = cooldown_path()
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_cooldowns(cooldowns: dict) -> None:
    """Persist cooldown state. Never raises."""
    path = cooldown_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(cooldowns, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        return None


def is_suppressed(arc_name: str, cooldowns: dict, cooldown_days: int) -> bool:
    """Returns True if arc fired within cooldown_days."""
    if cooldown_days <= 0:
        return False

    last_fired = cooldowns.get(arc_name)
    if not last_fired:
        return False

    try:
        fired_on = date.fromisoformat(last_fired)
    except Exception:
        return False

    return (date.today() - fired_on).days < cooldown_days


def record_fired(arc_name: str, cooldowns: dict) -> dict:
    """Returns updated cooldowns dict with arc_name set to today."""
    updated = dict(cooldowns or {})
    updated[arc_name] = date.today().isoformat()
    return updated


# ---------------------------------------------------------------------------
# Arc fire history — tracks all fire dates per arc for frequency analysis
# ---------------------------------------------------------------------------

_HISTORY_PATH = Path.home() / ".maps_os_arc_history.json"
_HISTORY_PRUNE_DAYS = 90  # discard entries older than this


def load_history() -> dict[str, list[str]]:
    """Load {arc_name: [iso_date, ...]}. Returns {} on missing file."""
    if not _HISTORY_PATH.exists():
        return {}
    try:
        data = json.loads(_HISTORY_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def save_history(history: dict[str, list[str]]) -> None:
    """Persist history. Never raises."""
    try:
        _HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        _HISTORY_PATH.write_text(
            json.dumps(history, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except Exception:
        return None


def record_history(arc_name: str, history: dict[str, list[str]]) -> dict[str, list[str]]:
    """Append today to arc's fire history, pruning entries older than 90 days."""
    updated = dict(history)
    dates = list(updated.get(arc_name, []))
    today = date.today().isoformat()
    if today not in dates:
        dates.append(today)
    cutoff = (date.today() - timedelta(days=_HISTORY_PRUNE_DAYS)).isoformat()
    dates = [d for d in dates if d >= cutoff]
    updated[arc_name] = dates
    return updated


def get_fire_count(arc_name: str, history: dict[str, list[str]], days: int = 14) -> int:
    """Count how many times arc fired within the last N days."""
    dates = history.get(arc_name, [])
    cutoff = (date.today() - timedelta(days=days)).isoformat()
    return sum(1 for d in dates if d >= cutoff)
