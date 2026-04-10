# maps · cassette.help · MIT
"""
date_resolver.py — Convert relative date phrases to ISO dates.

Handles: "tomorrow", "today", "monday"-"sunday", "next week", "next [weekday]", "in N days/weeks".
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

_WEEKDAYS = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def resolve_date(text: str, today: Optional[date] = None) -> Optional[date]:
    """Convert relative date phrases to ISO date. Returns None if unresolvable."""
    if today is None:
        today = date.today()

    t = text.lower().strip()

    if t in ("today", "now"):
        return today

    if t in ("tomorrow", "tomorrow"):
        return today + timedelta(days=1)

    if t in _WEEKDAYS:
        target_weekday = _WEEKDAYS[t]
        days_ahead = (target_weekday - today.weekday() + 7) % 7
        if days_ahead == 0:
            days_ahead = 7
        return today + timedelta(days=days_ahead)

    if t.startswith("next "):
        rest = t[5:].strip()
        if rest in _WEEKDAYS:
            target_weekday = _WEEKDAYS[rest]
            days_ahead = (target_weekday - today.weekday() + 7) % 7 + 7
            return today + timedelta(days=days_ahead)

    if t == "next week":
        return today + timedelta(days=7)

    import re

    m = re.match(r"in\s+(\d+)\s+days?", t)
    if m:
        n = int(m.group(1))
        return today + timedelta(days=n)

    m = re.match(r"in\s+(\d+)\s+weeks?", t)
    if m:
        n = int(m.group(1))
        return today + timedelta(weeks=n)

    return None
