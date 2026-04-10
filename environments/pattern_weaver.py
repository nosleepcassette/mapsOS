# maps · cassette.help · MIT
"""
pattern_weaver.py — Detects narrative arcs across maps-os log entries.

Input:  lists of recent STATE/BODY/MIND/SPIRIT/INTENTION entries (as dicts or Entry objects)
Output: list of Arc objects (type, message, severity)

Arc severity: "alert" (act now) vs "insight" (worth noting)
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional


SURVIVAL_TRIGGER_TAGS = frozenset(["depleted", "grieving"])
PATTERN_TRIGGER_TAGS = frozenset(["depleted", "grieving", "flooded", "surviving"])
MANIC_TAGS = frozenset(["manic"])
HIGH_STATES = frozenset(["thriving"])


@dataclass
class Arc:
    name: str
    severity: str       # "alert" | "insight" | "survival"
    message: str
    data: dict          # supporting data for the arc

    def __repr__(self) -> str:
        return f"Arc({self.name!r}, {self.severity!r})"


# ---------------------------------------------------------------------------
# Entry normalization
# ---------------------------------------------------------------------------

def _tag(entry: Any) -> str:
    """Extract the relevant tag/category/status from a raw dict or Entry."""
    if isinstance(entry, dict):
        # Garden recall entries look like: {"content": "STATE: 2026-04-09 | depleted | ..."}
        content = entry.get("content", "")
        if "|" in content:
            parts = [p.strip() for p in content.split("|")]
            if len(parts) >= 2:
                return parts[1].lower()
    # vent_parser Entry objects
    if hasattr(entry, "category") and entry.category:
        return entry.category.lower()
    return ""


def _status(entry: Any) -> str:
    if isinstance(entry, dict):
        content = entry.get("content", "")
        parts = [p.strip() for p in content.split("|")]
        if len(parts) >= 3:
            return parts[2].lower()
    if hasattr(entry, "status") and entry.status:
        return entry.status.lower()
    return ""


def _note(entry: Any) -> str:
    if isinstance(entry, dict):
        content = entry.get("content", "")
        parts = [p.strip() for p in content.split("|")]
        if len(parts) >= 4:
            return parts[3]
        if len(parts) == 3:
            return parts[2]
    if hasattr(entry, "note") and entry.note:
        return entry.note
    return ""


# ---------------------------------------------------------------------------
# Arc detectors (each returns Optional[Arc])
# ---------------------------------------------------------------------------

def _arc_manic_spike(
    state_entries: list, body_entries: list, mind_entries: list
) -> Optional[Arc]:
    """ARC 1 — Manic Spike + Sleep Debt"""
    recent_states = [_tag(e) for e in state_entries[-3:]]
    sleep_entries = [e for e in body_entries if _tag(e) == "sleep"]
    recent_sleep = [_status(e) for e in sleep_entries[-3:]]
    mind_flows = [e for e in mind_entries if _tag(e) == "flow"]
    high_flow = any(_status(e) in ("high", "hyper") for e in mind_flows[-3:])

    manic_present = any(t in MANIC_TAGS for t in recent_states)
    depleted_present = any(t == "depleted" for t in recent_states)
    bad_sleep = any(s in ("none", "poor", "broken") for s in recent_sleep)

    if (manic_present or depleted_present) and bad_sleep and high_flow:
        return Arc(
            name="manic_spike",
            severity="alert",
            message="You're in a coding spike with no sleep. The crash is coming. What time do you want to stop?",
            data={"states": recent_states, "sleep": recent_sleep},
        )
    return None


def _arc_isolation_creep(spirit_entries: list) -> Optional[Arc]:
    """ARC 2 — Isolation Creep"""
    isolation_days = sum(
        1 for e in spirit_entries if _tag(e) == "isolation" and _status(e) in ("high", "present", "rising")
    )
    connection_days = sum(1 for e in spirit_entries if _tag(e) == "connection")

    # Check last N entries for absence of connection
    recent_n = min(len(spirit_entries), 10)
    recent_spirit = spirit_entries[-recent_n:]
    days_no_connection = sum(1 for e in recent_spirit if _tag(e) != "connection")

    if isolation_days >= 3 or days_no_connection >= 5:
        n = isolation_days if isolation_days >= 3 else days_no_connection
        return Arc(
            name="isolation_creep",
            severity="alert",
            message=f"Haven't logged connection in {n} days. Who do you want to reach out to?",
            data={"isolation_days": isolation_days, "no_connection_days": days_no_connection},
        )
    return None


def _arc_body_neglect(body_entries: list, mind_entries: list) -> Optional[Arc]:
    """ARC 3 — Body Neglect + High Output"""
    hunger_entries = [e for e in body_entries if _tag(e) == "hunger"]
    movement_entries = [e for e in body_entries if _tag(e) == "movement"]
    flow_entries = [e for e in mind_entries if _tag(e) == "flow"]

    hungry = any(_status(e) in ("starving", "ignored") for e in hunger_entries[-3:])
    no_movement = any(_status(e) in ("none", "minimal") for e in movement_entries[-3:])
    high_flow = any(_status(e) in ("high", "hyper") for e in flow_entries[-3:])

    if high_flow and (hungry or no_movement):
        what = "food" if hungry else "a walk"
        return Arc(
            name="body_neglect",
            severity="alert",
            message=f"You've been in flow but your body is invisible right now. One thing: {what}.",
            data={"hungry": hungry, "no_movement": no_movement},
        )
    return None


def _arc_state_dip_holding(state_entries: list) -> Optional[Arc]:
    """ARC 4 — STATE Dip Holding (triggers survival mode check)"""
    if len(state_entries) < 2:
        return None
    recent = [_tag(e) for e in state_entries[-3:]]
    low_count = sum(1 for t in recent if t in PATTERN_TRIGGER_TAGS)
    if low_count >= 2:
        return Arc(
            name="state_dip_holding",
            severity="survival",
            message="",  # handled by SurvivalMode, not displayed directly
            data={"recent_states": recent, "low_count": low_count},
        )
    return None


def _arc_spirit_rising(state_entries: list, spirit_entries: list) -> Optional[Arc]:
    """ARC 5 — SPIRIT Rising + STATE Lagging"""
    recent_state = _tag(state_entries[-1]) if state_entries else "stable"
    rising_connection = any(
        _tag(e) == "connection" and _status(e) in ("rising", "present", "high")
        for e in spirit_entries[-5:]
    )
    state_low = recent_state in ("depleted", "stable", "surviving")

    if rising_connection and state_low:
        return Arc(
            name="spirit_rising",
            severity="insight",
            message=f"Connection is coming online even though you're {recent_state}. That's a good sign. Let it.",
            data={"state": recent_state},
        )
    return None


def _arc_intention_miss_pattern(intention_entries: list) -> list[Arc]:
    """ARC 6 — Intentions Missed Pattern (returns one Arc per missed intention)"""
    # Group by intention name
    from collections import defaultdict
    by_name: dict[str, list[str]] = defaultdict(list)
    for e in intention_entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if hasattr(e, "category"):
            name = e.category or ""
            status = e.status or ""
        else:
            parts = [p.strip() for p in content.split("|")]
            name = parts[0].replace("INTENTION:", "").strip() if parts else ""
            status = parts[1] if len(parts) > 1 else ""
        if name:
            by_name[name].append(status.lower())

    arcs = []
    for name, statuses in by_name.items():
        consecutive_misses = 0
        for s in reversed(statuses):
            if s == "missed":
                consecutive_misses += 1
            else:
                break
        if consecutive_misses >= 4:
            arcs.append(Arc(
                name="intention_miss_pattern",
                severity="insight",
                message=f"{name.title()} has been hard to hit. Want to adjust it, or just note it as context?",
                data={"intention": name, "consecutive_misses": consecutive_misses},
            ))
    return arcs


def _arc_post_manic_drop(state_entries: list) -> Optional[Arc]:
    """ARC 7 — Post-Manic Drop"""
    if len(state_entries) < 2:
        return None
    prev_states = [_tag(e) for e in state_entries[-4:-1]]
    current = _tag(state_entries[-1])
    was_manic = any(t in MANIC_TAGS for t in prev_states)
    now_low = current in ("depleted", "grieving", "stable")

    if was_manic and now_low:
        return Arc(
            name="post_manic_drop",
            severity="insight",
            message="Post-spike drop. This is predictable, not a failure. Rest is the only protocol.",
            data={"previous": prev_states, "current": current},
        )
    return None


def _arc_thriving_streak(state_entries: list) -> Optional[Arc]:
    """ARC 8 — Thriving Streak"""
    if len(state_entries) < 3:
        return None
    recent = [_tag(e) for e in state_entries[-3:]]
    if all(t == "thriving" for t in recent):
        return Arc(
            name="thriving_streak",
            severity="insight",
            message="Three days of thriving. What's different? Worth noting what's holding this.",
            data={"streak": len(recent)},
        )
    return None


# ---------------------------------------------------------------------------
# New arc detectors (Arcs 9, 12, 13, 15 — approved 2026-04-09)
# ---------------------------------------------------------------------------

def _arc_productivity_spiral(
    state_entries: list, mind_entries: list, spirit_entries: list
) -> Optional[Arc]:
    """ARC 9 — Productivity-as-Survival Spiral"""
    recent_states = [_tag(e) for e in state_entries[-3:]]
    at_risk = any(t in ("manic", "depleted") for t in recent_states)
    if not at_risk:
        return None

    # Work/output language in recent state notes
    _WORK_KW = [
        "working", "building", "coding", "shipping", "output", "project",
        "deploy", "launched", "shipped", "pushed", "wrote", "produced",
    ]
    recent_notes = [_note(e).lower() for e in state_entries[-5:]]
    has_work_language = any(any(kw in note for kw in _WORK_KW) for note in recent_notes)
    if not has_work_language:
        # Also check mind flow/hyper as a proxy for output mode
        mind_focus = [e for e in mind_entries if _tag(e) in ("flow", "focus")]
        has_work_language = any(_status(e) in ("high", "hyper") for e in mind_focus[-3:])

    if not has_work_language:
        return None

    # Spirit missing purpose or connection for 5+ recent entries
    spirit_tags = [_tag(e) for e in spirit_entries[-7:]]
    missing_spirit = not any(t in ("purpose", "connection") for t in spirit_tags)

    if missing_spirit:
        return Arc(
            name="productivity_spiral",
            severity="insight",
            message=(
                "You're building hard right now. Is it because things are clicking, "
                "or because stopping feels dangerous?"
            ),
            data={"states": recent_states, "missing_purpose_or_connection": True},
        )
    return None


def _arc_catastrophizing_spike(state_entries: list) -> Optional[Arc]:
    """ARC 12 — Catastrophizing Spike"""
    _CATASTROPHIZING = [
        "everything is fucked", "it's all ruined", "its all ruined",
        "complete failure", "nothing works", "it's over", "its over",
        "everything is broken", "ruined everything", "totally hopeless",
        "total disaster", "can't fix this", "cant fix this",
        "everything is falling apart", "nothing will ever",
        "always fails", "never works", "it's all wrong",
    ]
    recent_notes = [_note(e).lower() for e in state_entries[-3:]]
    for note in recent_notes:
        if any(phrase in note for phrase in _CATASTROPHIZING):
            return Arc(
                name="catastrophizing_spike",
                severity="insight",
                message=(
                    "That's a catastrophizing spike. "
                    "What's the one actual thing that's broken right now?"
                ),
                data={"note_fragment": note[:80]},
            )
    return None


def _arc_intrusive_loop(flash_entries: list) -> Optional[Arc]:
    """ARC 13 — Intrusive Loop (topic recurrence in flash entries)"""
    if len(flash_entries) < 3:
        return None

    _STOP = frozenset([
        "that", "this", "with", "have", "been", "from", "they", "what",
        "when", "just", "some", "like", "into", "than", "then", "them",
        "were", "very", "your", "more", "also", "here", "there",
    ])

    words: list[str] = []
    for e in flash_entries[-10:]:
        content = e.get("content", "") if isinstance(e, dict) else ""
        # FLASH: 2026-04-09 | the text
        parts = content.split("|", 1)
        if len(parts) > 1:
            text = parts[1].strip().lower()
            tokens = re.findall(r'\b[a-z]{4,}\b', text)
            words.extend(t for t in tokens if t not in _STOP)

    if not words:
        return None

    counter = Counter(words)
    most_common = counter.most_common(1)
    if most_common and most_common[0][1] >= 3:
        topic = most_common[0][0]
        count = most_common[0][1]
        return Arc(
            name="intrusive_loop",
            severity="insight",
            message=(
                f"'{topic}' has come up {count} times in recent flashes. "
                "That's a loop. What's underneath it?"
            ),
            data={"topic": topic, "count": count},
        )
    return None


def _arc_planning_hyperfocus(
    state_entries: list, mind_entries: list, intention_entries: list
) -> Optional[Arc]:
    """ARC 15 — Planning Hyperfocus (ADHD planning trap)"""
    recent_states = [_tag(e) for e in state_entries[-3:]]
    # Don't fire in crisis — survival takes priority
    in_crisis = any(t in ("depleted", "grieving", "surviving", "flooded") for t in recent_states)
    if in_crisis:
        return None

    _PLANNING_KW = [
        "plan", "planning", "design", "architecture", "structure", "system",
        "organize", "organising", "roadmap", "strategy", "framework", "schema",
        "workflow", "process", "outline", "sketch", "mapping", "spec",
        "todo", "checklist", "to-do",
    ]
    recent_notes = [_note(e).lower() for e in state_entries[-3:]]
    has_planning_language = any(
        any(kw in note for kw in _PLANNING_KW) for note in recent_notes
    )
    if not has_planning_language:
        return None

    # Mind is engaged and non-scattered — suggests active planning session
    # Check category + status: flow/clarity at any status, focus only if high or hyper
    high_mind = any(
        _tag(e) in ("flow", "clarity")
        or (_tag(e) == "focus" and _status(e) in ("high", "hyper"))
        for e in mind_entries[-3:]
    )
    if not high_mind:
        return None

    # No intentions logged today — planning without doing
    today = date.today().isoformat()
    today_intentions = [
        e for e in intention_entries
        if today in (e.get("content", "") if isinstance(e, dict) else "")
    ]
    if today_intentions:
        return None

    return Arc(
        name="planning_hyperfocus",
        severity="insight",
        message=(
            "You're planning to plan. What's the smallest first step on THE Thing? "
            "Not the whole plan — just the first move."
        ),
        data={"planning_detected": True, "today_intentions": 0},
    )


# ---------------------------------------------------------------------------
# New arcs: 17 (substance_coping), 18 (avoidance_language), 19 (habit_candidate)
# ---------------------------------------------------------------------------

_AVOIDANCE_PHRASES = [
    "i'll just", "do it later", "deal with it later", "not right now",
    "can't face", "don't want to deal", "pushing it off", "ignoring it",
    "maybe tomorrow", "i keep putting off", "been avoiding",
]


def _arc_substance_coping(state_entries: list, body_entries: list) -> Optional[Arc]:
    """ARC 17 — Substance use during heavy emotional state (no-judgment log flag)."""
    if not state_entries or not body_entries:
        return None
    recent_state = _tag(state_entries[-1]) if state_entries else ""
    if recent_state not in ("flooded", "grieving", "depleted"):
        return None
    substance_recent = any(_tag(e) == "substances" for e in body_entries[-5:])
    if not substance_recent:
        return None
    return Arc(
        name="substance_coping",
        severity="insight",
        message=(
            "Logged substances during a heavy state. "
            "Not a judgment — just visible. Pattern builds over time."
        ),
        data={"state": recent_state, "substance_logged": True},
    )


def _arc_avoidance_language(state_entries: list) -> Optional[Arc]:
    """ARC 18 — Avoidance language in vent notes (earlier detection than arc 10)."""
    # Scan state entry notes (which contain vent narrative snippets)
    if not state_entries:
        return None
    recent_notes = [_note(e).lower() for e in state_entries[-5:]]
    combined = " ".join(recent_notes)
    hits = [p for p in _AVOIDANCE_PHRASES if p in combined]
    if len(hits) >= 2:
        return Arc(
            name="avoidance_language",
            severity="insight",
            message=(
                f"Avoidance language in recent vents ({len(hits)} signals). "
                "What's the one thing you're actually circling?"
            ),
            data={"hits": hits[:3]},
        )
    return None


def _arc_habit_candidate(intention_entries: list) -> list[Arc]:
    """ARC 19 — Frequently-logged intention → suggest converting to harsh habit."""
    if not intention_entries:
        return []
    # Count per intention name
    counts: Counter = Counter()
    met_counts: Counter = Counter()
    for e in intention_entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if content.startswith("INTENTION:"):
            parts = [p.strip() for p in content.split("|")]
            if len(parts) >= 2:
                name = parts[0].replace("INTENTION:", "").strip()
                status = parts[1].strip() if len(parts) > 1 else ""
                counts[name] += 1
                if status == "met":
                    met_counts[name] += 1
    arcs = []
    for name, total in counts.items():
        if total >= 5 and name:
            met = met_counts.get(name, 0)
            rate = met / total
            if rate >= 0.6:
                arcs.append(Arc(
                    name="habit_candidate",
                    severity="insight",
                    message=(
                        f"'{name}' logged {total} times, met {met}/{total}. "
                        f"Worth adding to harsh as a habit?"
                    ),
                    data={"intention": name, "total": total, "met": met},
                ))
    return arcs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def weave(
    state_entries: list,
    body_entries: list,
    mind_entries: list,
    spirit_entries: list,
    intention_entries: list,
    flash_entries: list = None,
) -> list[Arc]:
    """
    Run all arc detectors in priority order.
    First alert-level arc wins (no alert stacking).
    All insights are returned.
    """
    if flash_entries is None:
        flash_entries = []

    arcs: list[Arc] = []

    # Alerts — first match wins
    alert_detectors = [
        lambda: _arc_manic_spike(state_entries, body_entries, mind_entries),
        lambda: _arc_body_neglect(body_entries, mind_entries),
        lambda: _arc_isolation_creep(spirit_entries),
        lambda: _arc_state_dip_holding(state_entries),
    ]
    for detector in alert_detectors:
        arc = detector()
        if arc is not None:
            arcs.append(arc)
            break  # one alert at a time

    # Insights — all that apply (arcs 5-9, 12, 15, 17, 18)
    insight_detectors = [
        lambda: _arc_spirit_rising(state_entries, spirit_entries),
        lambda: _arc_post_manic_drop(state_entries),
        lambda: _arc_thriving_streak(state_entries),
        lambda: _arc_productivity_spiral(state_entries, mind_entries, spirit_entries),
        lambda: _arc_catastrophizing_spike(state_entries),
        lambda: _arc_planning_hyperfocus(state_entries, mind_entries, intention_entries),
        lambda: _arc_substance_coping(state_entries, body_entries),
        lambda: _arc_avoidance_language(state_entries),
    ]
    for detector in insight_detectors:
        arc = detector()
        if arc is not None:
            arcs.append(arc)

    # Intentions — can have multiple
    arcs.extend(_arc_intention_miss_pattern(intention_entries))

    # Habit candidates (ARC 19) — multiple possible
    arcs.extend(_arc_habit_candidate(intention_entries))

    # Intrusive loop — requires flash entries
    if flash_entries:
        arc = _arc_intrusive_loop(flash_entries)
        if arc is not None:
            arcs.append(arc)

    return arcs


def check_survival_trigger(state_entries: list) -> bool:
    """
    Returns True if survival mode should be active.
    Trigger: STATE in (depleted, grieving) for 2+ of the last 3 entries.
    """
    if not state_entries:
        return False
    recent = [_tag(e) for e in state_entries[-3:]]
    return sum(1 for t in recent if t in SURVIVAL_TRIGGER_TAGS) >= 2
