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

# WIN detection patterns — regex, intentionally conservative to avoid false positives
_WIN_PATTERNS: list[str] = [
    r"\bactually (?:showered|brushed|cleaned|cooked|ate|called|texted|sent|wrote|went|did|fixed|finished|replied|responded|started)\b",
    r"\bfinally (?:sent|called|texted|did|wrote|fixed|finished|showered|cleaned|replied|responded|started|made)\b",
    r"\b(?:did the thing|got it done|went anyway|showed up anyway|pushed through|made myself)\b",
    r"\b(?:talked|called|texted) .{2,30} and it (?:went|was) (?:okay|ok|good|fine|well|better)\b",
    r"\bactually (?:made it|got up|got out|got there)\b",
]


VALID_STATE_TAGS = frozenset(
    ["surviving", "stable", "thriving", "grieving", "manic", "depleted", "flooded", "clear"]
)

# Keyword → STATE tag mapping (ordered: most-specific patterns first).
# Important: patterns are checked in order and first match wins.
# Compound/specific phrases must come before single-word fallbacks.
_STATE_SIGNALS: list[tuple[list[str], str]] = [
    # Grieving — specific emotional loss language (before manic "can't stop" fires)
    (["can't stop crying", "cant stop crying", "crying", "grief", "grieving",
      "loss", "miss them", "miss him", "miss her", "fallen apart", "falling apart",
      "mourning", "heartbroken"], "grieving"),
    # Manic — high-velocity elevated STATE (not just hyper-focus, which is a MIND signal)
    # "can't stop coding/working/building" is MIND.focus=hyper, not necessarily manic state
    (["ideas everywhere", "going going going", "unstoppable", "hypomanic",
      "been awake since", "wired and", "feel electric", "feel unstoppable",
      "everything is clicking and", "shipped three things", "shipped five things",
      "ELECTRIC", "manic energy", "manic episode"], "manic"),
    # Flooded — overwhelm/nervous system
    (["flooded", "drowning", "too much", "overwhelmed", "spinning out",
      "spinning", "can't breathe", "cant breathe", "too many threads",
      "too many tabs"], "flooded"),
    # Depleted — exhaustion/empty tank (running on fumes is specific to depleted)
    (["running on fumes", "running on spite", "fumes and spite",
      "exhausted", "drained", "empty", "nothing left", "depleted",
      "burnt out", "burned out", "dead inside", "can't keep going",
      "cant keep going", "tank is empty"], "depleted"),
    # Surviving — bare minimum function
    (["barely", "getting through", "just surviving", "survival mode",
      "just making it"], "surviving"),
    # Clear — post-storm perceptual sharpness
    (["weird clarity", "weirdly clear", "post-storm", "unusually clear",
      "hyper-clear", "post-cry clarity", "strangely calm"], "clear"),
    # Thriving — genuine forward momentum
    (["good", "clicking", "in it", "alive", "on fire", "flow state",
      "thriving", "nailing it", "really good", "feeling good"], "thriving"),
    # Stable — neutral baseline (last resort before stable)
    (["okay", "fine", "neutral", "alright", "not bad", "just here",
      "stable", "baseline"], "stable"),
]

# BODY signal patterns: (regex patterns, category, default_status_fn)
_BODY_SIGNALS: list[tuple[list[str], str]] = [
    (["no sleep", "didn't sleep", "haven't slept", "up since", "no rest", "awake all", "couldn't sleep", "insomnia", "sleep deprived"], "sleep"),
    (["ate", "eating", "food", "hungry", "starving", "forgot to eat", "haven't eaten", "skipped lunch", "skipped dinner", "no food", "meal"], "hunger"),
    (["pain", "ache", "aching", "sore", "hurts", "hurting", "stiff", "cramping", "headache", "migraine"], "pain"),
    (["walked", "walking", "run", "running", "exercise", "gym", "yoga", "dog park", "stretched", "moved"], "movement"),
    (["coffee", "caffeine", "weed", "alcohol", "beer", "wine", "meds", "medication", "adderall", "vyvanse", "thc", "cbd", "drink", "drinking", "smoke", "smoking"], "substances"),
    (["exhausted", "tired", "wiped", "no energy", "running low", "drained", "spent"], "energy"),
]

# MIND signal patterns
_MIND_SIGNALS: list[tuple[list[str], str, str]] = [
    (["can't stop working", "cant stop working", "can't stop coding", "cant stop coding", "can't stop building", "hyperfocus", "hyper-focus", "locked in", "won't stop", "wont stop"], "focus", "hyper"),
    (["can't focus", "cant focus", "scattered", "distracted", "all over the place", "no focus", "mind won't", "mind wont"], "focus", "scattered"),
    (["in the zone", "flow state", "deep work", "hours passed", "lost track of time", "zone"], "flow", "high"),
    (["too many tabs", "too many threads", "overwhelmed", "too much to hold", "spinning", "mental load"], "overwhelm", "high"),
    (["clear", "thinking clearly", "sharp", "seeing clearly", "lucid", "focused"], "clarity", "high"),
]

# SPIRIT signal patterns
_SPIRIT_SIGNALS: list[tuple[list[str], str, str]] = [
    (["alone", "lonely", "isolated", "no one", "haven't talked", "haven't seen", "disconnected", "by myself"], "isolation", "high"),
    (["talked to", "connected", "reaching out", "plans with", "saw", "called", "texted", "feeling seen", "together"], "connection", "rising"),
    (["creative", "inspired", "making", "art", "building something", "creating", "ideas flowing"], "creativity", "rising"),
    (["purpose", "meaning", "matters", "why i do this", "feels right", "aligned"], "purpose", "present"),
]


@dataclass
class Entry:
    track: str          # STATE, BODY, MIND, SPIRIT, INTENTION
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
            entries.append(Entry(
                track="BODY",
                date=log_date,
                category=category,
                status=status,
                note=snippet,
            ))
    return entries


def _infer_body_status(category: str, text_lower: str) -> str:
    if category == "sleep":
        if any(k in text_lower for k in ["no sleep", "didn't sleep", "haven't slept", "up since", "awake all", "couldn't sleep", "insomnia"]):
            return "none"
        if any(k in text_lower for k in ["poor sleep", "bad sleep", "broken sleep"]):
            return "poor"
        return "low"
    if category == "hunger":
        if any(k in text_lower for k in ["starving", "haven't eaten", "forgot to eat", "no food"]):
            return "starving"
        if any(k in text_lower for k in ["skipped", "forgot"]):
            return "ignored"
        return "fed"
    if category == "pain":
        if any(k in text_lower for k in ["acute", "severe", "unbearable"]):
            return "acute"
        if any(k in text_lower for k in ["really sore", "bad pain", "worst"]):
            return "high"
        if any(k in text_lower for k in ["ache", "sore", "stiff", "headache", "migraine"]):
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
            entries.append(Entry(
                track="MIND",
                date=log_date,
                category=category,
                status=status,
                note=snippet,
            ))
    return entries


def _extract_spirit_entries(text: str, log_date: str) -> list[Entry]:
    entries = []
    t = text.lower()
    for keywords, category, status in _SPIRIT_SIGNALS:
        if any(kw in t for kw in keywords):
            snippet = _find_snippet(text, keywords)
            entries.append(Entry(
                track="SPIRIT",
                date=log_date,
                category=category,
                status=status,
                note=snippet,
            ))
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
                if stop in note[m.end() - start:]:
                    note = note[:note.index(stop, m.end() - start)].strip()
                    break
            wins.append(Entry(
                track="WIN",
                date=log_date,
                category=None,
                status=None,
                note=note[:120],
            ))
    return wins


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
                snippet = snippet[snippet.find(" ") + 1 :] if " " in snippet else snippet
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
    entries.append(Entry(
        track="STATE",
        date=log_date,
        category=state_tag,
        status=None,
        note=narrative,
    ))

    # 2. BODY
    entries.extend(_extract_body_entries(text, log_date))

    # 3. MIND
    entries.extend(_extract_mind_entries(text, log_date))

    # 4. SPIRIT
    entries.extend(_extract_spirit_entries(text, log_date))

    # 5. WIN — not deduped (multiple wins are valid)
    wins = _extract_win_entries(text, log_date)
    entries.extend(wins)

    return _dedup_by_category([e for e in entries if e.track != "WIN"]) + wins


def format_garden_commands(entries: list[Entry], graph: str = "cassette") -> list[str]:
    """Return list of garden remember commands for all entries."""
    return [
        f"garden remember '{e.to_garden()}' --graph {graph}"
        for e in entries
    ]
