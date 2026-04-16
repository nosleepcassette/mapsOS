# maps · cassette.help · MIT
"""
roles.py — Embedded role/mode guidance for mapsOS.

STATE → suggested interaction mode, energy tier, ND-aware notes.
No external agent required. Designed for neurodivergent users.

To adapt for your own agent: extend MODE_PROFILES with your agent's
persona names and adjust STATE_MODE_MAP to taste.
"""

from __future__ import annotations

from datetime import date
from textwrap import wrap


MODE_PROFILES = {
    "witness": {
        "description": "hold space, no problem-solving",
        "energy": "Emergency",
        "nd_note": (
            "Do not reframe, redirect, or offer perspective. "
            "Named emotional experiences only. Silence is valid. "
            "This is not the time for executive function support."
        ),
        "suspend": ["springboard", "high-engagement", "manic-aware"],
    },
    "regulation-first": {
        "description": "body before cognition",
        "energy": "Low",
        "nd_note": (
            "Interoception is compromised when the tank is empty. "
            "One physical anchor first (water, food, position). "
            "Then check in. Don't start cognitive work until the body is acknowledged."
        ),
        "suspend": ["high-engagement", "springboard"],
    },
    "low-demand": {
        "description": "present without agenda",
        "energy": "Low",
        "nd_note": (
            "Don't introduce new tasks or decisions. "
            "Avoid open-ended planning questions. "
            "Demand-avoidance is real — keep the interaction low-stakes."
        ),
        "suspend": ["high-engagement"],
    },
    "springboard": {
        "description": "reflective — good for planning and pattern work",
        "energy": "Moderate",
        "nd_note": (
            "Reflective questions land here. Good time to surface patterns, "
            "name what's working, and make modest decisions. "
            "Avoid hyperfocus bait — keep sessions bounded."
        ),
        "suspend": ["witness", "regulation-first"],
    },
    "high-engagement": {
        "description": "full bandwidth — complex work, hard conversations",
        "energy": "High",
        "nd_note": (
            "Maximum cognitive bandwidth. Complex decisions land here. "
            "Watch for body neglect — high engagement can mask hunger and sleep signals. "
            "Check BODY before committing to a long sprint."
        ),
        "suspend": ["witness", "regulation-first", "low-demand"],
    },
    "manic-aware": {
        "description": "fast and connected — but unsustainable",
        "energy": "High",
        "nd_note": (
            "Elevated output is real but the pattern is unstable. "
            "Don't co-sign large plans or commitments yet. "
            "Note what's happening, log it, hold the decision for one sleep cycle."
        ),
        "suspend": ["high-engagement"],
    },
}


STATE_MODE_MAP = {
    "flooded": ("witness", "Emergency"),
    "grieving": ("witness", "Emergency"),
    "depleted": ("regulation-first", "Low"),
    "surviving": ("regulation-first", "Low"),
    "stable": ("low-demand", "Low"),
    "tender": ("low-demand", "Low"),
    "grounded": ("springboard", "Moderate"),
    "clear": ("springboard", "Moderate"),
    "thriving": ("high-engagement", "High"),
    "manic": ("manic-aware", "High"),
}


ARC_MODE_HINTS = {
    "manic_spike": "manic-aware — do not co-sign plans",
    "body_neglect": "regulation-first — body check before anything else",
    "isolation_creep": "low-demand — connection, not tasks",
    "state_dip_holding": "witness — survival mode active, no other modes",
    "post_manic_drop": "regulation-first — crash is predictable, rest is protocol",
    "productivity_spiral": "low-demand — disengage from output framing",
    "exec_dysfunction": "regulation-first then springboard — body first, then smallest step",
    "trust_rupture": "witness only — suppress everything else",
    "catastrophizing_spike": "low-demand — name the pattern, don't argue content",
    "planning_hyperfocus": "springboard — bound the session, don't let it spiral",
    "thriving_streak": "high-engagement — what's working? name and sustain it",
    "cycle_meta": "manic-aware — structural pattern, address the cycle not the state",
}


def _wrap_prefixed(prefix: str, text: str, width: int = 72) -> list[str]:
    if not text:
        return []
    hanging = " " * len(prefix)
    wrapped = wrap(text, width=width - len(prefix)) or [text]
    return [prefix + wrapped[0]] + [hanging + line for line in wrapped[1:]]


def format_role_output(state_tag: str, arcs: list) -> str:
    """
    Returns formatted role guidance block for maps check --role.

    arcs: list of Arc objects with .name, .severity, .message
    """
    mode, energy = STATE_MODE_MAP.get(state_tag, ("low-demand", "Low"))
    profile = MODE_PROFILES.get(mode, {})

    lines = []
    lines.append(f"ROLE GUIDANCE  ·  {date.today().isoformat()}")
    lines.append("")
    lines.append(f"  state      {state_tag}")
    lines.append(f"  mode       {mode}")
    lines.append(f"  energy     {energy}")
    lines.append("")
    lines.append(f"  approach   {profile.get('description', '')}")
    lines.extend(_wrap_prefixed("  nd-note   ", profile.get("nd_note", "")))

    arc_hints = []
    for arc in arcs:
        hint = ARC_MODE_HINTS.get(getattr(arc, "name", ""))
        if hint:
            severity = getattr(arc, "severity", "").upper() or "INFO"
            arc_hints.append(f"  arc hint   {severity}: {hint}")
    if arc_hints:
        lines.append("")
        lines.extend(arc_hints)

    suspend = profile.get("suspend", [])
    if suspend:
        lines.append("")
        lines.append(f"  suspend    {', '.join(suspend)}")

    return "\n".join(lines)
