# maps · cassette.help · MIT
"""
vent_parser.py — Free-form text → structured maps-os log entries.

Input:  raw text string
Output: list of Entry dicts ready for garden logging
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional

try:
    from environments.maps_os_config import known_people
except Exception:
    known_people = lambda: []

# WIN detection patterns — regex, intentionally conservative to avoid false positives
_WIN_PATTERNS: list[str] = [
    r"\bactually (?:showered|brushed|cleaned|cooked|ate|called|texted|sent|wrote|went|did|fixed|finished|replied|responded|started)\b",
    r"\bfinally (?:sent|called|texted|did|wrote|fixed|finished|showered|cleaned|replied|responded|started|made)\b",
    r"\b(?:did the thing|got it done|went anyway|showed up anyway|pushed through|made myself)\b",
    r"\b(?:talked|called|texted) .{2,30} and it (?:went|was) (?:okay|ok|good|fine|well|better)\b",
    r"\bactually (?:made it|got up|got out|got there)\b",
]


VALID_STATE_TAGS = frozenset(
    [
        "surviving",
        "stable",
        "thriving",
        "grieving",
        "manic",
        "depleted",
        "flooded",
        "clear",
    ]
)

# Keyword → STATE tag mapping (ordered: most-specific patterns first).
# Important: patterns are checked in order and first match wins.
# Compound/specific phrases must come before single-word fallbacks.
_STATE_SIGNALS: list[tuple[list[str], str]] = [
    # Grieving — specific emotional loss language (before manic "can't stop" fires)
    (
        [
            "can't stop crying",
            "cant stop crying",
            "crying",
            "grief",
            "grieving",
            "loss",
            "miss them",
            "miss him",
            "miss her",
            "fallen apart",
            "falling apart",
            "mourning",
            "heartbroken",
        ],
        "grieving",
    ),
    # Manic — high-velocity elevated STATE (not just hyper-focus, which is a MIND signal)
    # "can't stop coding/working/building" is MIND.focus=hyper, not necessarily manic state
    (
        [
            "ideas everywhere",
            "going going going",
            "unstoppable",
            "hypomanic",
            "been awake since",
            "wired and",
            "feel electric",
            "feel unstoppable",
            "everything is clicking and",
            "shipped three things",
            "shipped five things",
            "ELECTRIC",
            "manic energy",
            "manic episode",
        ],
        "manic",
    ),
    # Flooded — overwhelm/nervous system
    (
        [
            "flooded",
            "drowning",
            "too much",
            "overwhelmed",
            "spinning out",
            "spinning",
            "can't breathe",
            "cant breathe",
            "too many threads",
            "too many tabs",
        ],
        "flooded",
    ),
    # Depleted — exhaustion/empty tank (running on fumes is specific to depleted)
    (
        [
            "running on fumes",
            "running on spite",
            "fumes and spite",
            "exhausted",
            "drained",
            "empty",
            "nothing left",
            "depleted",
            "burnt out",
            "burned out",
            "dead inside",
            "can't keep going",
            "cant keep going",
            "tank is empty",
        ],
        "depleted",
    ),
    # Surviving — bare minimum function
    (
        [
            "barely",
            "getting through",
            "just surviving",
            "survival mode",
            "just making it",
        ],
        "surviving",
    ),
    # Clear — post-storm perceptual sharpness
    (
        [
            "weird clarity",
            "weirdly clear",
            "post-storm",
            "unusually clear",
            "hyper-clear",
            "post-cry clarity",
            "strangely calm",
        ],
        "clear",
    ),
    # Thriving — genuine forward momentum
    (
        [
            "good",
            "clicking",
            "in it",
            "alive",
            "on fire",
            "flow state",
            "thriving",
            "nailing it",
            "really good",
            "feeling good",
        ],
        "thriving",
    ),
    # Stable — neutral baseline (last resort before stable)
    (
        [
            "okay",
            "fine",
            "neutral",
            "alright",
            "not bad",
            "just here",
            "stable",
            "baseline",
        ],
        "stable",
    ),
]

# BODY signal patterns: (regex patterns, category, default_status_fn)
_BODY_SIGNALS: list[tuple[list[str], str]] = [
    (
        [
            "no sleep",
            "didn't sleep",
            "haven't slept",
            "up since",
            "no rest",
            "awake all",
            "couldn't sleep",
            "insomnia",
            "sleep deprived",
        ],
        "sleep",
    ),
    (
        [
            "ate",
            "eating",
            "food",
            "hungry",
            "starving",
            "forgot to eat",
            "haven't eaten",
            "skipped lunch",
            "skipped dinner",
            "no food",
            "meal",
        ],
        "hunger",
    ),
    (
        [
            "pain",
            "ache",
            "aching",
            "sore",
            "hurts",
            "hurting",
            "stiff",
            "cramping",
            "headache",
            "migraine",
            "back hurts",
            "neck stiff",
            "eye strain",
            "tension headache",
            "shoulder pain",
            "jaw tight",
        ],
        "pain",
    ),
    (
        [
            "walked",
            "walking",
            "run",
            "running",
            "exercise",
            "gym",
            "yoga",
            "dog park",
            "stretched",
            "moved",
        ],
        "movement",
    ),
    (
        [
            "coffee",
            "caffeine",
            "weed",
            "alcohol",
            "beer",
            "wine",
            "meds",
            "medication",
            "adderall",
            "vyvanse",
            "thc",
            "cbd",
            "drink",
            "drinking",
            "smoke",
            "smoking",
        ],
        "substances",
    ),
    (
        ["exhausted", "tired", "wiped", "no energy", "running low", "drained", "spent"],
        "energy",
    ),
]

# MIND signal patterns
_MIND_SIGNALS: list[tuple[list[str], str, str]] = [
    (
        [
            "can't stop working",
            "cant stop working",
            "can't stop coding",
            "cant stop coding",
            "can't stop building",
            "hyperfocus",
            "hyper-focus",
            "locked in",
            "won't stop",
            "wont stop",
        ],
        "focus",
        "hyper",
    ),
    (
        [
            "can't focus",
            "cant focus",
            "scattered",
            "distracted",
            "all over the place",
            "no focus",
            "mind won't",
            "mind wont",
        ],
        "focus",
        "scattered",
    ),
    (
        [
            "in the zone",
            "flow state",
            "deep work",
            "hours passed",
            "lost track of time",
            "zone",
        ],
        "flow",
        "high",
    ),
    (
        [
            "too many tabs",
            "too many threads",
            "overwhelmed",
            "too much to hold",
            "spinning",
            "mental load",
        ],
        "overwhelm",
        "high",
    ),
    (
        ["clear", "thinking clearly", "sharp", "seeing clearly", "lucid", "focused"],
        "clarity",
        "high",
    ),
]

# SPIRIT signal patterns
_SPIRIT_SIGNALS: list[tuple[list[str], str, str]] = [
    (
        [
            "alone",
            "lonely",
            "isolated",
            "no one",
            "haven't talked",
            "haven't seen",
            "disconnected",
            "by myself",
        ],
        "isolation",
        "high",
    ),
    (
        [
            "talked to",
            "connected",
            "reaching out",
            "plans with",
            "saw",
            "called",
            "texted",
            "feeling seen",
            "together",
        ],
        "connection",
        "rising",
    ),
    (
        [
            "creative",
            "inspired",
            "making",
            "art",
            "building something",
            "creating",
            "ideas flowing",
        ],
        "creativity",
        "rising",
    ),
    (
        ["purpose", "meaning", "matters", "why i do this", "feels right", "aligned"],
        "purpose",
        "present",
    ),
]


@dataclass
class Entry:
    track: str  # STATE, BODY, MIND, SPIRIT, INTENTION
    date: str
    category: Optional[str]
    status: Optional[str]
    note: str

    def to_garden(self) -> str:
        """Format as garden remember string."""
        if self.track == "STATE":
            return f"STATE: {self.date} | {self.category} | {self.note}"
        if self.track in ("BODY", "MIND", "SPIRIT"):
            return f"{self.track}: {self.date} | {self.category} | {self.status} | {self.note}"
        if self.track == "INTENTION":
            return f"INTENTION: {self.category} | {self.status} | {self.date} | {self.note}"
        if self.track == "WIN":
            return f"WIN: {self.date} | {self.note}"
        if self.track == "PERSON":
            return f"PERSON: {self.date} | {self.note}"
        if self.track == "DECISION":
            return f"DECISION: {self.date} | {self.note}"
        if self.track == "RESISTANCE":
            return f"RESISTANCE: {self.date} | {self.note}"
        if self.track == "TRIGGER":
            return f"TRIGGER: {self.date} | {self.note}"
        if self.track == "GOAL":
            return f"GOAL: {self.date} | {self.note}"
        if self.track == "EVENT":
            return f"EVENT: {self.date} | {self.note}"
        if self.track == "DEADLINE":
            return f"DEADLINE: {self.date} | {self.note}"
        return f"{self.track}: {self.date} | {self.note}"


def _today() -> str:
    return date.today().isoformat()


def _lower_contains(text: str, keywords: list[str]) -> bool:
    t = text.lower()
    return any(kw in t for kw in keywords)


def _infer_state_tag(text: str) -> str:
    """Return the best-matching STATE tag for the text."""
    t = text.lower()
    for keywords, tag in _STATE_SIGNALS:
        if any(kw in t for kw in keywords):
            return tag
    return "stable"


def _extract_body_entries(text: str, log_date: str) -> list[Entry]:
    entries = []
    t = text.lower()
    for keywords, category in _BODY_SIGNALS:
        if any(kw in t for kw in keywords):
            # Find the matching snippet for the note
            snippet = _find_snippet(text, keywords)
            status = _infer_body_status(category, t)
            entries.append(
                Entry(
                    track="BODY",
                    date=log_date,
                    category=category,
                    status=status,
                    note=snippet,
                )
            )
    return entries


def _infer_body_status(category: str, text_lower: str) -> str:
    if category == "sleep":
        if any(
            k in text_lower
            for k in [
                "kept waking",
                "woke up at",
                "broken sleep",
                "woke up in the night",
            ]
        ):
            return "broken"
        if any(
            k in text_lower
            for k in [
                "couldn't fall asleep",
                "tossed and turned",
                "can't sleep",
            ]
        ):
            return "restless"
        if any(
            k in text_lower
            for k in [
                "slept through",
                "actually rested",
                "best sleep",
                "finally slept",
            ]
        ):
            return "deep"
        if any(
            k in text_lower
            for k in [
                "slept too long",
                "slept 12 hours",
                "can't get up",
                "slept all day",
            ]
        ):
            return "overslept"
        if any(
            k in text_lower
            for k in [
                "no sleep",
                "didn't sleep",
                "haven't slept",
                "up since",
                "awake all",
                "couldn't sleep",
                "insomnia",
            ]
        ):
            return "none"
        if any(k in text_lower for k in ["poor sleep", "bad sleep"]):
            return "poor"
        return "ok"
    if category == "hunger":
        if any(
            k in text_lower
            for k in ["starving", "haven't eaten", "forgot to eat", "no food"]
        ):
            return "starving"
        if any(k in text_lower for k in ["skipped", "forgot"]):
            return "ignored"
        return "fed"
    if category == "pain":
        if any(k in text_lower for k in ["acute", "severe", "unbearable"]):
            return "acute"
        if any(k in text_lower for k in ["really sore", "bad pain", "worst"]):
            return "high"
        if any(
            k in text_lower for k in ["ache", "sore", "stiff", "headache", "migraine"]
        ):
            return "present"
        return "low"
    if category == "movement":
        if any(k in text_lower for k in ["gym", "run", "ran", "yoga", "exercise"]):
            return "active"
        return "some"
    if category == "energy":
        if any(k in text_lower for k in ["exhausted", "wiped", "drained", "no energy"]):
            return "exhausted"
        return "low"
    return "present"


def _extract_mind_entries(text: str, log_date: str) -> list[Entry]:
    entries = []
    t = text.lower()
    for keywords, category, status in _MIND_SIGNALS:
        if any(kw in t for kw in keywords):
            snippet = _find_snippet(text, keywords)
            entries.append(
                Entry(
                    track="MIND",
                    date=log_date,
                    category=category,
                    status=status,
                    note=snippet,
                )
            )
    return entries


def _extract_spirit_entries(text: str, log_date: str) -> list[Entry]:
    entries = []
    t = text.lower()
    for keywords, category, status in _SPIRIT_SIGNALS:
        if any(kw in t for kw in keywords):
            snippet = _find_snippet(text, keywords)
            entries.append(
                Entry(
                    track="SPIRIT",
                    date=log_date,
                    category=category,
                    status=status,
                    note=snippet,
                )
            )
    return entries


def _extract_win_entries(text: str, log_date: str) -> list[Entry]:
    """Extract WIN entries from vent text — things accomplished despite resistance."""
    wins = []
    t_lower = text.lower()
    for pattern in _WIN_PATTERNS:
        m = re.search(pattern, t_lower)
        if m:
            # Grab the full phrase around the match
            start = max(0, m.start() - 5)
            end = min(len(text), m.end() + 30)
            note = text[start:end].strip().rstrip(".,!?;")
            # Trim to sentence boundary if possible
            for stop in (".", "!", "?", ","):
                if stop in note[m.end() - start :]:
                    note = note[: note.index(stop, m.end() - start)].strip()
                    break
            wins.append(
                Entry(
                    track="WIN",
                    date=log_date,
                    category=None,
                    status=None,
                    note=note[:120],
                )
            )
    return wins


def _extract_person_entries(text: str, log_date: str) -> list[Entry]:
    """Extract PERSON entries — names from known_people or interaction keywords."""
    entries = []
    t_lower = text.lower()

    _PERSON_KEYWORDS = [
        "talked to",
        "called",
        "texted",
        "plans with",
        "saw",
        "reached out to",
    ]
    known = known_people()

    matched_people: set[str] = set()

    for kw in _PERSON_KEYWORDS:
        if kw in t_lower:
            idx = t_lower.find(kw)
            start = max(0, idx - 30)
            end = min(len(text), idx + len(kw) + 30)
            context = text[start:end].strip()
            name = _extract_name_from_context(context, kw)
            if name:
                matched_people.add(name)

    for person in known:
        if person in t_lower:
            matched_people.add(person)

    for name in matched_people:
        sentiment = _infer_sentiment(text, name)
        context = _extract_context_phrase(text, name)
        entries.append(
            Entry(
                track="PERSON",
                date=log_date,
                category=None,
                status=None,
                note=f"{name} | {context} | {sentiment}",
            )
        )

    return entries


def _extract_name_from_context(context: str, keyword: str) -> str:
    """Extract name following a keyword in context."""
    t_lower = context.lower()
    idx = t_lower.find(keyword)
    if idx >= 0:
        start = idx + len(keyword)
        rest = context[start : start + 30].strip()
        if rest:
            words = rest.split()
            if words:
                name = words[0].rstrip(".,!?;:").strip("'\"")
                if (
                    name
                    and len(name) >= 2
                    and name.lower()
                    not in ("to", "with", "the", "a", "an", "and", "for")
                ):
                    return name.lower()
    return ""


def _extract_context_phrase(text: str, name: str) -> str:
    """Extract context phrase near a name mention."""
    t_lower = text.lower()
    name_lower = name.lower()
    idx = t_lower.find(name_lower)
    if idx >= 0:
        start = max(0, idx - 15)
        end = min(len(text), idx + len(name) + 25)
        phrase = text[start:end].strip()
        return phrase[:50]
    return "interaction"


def _infer_sentiment(text: str, name: str) -> str:
    """Infer sentiment from text near name mention."""
    t_lower = text.lower()
    idx = t_lower.find(name.lower())
    if idx >= 0:
        window = t_lower[max(0, idx - 30) : min(len(t_lower), idx + 30)]
        if any(
            k in window
            for k in ["good", "great", "loved", "nice", "fun", "awesome", "amazing"]
        ):
            return "positive"
        if any(
            k in window
            for k in ["hard", "difficult", "drained", "upset", "tired", "exhausting"]
        ):
            return "negative"
    return "neutral"


def _extract_decision_entries(text: str, log_date: str) -> list[Entry]:
    """Extract DECISION entries — unresolved choices."""
    entries = []
    t_lower = text.lower()

    _DECISION_TRIGGERS = [
        "i don't know if i should",
        "should i",
        "can't decide between",
        "not sure whether to",
        "weighing",
    ]

    for trigger in _DECISION_TRIGGERS:
        if trigger in t_lower:
            idx = t_lower.find(trigger)
            start = max(0, idx - 10)
            end = min(len(text), idx + len(trigger) + 60)
            note = text[start:end].strip().rstrip(".,!?;")
            entries.append(
                Entry(
                    track="DECISION",
                    date=log_date,
                    category=None,
                    status=None,
                    note=note[:80],
                )
            )
            break

    return entries


def _extract_resistance_entries(text: str, log_date: str) -> list[Entry]:
    """Extract RESISTANCE entries — avoidance signals."""
    entries = []
    t_lower = text.lower()

    _RESISTANCE_TRIGGERS = [
        ("i don't want to", "medium"),
        ("i keep avoiding", "medium"),
        ("can't bring myself to", "high"),
        ("dreading", "high"),
        ("the thought of", "high"),
        ("can't start", "high"),
        ("not feeling it", "medium"),
        ("maybe later", "low"),
    ]

    for trigger, default_intensity in _RESISTANCE_TRIGGERS:
        if trigger in t_lower:
            idx = t_lower.find(trigger)
            start = max(0, idx - 15)
            end = min(len(text), idx + len(trigger) + 40)
            phrase = text[start:end].strip().rstrip(".,!?;")
            intensity = _infer_intensity(text, phrase, default_intensity)
            entries.append(
                Entry(
                    track="RESISTANCE",
                    date=log_date,
                    category=None,
                    status=None,
                    note=f"{phrase[:50]} | {intensity}",
                )
            )

    return entries


def _infer_intensity(text: str, phrase: str, default: str) -> str:
    """Infer resistance intensity from context."""
    t_lower = (text + " " + phrase).lower()
    if any(
        k in t_lower for k in ["dreading", "can't face", "terrified", "overwhelmed"]
    ):
        return "high"
    if any(k in t_lower for k in ["don't want", "not feeling"]):
        return "medium"
    return default


def _extract_trigger_entries(text: str, log_date: str) -> list[Entry]:
    """Extract TRIGGER entries — emotional triggers."""
    entries = []
    t_lower = text.lower()

    _TRIGGER_PATTERNS = [
        "when i saw",
        "triggered by",
        "set off by",
        "they said",
        "she said",
        "he said",
        "told me",
    ]

    for pattern in _TRIGGER_PATTERNS:
        if pattern in t_lower:
            idx = t_lower.find(pattern)
            start = max(0, idx - 20)
            end = min(len(text), idx + len(pattern) + 40)
            phrase = text[start:end].strip().rstrip(".,!?;")
            reaction = _extract_reaction(text, phrase)
            entries.append(
                Entry(
                    track="TRIGGER",
                    date=log_date,
                    category=None,
                    status=None,
                    note=f"{phrase[:40]} | {reaction}",
                )
            )

    return entries


def _extract_reaction(text: str, trigger_phrase: str) -> str:
    """Extract reaction following a trigger."""
    t_lower = text.lower()
    idx = t_lower.find(trigger_phrase.lower())
    if idx >= 0:
        end = min(len(text), idx + len(trigger_phrase) + 30)
        reaction = text[idx:end].strip()
        if len(reaction) > 5:
            return reaction[:30]
    return "reaction"


def _extract_goal_entries(text: str, log_date: str) -> list[Entry]:
    """Extract GOAL entries — intentions and goals."""
    entries = []
    t_lower = text.lower()

    _GOAL_TRIGGERS = [
        "i want to",
        "i'd like to",
        "my goal is",
        "planning to",
        "hoping to",
        "i need to make sure",
        "i should really",
    ]

    for trigger in _GOAL_TRIGGERS:
        if trigger in t_lower:
            idx = t_lower.find(trigger)
            start = idx
            end = min(len(text), idx + len(trigger) + 80)
            rest = text[start:end].strip()
            if rest:
                for stop in (".", "!", "?"):
                    if stop in rest:
                        rest = rest[: rest.index(stop)].strip()
                        break
                if rest:
                    entries.append(
                        Entry(
                            track="GOAL",
                            date=log_date,
                            category=None,
                            status=None,
                            note=f"{rest[:60]} | none | open",
                        )
                    )

    return entries


def _extract_event_entries(text: str, log_date: str, today=None) -> list[Entry]:
    """Extract EVENT entries from text."""
    try:
        from environments.date_resolver import resolve_date as _resolve_date
    except Exception:
        _resolve_date = None

    if today is None:
        today = date.today()

    entries = []
    t_lower = text.lower()

    _EVENT_TRIGGERS = [
        "therapy on",
        "appointment on",
        "appointment",
        "meeting on",
        "on monday",
        "on tuesday",
        "on wednesday",
        "on thursday",
        "on friday",
        "on saturday",
        "on sunday",
        "that thing on",
    ]
    _DATE_PHRASE_RE = re.compile(
        r"\b(?:today|tomorrow|next week|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|monday|tuesday|wednesday|thursday|friday|saturday|sunday|in\s+\d+\s+days?|in\s+\d+\s+weeks?)\b"
    )
    seen_matches: list[tuple[int, int, str]] = []

    for trigger in _EVENT_TRIGGERS:
        for match in re.finditer(re.escape(trigger), t_lower):
            window_start = match.start()
            window_end = min(len(text), match.end() + 60)
            window_lower = t_lower[window_start:window_end]
            date_match = _DATE_PHRASE_RE.search(window_lower)
            if not date_match or not _resolve_date:
                continue

            date_phrase = window_lower[date_match.start() : date_match.end()]
            event_date = _resolve_date(date_phrase, today)
            if not event_date:
                continue

            event_date_iso = event_date.isoformat()
            if any(
                seen_date == event_date_iso
                and not (match.end() <= seen_start or match.start() >= seen_end)
                for seen_start, seen_end, seen_date in seen_matches
            ):
                continue
            seen_matches.append((match.start(), match.end(), event_date_iso))

            description = text[window_start:window_end].strip().rstrip(".,!?;")
            entries.append(
                Entry(
                    track="EVENT",
                    date=log_date,
                    category=None,
                    status=None,
                    note=f"{event_date_iso} | {description[:60]}",
                )
            )

    return entries


def _extract_deadline_entries(text: str, log_date: str, today=None) -> list[Entry]:
    """Extract DEADLINE entries from text."""
    try:
        from environments.date_resolver import resolve_date as _resolve_date
    except Exception:
        _resolve_date = None

    entries = []
    t_lower = text.lower()

    _DEADLINE_TRIGGERS = [
        ("due by", "high"),
        ("deadline", "medium"),
        ("need to finish by", "medium"),
        ("submit by", "medium"),
        ("urgent", "high"),
        ("asap", "high"),
    ]

    for trigger, default_urgency in _DEADLINE_TRIGGERS:
        if trigger in t_lower:
            idx = t_lower.find(trigger)
            start = max(0, idx - 10)
            end = min(len(text), idx + len(trigger) + 50)
            phrase = text[start:end].strip().rstrip(".,!?")

            t_phrase = phrase.lower()
            urgency = default_urgency
            if any(k in t_phrase for k in ["urgent", "asap", "today"]):
                urgency = "high"
            elif any(k in t_phrase for k in ["tomorrow", "next day", "1 day"]):
                urgency = "high"

            entries.append(
                Entry(
                    track="DEADLINE",
                    date=log_date,
                    category=None,
                    status=urgency,
                    note=f"none | {phrase[:40]}",
                )
            )

    return entries


def _find_snippet(original_text: str, keywords: list[str]) -> str:
    """Extract a short phrase around the first keyword match."""
    t_lower = original_text.lower()
    for kw in keywords:
        idx = t_lower.find(kw)
        if idx >= 0:
            start = max(0, idx - 15)
            end = min(len(original_text), idx + len(kw) + 30)
            snippet = original_text[start:end].strip()
            # Clean up partial words at boundaries
            if start > 0 and not original_text[start - 1].isspace():
                snippet = (
                    snippet[snippet.find(" ") + 1 :] if " " in snippet else snippet
                )
            return snippet.rstrip(".,!?;")
    return ""


def _dedup_by_category(entries: list[Entry]) -> list[Entry]:
    """Keep first entry per (track, category) pair."""
    seen: set[tuple[str, str | None]] = set()
    out = []
    for e in entries:
        key = (e.track, e.category)
        if key not in seen:
            seen.add(key)
            out.append(e)
    return out


def parse_vent(text: str, log_date: Optional[str] = None) -> list[Entry]:
    """
    Parse free-form vent text into structured log entries.

    Returns a list of Entry objects ordered: STATE first, then BODY, MIND, SPIRIT.
    """
    if not text or not text.strip():
        return []

    log_date = log_date or _today()
    entries: list[Entry] = []

    # 1. STATE — always exactly one
    state_tag = _infer_state_tag(text)
    # Use a condensed narrative from the text (first 80 chars, cleaned)
    narrative = text.strip()
    if len(narrative) > 80:
        narrative = narrative[:77].rsplit(" ", 1)[0] + "..."
    entries.append(
        Entry(
            track="STATE",
            date=log_date,
            category=state_tag,
            status=None,
            note=narrative,
        )
    )

    # 2. BODY
    entries.extend(_extract_body_entries(text, log_date))

    # 3. MIND
    entries.extend(_extract_mind_entries(text, log_date))

    # 4. SPIRIT
    entries.extend(_extract_spirit_entries(text, log_date))

    # 5. WIN — not deduped (multiple wins are valid)
    wins = _extract_win_entries(text, log_date)
    entries.extend(wins)

    # 6. New entry types — not deduped (each instance is meaningful)
    entries.extend(_extract_person_entries(text, log_date))
    entries.extend(_extract_decision_entries(text, log_date))
    entries.extend(_extract_resistance_entries(text, log_date))
    entries.extend(_extract_trigger_entries(text, log_date))
    entries.extend(_extract_goal_entries(text, log_date))
    entries.extend(_extract_event_entries(text, log_date, date.today()))
    entries.extend(_extract_deadline_entries(text, log_date, date.today()))
    non_dedup_tracks = {"WIN", "EVENT", "DEADLINE"}
    deduped = _dedup_by_category([e for e in entries if e.track not in non_dedup_tracks])
    non_deduped = [e for e in entries if e.track in non_dedup_tracks]
    return deduped + non_deduped


def format_garden_commands(entries: list[Entry], graph: str = "cassette") -> list[str]:
    """Return list of garden remember commands for all entries."""
    return [f"garden remember '{e.to_garden()}' --graph {graph}" for e in entries]
