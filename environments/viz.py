# maps · cassette.help · MIT
"""
viz.py — Visualization utilities for maps-os.

Rich-only rendering for state trends, body signals, and arc history.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

STATE_COLORS = {
    "depleted": "red",
    "grieving": "red",
    "surviving": "yellow",
    "stable": "blue",
    "thriving": "green",
    "manic": "magenta",
    "flooded": "yellow",
    "clear": "cyan",
}


def _color_for_state(tag: str) -> str:
    return STATE_COLORS.get(tag.lower(), "white")


def render_trend(entries: list, days: int = 90) -> "rich.Text":
    """
    Render state trend as Unicode bar chart.

    Input: list of STATE entries (as dicts or Entry objects)
    Output: Rich Text block
    """
    try:
        from rich.text import Text
    except ImportError:
        return None

    if not entries:
        return Text("no state data")

    cutoff = date.today() - timedelta(days=days)
    seen_tags: set[str] = set()
    tag_by_date: dict[date, str] = {}

    for e in entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if not content.startswith("STATE:"):
            continue

        parts = content.split("|")
        if len(parts) < 2:
            continue

        date_str = parts[0].replace("STATE:", "").strip()
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue

        if entry_date >= cutoff:
            tag = parts[1].strip().lower()
            seen_tags.add(tag)
            tag_by_date[entry_date] = tag

    if not tag_by_date:
        return Text("no state data in range")

    days_list = [cutoff + timedelta(days=i) for i in range(days + 1)]
    days_present = sorted(tag_by_date.keys())

    text = Text()
    row_labels = sorted(seen_tags)

    for tag in row_labels:
        text.append(f"{tag:12}", _color_for_state(tag))
        for d in days_list:
            if d in tag_by_date and tag_by_date[d] == tag:
                text.append("█", _color_for_state(tag))
            else:
                text.append("░", "dim")
        text.append("\n")

    text.append("\nMonths:\n", "bold")
    months: dict[str, int] = {}
    for d in days_list:
        month = d.strftime("%b")
        months[month] = months.get(month, 0) + 1

    month_labels = []
    for i, d in enumerate(days_list):
        if d.day == 1:
            month_labels.append((i, d.strftime("%b")))

    for idx, label in month_labels:
        text.append(f"{label:>4}")

    return text


def render_viz(
    body_entries: list,
    state_entries: list,
    arc_history: Optional[list] = None,
) -> "rich console.console.Console":
    """
    Render visualization panels.

    Panel 1: state sparkline — last 14 days
    Panel 2: body presence — last 7 days
    Panel 3: arc frequency — last 30 days
    """
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.text import Text
    except ImportError:
        return None

    if arc_history is None:
        arc_history = []

    console = Console()

    text = Text()

    text.append("STATE sparkline (14 days)\n", "bold green")
    days = 14
    cutoff = date.today() - timedelta(days=days)
    state_by_date: dict[date, str] = {}

    for e in state_entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if not content.startswith("STATE:"):
            continue
        parts = content.split("|")
        if len(parts) >= 2:
            date_str = parts[0].replace("STATE:", "").strip()
            try:
                entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
                if entry_date >= cutoff:
                    state_by_date[entry_date] = parts[1].strip().lower()
            except Exception:
                pass

    for i in range(days):
        d = cutoff + timedelta(days=i)
        tag = state_by_date.get(d, "")
        if tag:
            text.append("█", _color_for_state(tag))
        else:
            text.append("·")
    text.append("\n\n")

    text.append("BODY signals (7 days)\n", "bold green")
    body_cutoff = date.today() - timedelta(days=7)
    categories = ["sleep", "hunger", "pain", "movement", "energy"]
    body_by_day: set[tuple[date, str]] = set()

    for e in body_entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if not content.startswith("BODY:"):
            continue
        parts = content.split("|")
        if len(parts) < 2:
            continue
        date_str = parts[0].replace("BODY:", "").strip()
        cat = parts[1].strip().lower()
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        body_by_day.add((entry_date, cat))

    for cat in categories:
        text.append(f"{cat:10}", "cyan")
        for i in range(7):
            d = body_cutoff + timedelta(days=i)
            present = (d, cat) in body_by_day
            if present:
                text.append("■", "green")
            else:
                text.append("·")
        text.append("\n")
    text.append("\n")

    text.append("ARC frequency (30 days)\n", "bold green")
    arc_counts: Counter = Counter()
    for arc in arc_history:
        if hasattr(arc, "name"):
            arc_counts[arc.name] += 1

    if arc_counts:
        for arc_name, count in arc_counts.most_common(10):
            text.append(f"{arc_name}: {count}\n")
    else:
        text.append("no arcs fired\n")

    return Panel(text, title="maps-os viz")


def render_trend_simple(entries: list, days: int = 90) -> str:
    """Simple text fallback for render_trend."""
    if not entries:
        return "no state data"

    cutoff = date.today() - timedelta(days=days)
    seen_tags: set[str] = set()
    tag_by_date: dict[date, str] = {}

    for e in entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if not content.startswith("STATE:"):
            continue
        parts = content.split("|")
        if len(parts) < 2:
            continue
        date_str = parts[0].replace("STATE:", "").strip()
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if entry_date >= cutoff:
            tag = parts[1].strip().lower()
            seen_tags.add(tag)
            tag_by_date[entry_date] = tag

    if not tag_by_date:
        return "no state data in range"

    lines = []
    for tag in sorted(seen_tags):
        line = f"{tag:12} "
        for d in range(days + 1):
            check_date = cutoff + timedelta(days=d)
            if check_date in tag_by_date and tag_by_date[check_date] == tag:
                line += "█"
            else:
                line += "░"
        lines.append(line)

    return "\n".join(lines)
