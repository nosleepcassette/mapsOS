# maps · cassette.help · MIT
"""
survival_mode.py — State machine for mapsOS survival mode.

Survival Mode activates when STATE = depleted or grieving for 2+ consecutive days.
It contracts the system: only eat/sleep/water tracked, no productivity language.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

SURVIVAL_BRIEFING = """Three things today:
→ eat something real
→ drink water
→ sleep when you can

That's the whole job. Everything else can wait."""

EXIT_MESSAGE = "Logged {state}. Survival mode standing down."

LOW_STATES = {"depleted", "grieving", "surviving"}
SURVIVAL_WINDOW = 5
SURVIVAL_THRESHOLD = 3

# Logs that are allowed during survival mode
SURVIVAL_ALLOWED_TRACKS = frozenset(["STATE", "BODY"])
SURVIVAL_ALLOWED_BODY_CATEGORIES = frozenset(["sleep", "hunger", "energy"])


@dataclass
class SurvivalModeState:
    active: bool = False
    days_in_mode: int = 0
    trigger_state: Optional[str] = None


def _configured_low_states() -> set[str]:
    try:
        from .maps_os_config import load_config, load_survival_config

        return set(load_survival_config(load_config())["low_states"])
    except Exception:
        return set(LOW_STATES)


def evaluate(
    state_entries: list,
    low_states: set | None = None,
    window: int = SURVIVAL_WINDOW,
    threshold: int = SURVIVAL_THRESHOLD,
) -> SurvivalModeState:
    """
    Given recent STATE entries, return the current SurvivalModeState.
    """
    if low_states is None:
        low_states = _configured_low_states()

    recent = state_entries[-window:] if window > 0 else []
    low_count = sum(1 for entry in recent if _extract_tag(entry) in low_states)
    active = low_count >= threshold
    if not active:
        return SurvivalModeState(active=False)

    trigger_tag = _extract_tag(state_entries[-1]) if state_entries else None

    return SurvivalModeState(
        active=True,
        days_in_mode=low_count,
        trigger_state=trigger_tag,
    )


def should_exit(
    current_state_tag: str, was_in_survival: bool, low_states: set | None = None
) -> bool:
    """Returns True if survival mode should exit."""
    if not was_in_survival:
        return False
    active_low_states = low_states if low_states is not None else _configured_low_states()
    return current_state_tag not in active_low_states


def exit_message(state_tag: str) -> str:
    return EXIT_MESSAGE.format(state=state_tag)


def briefing() -> str:
    return SURVIVAL_BRIEFING


def filter_entries_for_survival(entries: list) -> list:
    """
    Filter log entries: in survival mode, only STATE and certain BODY categories pass.
    Entries can be vent_parser.Entry objects or dicts.
    """
    allowed = []
    for entry in entries:
        track = _extract_track(entry)
        if track == "STATE":
            allowed.append(entry)
        elif track == "BODY":
            category = _extract_category(entry)
            if category in SURVIVAL_ALLOWED_BODY_CATEGORIES:
                allowed.append(entry)
    return allowed


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _extract_tag(entry) -> str:
    if isinstance(entry, dict):
        content = entry.get("content", "")
        parts = [p.strip() for p in content.split("|")]
        return parts[1].lower() if len(parts) >= 2 else ""
    if hasattr(entry, "category") and entry.category:
        return entry.category.lower()
    return ""


def _extract_track(entry) -> str:
    if isinstance(entry, dict):
        content = entry.get("content", "")
        return content.split(":")[0].strip().upper() if ":" in content else ""
    if hasattr(entry, "track"):
        return entry.track.upper()
    return ""


def _extract_category(entry) -> str:
    if isinstance(entry, dict):
        content = entry.get("content", "")
        parts = [p.strip() for p in content.split("|")]
        return parts[1].lower() if len(parts) >= 2 else ""
    if hasattr(entry, "category") and entry.category:
        return entry.category.lower()
    return ""
