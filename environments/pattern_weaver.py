# maps · cassette.help · MIT
"""
pattern_weaver.py — Detects narrative arcs across maps-os log entries.

Input:  lists of recent STATE/BODY/MIND/SPIRIT/INTENTION entries (as dicts or Entry objects)
Output: list of Arc objects (type, message, severity)

Arc severity: "alert" (act now) vs "insight" (worth noting)
"""

from __future__ import annotations

import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from typing import Any, Optional

from environments import arc_cooldown


SURVIVAL_TRIGGER_TAGS = frozenset(["depleted", "grieving"])
PATTERN_TRIGGER_TAGS = frozenset(["depleted", "grieving", "flooded", "surviving"])
MANIC_TAGS = frozenset(["manic"])
HIGH_STATES = frozenset(["thriving"])
_ISO_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


@dataclass
class Arc:
    name: str
    severity: str  # "alert" | "insight" | "survival"
    message: str
    data: dict  # supporting data for the arc

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


def _entry_dates(entry: Any) -> set[str]:
    """Extract any ISO dates embedded in a raw dict or Entry object."""
    if isinstance(entry, dict):
        return set(_ISO_DATE_RE.findall(entry.get("content", "")))
    if hasattr(entry, "date") and entry.date:
        return {entry.date}
    return set()


def _entry_date(entry: Any) -> Optional[date]:
    """Extract the primary ISO date from a raw dict or Entry object."""
    for raw_date in sorted(_entry_dates(entry)):
        try:
            return date.fromisoformat(raw_date)
        except ValueError:
            continue
    return None


def _parse_resistance_entry(entry: Any) -> Optional[dict]:
    """Parse RESISTANCE entries stored as `RESISTANCE: date | phrase | intensity`."""
    content = entry.get("content", "") if isinstance(entry, dict) else ""
    if isinstance(entry, dict):
        if not content.startswith("RESISTANCE:"):
            return None
        parts = [p.strip() for p in content.split("|", 2)]
        if len(parts) < 3:
            return None
        source = parts[1].lower()
        intensity = parts[2].lower()
    elif getattr(entry, "track", None) == "RESISTANCE":
        note_parts = [p.strip() for p in (getattr(entry, "note", "") or "").split("|", 1)]
        if len(note_parts) < 2:
            return None
        source = note_parts[0].lower()
        intensity = note_parts[1].lower()
    else:
        return None

    entry_date = _entry_date(entry)
    if entry_date is None or not source:
        return None

    tokens = set(re.findall(r"\b[a-z]{5,}\b", source))
    return {
        "date": entry_date,
        "source": source,
        "intensity": intensity,
        "tokens": tokens,
    }


def _parse_person_entry(entry: Any) -> Optional[dict]:
    """Parse PERSON entries stored as `PERSON: date | name | context | sentiment`."""
    content = entry.get("content", "") if isinstance(entry, dict) else ""
    if isinstance(entry, dict):
        if not content.startswith("PERSON:"):
            return None
        parts = [p.strip() for p in content.split("|", 3)]
        if len(parts) < 4:
            return None
        name = parts[1].lower()
        context = parts[2]
        sentiment = parts[3].lower()
    elif getattr(entry, "track", None) == "PERSON":
        note_parts = [p.strip() for p in (getattr(entry, "note", "") or "").split("|", 2)]
        if len(note_parts) < 3:
            return None
        name = note_parts[0].lower()
        context = note_parts[1]
        sentiment = note_parts[2].lower()
    else:
        return None

    entry_date = _entry_date(entry)
    if entry_date is None or not name:
        return None

    return {
        "date": entry_date,
        "name": name,
        "context": context,
        "sentiment": sentiment,
    }


def _parse_goal_entry(entry: Any) -> Optional[dict]:
    """Parse GOAL entries stored as `GOAL: date | description | due | status`."""
    content = entry.get("content", "") if isinstance(entry, dict) else ""
    if isinstance(entry, dict):
        if not content.startswith("GOAL:"):
            return None
        parts = [p.strip() for p in content.split("|", 3)]
        if len(parts) < 4:
            return None
        description = parts[1]
        due = parts[2]
        status = parts[3].lower()
    elif getattr(entry, "track", None) == "GOAL":
        note_parts = [p.strip() for p in (getattr(entry, "note", "") or "").split("|", 2)]
        if len(note_parts) < 3:
            return None
        description = note_parts[0]
        due = note_parts[1]
        status = note_parts[2].lower()
    else:
        return None

    entry_date = _entry_date(entry)
    if entry_date is None or not description:
        return None

    return {
        "date": entry_date,
        "description": description,
        "due": due,
        "status": status,
    }


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


def _arc_isolation_creep(
    spirit_entries: list, person_entries: list = None
) -> Optional[Arc]:
    """ARC 2 — Isolation Creep"""
    isolation_days = sum(
        1
        for e in spirit_entries
        if _tag(e) == "isolation" and _status(e) in ("high", "present", "rising")
    )
    connection_days = sum(1 for e in spirit_entries if _tag(e) == "connection")

    recent_n = min(len(spirit_entries), 10)
    recent_spirit = spirit_entries[-recent_n:]
    days_no_connection = sum(1 for e in recent_spirit if _tag(e) != "connection")

    if isolation_days >= 3 or days_no_connection >= 5:
        n = isolation_days if isolation_days >= 3 else days_no_connection

        most_recent_name = ""
        if person_entries:
            for e in person_entries:
                content = e.get("content", "") if isinstance(e, dict) else ""
                if content.startswith("PERSON:"):
                    parts = content.split("|")
                    if len(parts) >= 2:
                        note = parts[1].strip()
                        if "|" in note:
                            name = note.split("|")[0].strip()
                            if name:
                                most_recent_name = name
                                break

        if most_recent_name:
            message = f"Haven't connected with {most_recent_name} in {n} days. Still relevant?"
        else:
            message = f"Haven't logged connection in {n} days. Who do you want to reach out to?"

        return Arc(
            name="isolation_creep",
            severity="alert",
            message=message,
            data={
                "isolation_days": isolation_days,
                "no_connection_days": days_no_connection,
            },
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
            arcs.append(
                Arc(
                    name="intention_miss_pattern",
                    severity="insight",
                    message=f"{name.title()} has been hard to hit. Want to adjust it, or just note it as context?",
                    data={"intention": name, "consecutive_misses": consecutive_misses},
                )
            )
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
        "working",
        "building",
        "coding",
        "shipping",
        "output",
        "project",
        "deploy",
        "launched",
        "shipped",
        "pushed",
        "wrote",
        "produced",
    ]
    recent_notes = [_note(e).lower() for e in state_entries[-5:]]
    has_work_language = any(any(kw in note for kw in _WORK_KW) for note in recent_notes)
    if not has_work_language:
        # Also check mind flow/hyper as a proxy for output mode
        mind_focus = [e for e in mind_entries if _tag(e) in ("flow", "focus")]
        has_work_language = any(
            _status(e) in ("high", "hyper") for e in mind_focus[-3:]
        )

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
        "everything is fucked",
        "it's all ruined",
        "its all ruined",
        "complete failure",
        "nothing works",
        "it's over",
        "its over",
        "everything is broken",
        "ruined everything",
        "totally hopeless",
        "total disaster",
        "can't fix this",
        "cant fix this",
        "everything is falling apart",
        "nothing will ever",
        "always fails",
        "never works",
        "it's all wrong",
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

    _STOP = frozenset(
        [
            "that",
            "this",
            "with",
            "have",
            "been",
            "from",
            "they",
            "what",
            "when",
            "just",
            "some",
            "like",
            "into",
            "than",
            "then",
            "them",
            "were",
            "very",
            "your",
            "more",
            "also",
            "here",
            "there",
        ]
    )

    words: list[str] = []
    for e in flash_entries[-10:]:
        content = e.get("content", "") if isinstance(e, dict) else ""
        # FLASH: 2026-04-09 | the text
        parts = content.split("|", 1)
        if len(parts) > 1:
            text = parts[1].strip().lower()
            tokens = re.findall(r"\b[a-z]{4,}\b", text)
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
    in_crisis = any(
        t in ("depleted", "grieving", "surviving", "flooded") for t in recent_states
    )
    if in_crisis:
        return None

    _PLANNING_KW = [
        "plan",
        "planning",
        "design",
        "architecture",
        "structure",
        "system",
        "organize",
        "organising",
        "roadmap",
        "strategy",
        "framework",
        "schema",
        "workflow",
        "process",
        "outline",
        "sketch",
        "mapping",
        "spec",
        "todo",
        "checklist",
        "to-do",
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

    # No intentions logged on the current session date — planning without doing
    session_dates: set[str] = set()
    for e in state_entries[-3:]:
        session_dates.update(_entry_dates(e))
    if not session_dates:
        session_dates.add(date.today().isoformat())

    today_intentions = [
        e
        for e in intention_entries
        if _entry_dates(e) & session_dates
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
    "i'll just",
    "do it later",
    "deal with it later",
    "not right now",
    "can't face",
    "don't want to deal",
    "pushing it off",
    "ignoring it",
    "maybe tomorrow",
    "i keep putting off",
    "been avoiding",
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
                arcs.append(
                    Arc(
                        name="habit_candidate",
                        severity="insight",
                        message=(
                            f"'{name}' logged {total} times, met {met}/{total}. "
                            f"Worth adding to harsh as a habit?"
                        ),
                        data={"intention": name, "total": total, "met": met},
                    )
                )
    return arcs


def _arc_decision_pile(decision_entries: list) -> Optional[Arc]:
    """ARC 20 — Decision pile (unresolved decisions accumulating)."""
    if len(decision_entries) < 3:
        return None

    from datetime import datetime

    now = datetime.now()
    recent = []
    for e in decision_entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if content.startswith("DECISION:"):
            parts = content.split("|")
            if len(parts) >= 1:
                date_part = parts[0].replace("DECISION:", "").strip()
                try:
                    entry_date = datetime.strptime(date_part, "%Y-%m-%d")
                    if (now - entry_date).days <= 7:
                        recent.append(content)
                except Exception:
                    recent.append(content)

    if len(recent) >= 3:
        oldest = recent[0] if recent else ""
        desc = ""
        if oldest:
            parts = oldest.split("|")
            if len(parts) > 1:
                desc = parts[1].strip()[:50]
        return Arc(
            name="decision_pile",
            severity="insight",
            message=f"you had {len(recent)} unresolved decision points this week. want to revisit any of them?",
            data={"count": len(recent), "oldest": desc},
        )
    return None


def _arc_trigger_pattern(trigger_entries: list) -> Optional[Arc]:
    """ARC 21 — Trigger pattern (same trigger source recurring)."""
    if len(trigger_entries) < 3:
        return None

    sources: Counter = Counter()
    for e in trigger_entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if content.startswith("TRIGGER:"):
            parts = content.split("|")
            if len(parts) > 1:
                note = parts[1].strip()
                if "|" in note:
                    source = note.split("|")[0].strip()[:30]
                    if source:
                        sources[source] += 1

    for source, count in sources.items():
        if count >= 3:
            return Arc(
                name="trigger_pattern",
                severity="insight",
                message=f"you've logged {count} triggers from {source}. that's a pattern worth knowing.",
                data={"source": source, "count": count},
            )
    return None


def _arc_goal_stall(goal_entries: list) -> Optional[Arc]:
    """ARC 22 — Goal stall (goals open for 14+ days)."""
    if not goal_entries:
        return None

    today = date.today()
    stalled = []

    for parsed in (_parse_goal_entry(entry) for entry in goal_entries):
        if parsed is None or parsed["status"] != "open":
            continue
        days_open = (today - parsed["date"]).days
        if days_open >= 14:
            stalled.append((parsed["description"], days_open))

    if stalled:
        stalled.sort(key=lambda x: x[1], reverse=True)
        goal, days = stalled[0]
        return Arc(
            name="goal_stall",
            severity="insight",
            message=f"'{goal}' has been open for {days} days. still relevant?",
            data={"goal": goal, "days": days},
        )
    return None


def _arc_resistance_pattern(resistance_entries: list) -> Optional[Arc]:
    """ARC 23 — Repeated resistance source within a short window."""
    parsed_entries = [
        parsed
        for parsed in (_parse_resistance_entry(entry) for entry in resistance_entries)
        if parsed is not None and parsed["tokens"]
    ]
    if len(parsed_entries) < 3:
        return None

    token_groups: dict[str, list[dict]] = defaultdict(list)
    for entry in parsed_entries:
        for token in entry["tokens"]:
            token_groups[token].append(entry)

    best_window: tuple[int, int, list[dict]] | None = None
    for entries in token_groups.values():
        if len(entries) < 3:
            continue
        entries.sort(key=lambda item: item["date"])
        start = 0
        for end in range(len(entries)):
            while (entries[end]["date"] - entries[start]["date"]).days > 14:
                start += 1
            window = entries[start : end + 1]
            if len(window) < 3:
                continue
            candidate = (len(window), -window[0]["date"].toordinal(), window)
            if best_window is None or candidate > best_window:
                best_window = candidate

    if best_window is None:
        return None

    window = best_window[2]
    source = window[0]["source"]
    span_days = max((window[-1]["date"] - window[0]["date"]).days, 1)
    return Arc(
        name="resistance_pattern",
        severity="insight",
        message=f"you've been resisting {source} for {span_days} days. worth naming why?",
        data={"source": source, "count": len(window), "days": span_days},
    )


def _arc_negative_interaction_pattern(person_entries: list) -> Optional[Arc]:
    """ARC 24 — Same person logged as negative repeatedly within 30 days."""
    negative_entries = [
        parsed
        for parsed in (_parse_person_entry(entry) for entry in person_entries)
        if parsed is not None and parsed["sentiment"] == "negative"
    ]
    if len(negative_entries) < 3:
        return None

    by_name: dict[str, list[dict]] = defaultdict(list)
    for entry in negative_entries:
        by_name[entry["name"]].append(entry)

    best_window: tuple[int, int, str, list[dict]] | None = None
    for name, entries in by_name.items():
        if len(entries) < 3:
            continue
        entries.sort(key=lambda item: item["date"])
        start = 0
        for end in range(len(entries)):
            while (entries[end]["date"] - entries[start]["date"]).days > 30:
                start += 1
            window = entries[start : end + 1]
            if len(window) < 3:
                continue
            candidate = (len(window), -window[0]["date"].toordinal(), name, window)
            if best_window is None or candidate > best_window:
                best_window = candidate

    if best_window is None:
        return None

    name = best_window[2]
    return Arc(
        name="negative_interaction_pattern",
        severity="insight",
        message=f"{name} is consistently showing up as draining. pattern worth noticing.",
        data={"name": name, "count": len(best_window[3])},
    )


def _arc_exec_dysfunction(
    state_entries: list,
    resistance_entries: list,
    goal_entries: list,
) -> Optional[Arc]:
    """ARC 25 — Low state + high resistance + stalled open goal."""
    if not state_entries:
        return None

    current_state = _tag(state_entries[-1])
    if current_state in ("grieving", "surviving"):
        return None
    if current_state not in ("depleted", "flooded", "manic"):
        return None

    today = date.today()
    recent_high_resistance = [
        parsed
        for parsed in (_parse_resistance_entry(entry) for entry in resistance_entries)
        if parsed is not None
        and parsed["intensity"] == "high"
        and 0 <= (today - parsed["date"]).days <= 7
    ]
    if not recent_high_resistance:
        return None

    stalled_goals = [
        parsed
        for parsed in (_parse_goal_entry(entry) for entry in goal_entries)
        if parsed is not None
        and parsed["status"] == "open"
        and (today - parsed["date"]).days >= 14
    ]
    if not stalled_goals:
        return None

    stalled_goals.sort(key=lambda item: item["date"])
    goal = stalled_goals[0]["description"]
    return Arc(
        name="exec_dysfunction",
        severity="insight",
        message=(
            f"resistance is high and {goal} has been stalled. "
            "exec dysfunction pattern. what's the one thing that doesn't require starting?"
        ),
        data={
            "state": current_state,
            "goal": goal,
            "resistance_count": len(recent_high_resistance),
        },
    )


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
    decision_entries: list = None,
    trigger_entries: list = None,
    goal_entries: list = None,
    person_entries: list = None,
    resistance_entries: list = None,
    apply_cooldown: bool = True,
) -> list[Arc]:
    """
    Run all arc detectors in priority order.
    First alert-level arc wins (no alert stacking).
    All insights are returned.
    """
    if flash_entries is None:
        flash_entries = []
    if decision_entries is None:
        decision_entries = []
    if trigger_entries is None:
        trigger_entries = []
    if goal_entries is None:
        goal_entries = []
    if person_entries is None:
        person_entries = []
    if resistance_entries is None:
        resistance_entries = []

    arcs: list[Arc] = []

    # Alerts — first match wins
    alert_detectors = [
        lambda: _arc_manic_spike(state_entries, body_entries, mind_entries),
        lambda: _arc_body_neglect(body_entries, mind_entries),
        lambda: _arc_isolation_creep(spirit_entries, person_entries),
        lambda: _arc_state_dip_holding(state_entries),
    ]
    for detector in alert_detectors:
        arc = detector()
        if arc is not None:
            arcs.append(arc)
            break  # one alert at a time

    # Insights — all that apply (arcs 5-9, 12, 15, 17, 18, 20, 21, 22)
    insight_detectors = [
        lambda: _arc_spirit_rising(state_entries, spirit_entries),
        lambda: _arc_post_manic_drop(state_entries),
        lambda: _arc_thriving_streak(state_entries),
        lambda: _arc_productivity_spiral(state_entries, mind_entries, spirit_entries),
        lambda: _arc_catastrophizing_spike(state_entries),
        lambda: _arc_planning_hyperfocus(
            state_entries, mind_entries, intention_entries
        ),
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

    # ARC 20, 21, 22 — new decision/trigger/goal arcs
    arcs.append(_arc_decision_pile(decision_entries))
    arcs.append(_arc_trigger_pattern(trigger_entries))
    arcs.append(_arc_goal_stall(goal_entries))
    arcs.append(_arc_resistance_pattern(resistance_entries))
    arcs.append(_arc_negative_interaction_pattern(person_entries))
    arcs.append(_arc_exec_dysfunction(state_entries, resistance_entries, goal_entries))

    # Intrusive loop — requires flash entries
    if flash_entries:
        arc = _arc_intrusive_loop(flash_entries)
        if arc is not None:
            arcs.append(arc)

    arcs = [a for a in arcs if a is not None]

    if not apply_cooldown or not arcs:
        return arcs

    cooldowns = arc_cooldown.load_cooldowns()
    visible_arcs: list[Arc] = []
    for arc in arcs:
        cooldown_days = arc_cooldown.ARC_COOLDOWNS.get(arc.name, 0)
        if (
            arc.severity != "survival"
            and arc_cooldown.is_suppressed(arc.name, cooldowns, cooldown_days)
        ):
            continue
        visible_arcs.append(arc)
        cooldowns = arc_cooldown.record_fired(arc.name, cooldowns)

    arc_cooldown.save_cooldowns(cooldowns)
    return visible_arcs


def check_survival_trigger(state_entries: list) -> bool:
    """
    Returns True if survival mode should be active.
    Trigger: STATE in (depleted, grieving) for 2+ of the last 3 entries.
    """
    if not state_entries:
        return False
    recent = [_tag(e) for e in state_entries[-3:]]
    return sum(1 for t in recent if t in SURVIVAL_TRIGGER_TAGS) >= 2
