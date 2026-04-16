# maps · cassette.help · MIT
"""
viz.py — Visualization utilities for mapsOS.

Rich-only rendering for state trends, body signals, and arc history.
All functions return Rich renderables (Text, Table, Panel) or None on import failure.
"""

from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timedelta
from typing import Optional

# ── Energy axis ──────────────────────────────────────────────────────────────
# Maps state tags to a 1–7 energy level used for sparkline height.
# Flooded/manic sit high — not "good", but energetically loud.
ENERGY_LEVEL: dict[str, int] = {
    "depleted":  1,
    "surviving": 2,
    "grieving":  2,
    "stable":    3,
    "grounded":  4,
    "clear":     4,
    "tender":    4,
    "thriving":  5,
    "flooded":   6,
    "manic":     7,
}

# Block ramp — index = energy level (0 = not logged/gap)
_SPARK = [" ", "▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]

# ── Full RGB palette ─────────────────────────────────────────────────────────
STATE_RGB: dict[str, str] = {
    "depleted":  "#7a7a7a",
    "grieving":  "#7b9eb5",
    "surviving": "#c47c7c",
    "flooded":   "#d4893a",
    "manic":     "#b07fd4",
    "stable":    "#c0bdb4",
    "grounded":  "#5fa89b",
    "tender":    "#c97a95",
    "thriving":  "#7ab87e",
    "clear":     "#6abdd4",
}

# Backwards compat
STATE_COLORS = STATE_RGB

AMBER         = "#f3c97a"
AMBER_DIM     = "#8a6c3a"
AMBER_GLOW    = "#ffdf99"
CREAM         = "#f5e8c7"
PALE          = "#dbc59a"
MUTED         = "#9e8c78"
ALERT_COLOR   = "#e05c5c"
INSIGHT_COLOR = "#d4a84b"
SURVIVAL_COLOR = "#9e6ba8"


def _color_for_state(tag: str) -> str:
    return STATE_RGB.get(tag.lower(), AMBER)


def _parse_state_entries(entries: list, days: int) -> dict[date, str]:
    """Parse STATE entry list → {date: tag} dict, filtered to last N days."""
    cutoff = date.today() - timedelta(days=days)
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
            tag_by_date[entry_date] = parts[1].strip().lower()
    return tag_by_date


# ── Widget: state sparkline ──────────────────────────────────────────────────

def render_state_sparkline(entries: list, days: int = 30) -> "rich.text.Text | None":
    """
    Single-row sparkline. Bar height = energy level, color = state tag.

    ▁▁▂▂▃▃▄▄▄▅▅▅▆▆▅▅▄▄▃▃
    Missing days: · in dim.
    """
    try:
        from rich.text import Text
    except ImportError:
        return None

    tag_by_date = _parse_state_entries(entries, days)
    if not tag_by_date:
        return Text("no state data", style="dim")

    cutoff = date.today() - timedelta(days=days)
    text = Text()
    for i in range(days + 1):
        d = cutoff + timedelta(days=i)
        tag = tag_by_date.get(d)
        if tag:
            level = ENERGY_LEVEL.get(tag, 3)
            char = _SPARK[min(level, len(_SPARK) - 1)]
            text.append(char, style=_color_for_state(tag))
        else:
            text.append("·", style="dim")

    return text


# ── Widget: body heat grid ───────────────────────────────────────────────────

# Status quality map: category → {status_keyword: quality}
_BODY_QUALITY: dict[str, dict[str, str]] = {
    "sleep":    {
        "none": "bad", "poor": "bad", "broken": "bad",
        "ok": "neutral", "solid": "good", "deep": "good",
    },
    "hunger":   {
        "starving": "bad", "ignored": "bad",
        "fed": "neutral", "good": "good",
    },
    "pain":     {
        "none": "good", "low": "neutral", "present": "neutral",
        "high": "bad", "acute": "bad",
    },
    "movement": {
        "none": "bad", "minimal": "neutral",
        "some": "good", "active": "good",
    },
    "energy":   {"low": "bad", "medium": "neutral", "high": "good"},
    "substances": {},  # always neutral — just log presence
}

_QUALITY_COLOR = {
    "good":    "#7ab87e",   # sage green
    "neutral": AMBER,       # amber
    "bad":     "#c47c7c",   # dull coral
}

_BODY_CATEGORIES = ["sleep", "hunger", "pain", "movement", "energy"]


def render_body_heatgrid(entries: list, days: int = 7) -> "rich.table.Table | None":
    """
    N-day body presence grid with status-quality color coding.

    Rows: sleep, hunger, pain, movement, energy
    Cols: last N days
    Colors: green=good, amber=neutral, red=bad, ·· dim=not logged
    """
    try:
        from rich.table import Table
        from rich.text import Text
    except ImportError:
        return None

    cutoff = date.today() - timedelta(days=days - 1)
    days_list = [cutoff + timedelta(days=i) for i in range(days)]

    # Parse entries: (date, category) → quality
    cell_data: dict[tuple[date, str], str] = {}
    for e in entries:
        content = e.get("content", "") if isinstance(e, dict) else ""
        if not content.startswith("BODY:"):
            continue
        parts = [p.strip() for p in content.split("|")]
        if len(parts) < 3:
            continue
        date_str = parts[0].replace("BODY:", "").strip()
        cat = parts[1].lower()
        status = parts[2].lower()
        try:
            entry_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except Exception:
            continue
        if entry_date >= cutoff and cat in _BODY_QUALITY:
            q_map = _BODY_QUALITY[cat]
            quality = q_map.get(status, "neutral")
            cell_data[(entry_date, cat)] = quality

    tbl = Table(
        box=None,
        show_header=True,
        pad_edge=False,
        header_style=f"dim {PALE}",
        expand=False,
    )
    tbl.add_column("", style=f"dim {PALE}", width=9, no_wrap=True)
    for d in days_list:
        tbl.add_column(d.strftime("%a"), justify="center", width=3, no_wrap=True)

    for cat in _BODY_CATEGORIES:
        cells: list = []
        for d in days_list:
            quality = cell_data.get((d, cat))
            if quality:
                color = _QUALITY_COLOR[quality]
                cells.append(Text("██", style=color))
            else:
                cells.append(Text("··", style="dim"))
        tbl.add_row(cat, *cells)

    return tbl


# ── Widget: state distribution bars ─────────────────────────────────────────

def render_state_distribution(
    entries: list,
    days: int = 30,
    bar_width: int = 28,
) -> "rich.text.Text | None":
    """
    Horizontal proportional bar chart: one row per state tag.

    thriving  ████████████░░░░░░░░  12d  40%
    """
    try:
        from rich.text import Text
    except ImportError:
        return None

    tag_by_date = _parse_state_entries(entries, days)
    if not tag_by_date:
        return Text("no state data", style="dim")

    counts = Counter(tag_by_date.values())
    total = sum(counts.values())
    if total == 0:
        return Text("no state data", style="dim")

    text = Text()
    for tag, count in counts.most_common():
        color = _color_for_state(tag)
        pct = count / total
        filled = max(1, round(pct * bar_width))
        empty = bar_width - filled
        pct_str = f"{round(pct * 100):>3}%"
        day_str = f"{count:>2}d"
        text.append(f"  {tag:<10}", style=f"dim {PALE}")
        text.append("█" * filled, style=color)
        text.append("░" * empty, style="dim")
        text.append(f"  {day_str}  {pct_str}\n", style="dim")

    return text


# ── Composed views ───────────────────────────────────────────────────────────

def render_trend(entries: list, days: int = 90) -> "rich.text.Text | None":
    """
    Full trend view: sparkline + legend + distribution bars.
    Replaces the old row-per-state block chart.
    Returns Rich Text (renderable directly via console.print).
    """
    try:
        from rich.text import Text
    except ImportError:
        return None

    if not entries:
        return Text("no state data")

    text = Text()
    text.append(f"STATE  ·  last {days} days\n\n", style=f"bold {AMBER}")

    # Sparkline
    spark = render_state_sparkline(entries, days=min(days, 90))
    if spark:
        text.append_text(spark)
        text.append("\n\n")

    # Legend — two rows by energy level to avoid wrap
    low_tags  = [(t, l) for t, l in sorted(ENERGY_LEVEL.items(), key=lambda x: x[1]) if l <= 3]
    high_tags = [(t, l) for t, l in sorted(ENERGY_LEVEL.items(), key=lambda x: x[1]) if l > 3]
    for row in (low_tags, high_tags):
        text.append("  ")
        for tag, level in row:
            char = _SPARK[min(level, len(_SPARK) - 1)]
            text.append(f"{char} {tag}  ", style=_color_for_state(tag))
        text.append("\n")
    text.append("\n")

    # Distribution
    text.append("DISTRIBUTION\n\n", style=f"bold {AMBER}")
    dist = render_state_distribution(entries, days=days, bar_width=28)
    if dist:
        text.append_text(dist)

    return text


def render_viz(
    body_entries: list,
    state_entries: list,
    arc_history: Optional[list] = None,
) -> "rich.panel.Panel | None":
    """
    Compact dashboard panel: sparkline (14d) + body heat grid (7d) + arc frequency.
    Border color = current state's RGB.
    Returns rich.panel.Panel with box.ROUNDED.
    """
    try:
        from rich.console import Group, Console
        from rich.panel import Panel
        from rich.text import Text
        from rich import box as rich_box
    except ImportError:
        return None

    if arc_history is None:
        arc_history = []

    # Detect current state for border
    current_state = "stable"
    if state_entries:
        last = state_entries[-1]
        content = last.get("content", "") if isinstance(last, dict) else ""
        parts = content.split("|")
        if len(parts) >= 2:
            current_state = parts[1].strip().lower()

    border_color = _color_for_state(current_state)

    # Build sections as discrete renderables so Table renders natively
    # (embedding Table in Text via capture breaks column alignment)
    sections: list = []

    # STATE sparkline
    sections.append(Text(f"STATE · 14 days\n", style=f"bold {AMBER}"))
    spark = render_state_sparkline(state_entries, days=14)
    sections.append(spark if spark else Text("no state data", style="dim"))
    sections.append(Text("\n\n"))

    # BODY heat grid — Table added directly, no capture
    sections.append(Text("BODY · 7 days\n", style=f"bold {AMBER}"))
    grid = render_body_heatgrid(body_entries, days=7)
    sections.append(grid if grid else Text("no body data", style="dim"))
    sections.append(Text("\n"))

    # Arc frequency
    arc_text = Text()
    arc_text.append("\nARC frequency · 30 days\n", style=f"bold {AMBER}")
    arc_counts: Counter = Counter()
    for arc in arc_history:
        if hasattr(arc, "name"):
            arc_counts[arc.name] += 1
    if arc_counts:
        for arc_name, count in arc_counts.most_common(8):
            arc_text.append(f"  {arc_name:<28} {count}\n", style="dim")
    else:
        arc_text.append("  no arcs fired\n", style="dim")
    sections.append(arc_text)

    return Panel(
        Group(*sections),
        title=f"[bold {AMBER}]mapsOS viz[/bold {AMBER}]",
        border_style=border_color,
        box=rich_box.ROUNDED,
        expand=True,
    )


def render_trend_simple(entries: list, days: int = 90) -> str:
    """Plain text fallback for render_trend — no Rich required."""
    if not entries:
        return "no state data"

    cutoff = date.today() - timedelta(days=days)
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
            tag_by_date[entry_date] = parts[1].strip().lower()

    if not tag_by_date:
        return "no state data in range"

    # Single sparkline row
    line = ""
    cutoff_d = date.today() - timedelta(days=days)
    for i in range(days + 1):
        d = cutoff_d + timedelta(days=i)
        tag = tag_by_date.get(d)
        if tag:
            level = ENERGY_LEVEL.get(tag, 3)
            line += _SPARK[min(level, len(_SPARK) - 1)]
        else:
            line += "·"

    counts = Counter(tag_by_date.values())
    dist_lines = []
    total = sum(counts.values())
    for tag, count in counts.most_common():
        pct = round(count / total * 100)
        dist_lines.append(f"  {tag:<10} {count:>2}d  {pct:>3}%")

    return f"STATE ({days}d)\n{line}\n\n" + "\n".join(dist_lines)
