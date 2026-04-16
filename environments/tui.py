# maps · cassette.help · MIT
"""
tui.py — Rich terminal UI for mapsOS.

Launches when `maps` is run with no arguments in a TTY.
Matches the tsundoku/augury aesthetic: warm amber palette, vim keys, raw input.
"""

from __future__ import annotations

import os
import re
import sys
import time
import select
import termios
import tty
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.text import Text
    from rich.table import Table
    from rich.markup import escape
    from rich.columns import Columns
    from rich.padding import Padding
    from rich import box as _rich_box

    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    _rich_box = None


# ---------------------------------------------------------------------------
# ASCII logo
# ---------------------------------------------------------------------------

LOGO_LINES = [
    '                                      MMP"""""YMM MP""""""`MM',
    "                                      M' .mmm. `M M  mmmmm..M",
    "88d8b.d8b. .d8888b. 88d888b. .d8888b. M  MMMMM  M M.      `YM",
    "88'`88'`88 88'  `88 88'  `88 Y8ooooo. M  MMMMM  M MMMMMMM.  M",
    "88  88  88 88.  .88 88.  .88       88 M. `MMM' .M M. .MMM'  M",
    "dP  dP  dP `88888P8 88Y888P' `88888P' MMb     dMM Mb.     .dM",
    "                    88                MMMMMMMMMMM MMMMMMMMMMM",
    "                    dP",
]

TAGLINE = "qualitative life operating system"
BYLINE = "built with love by & for maps  ·  https://cassette.help"
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

# Full RGB state palette (matches viz.py STATE_RGB)
STATE_RGB: dict[str, str] = {
    "depleted":  "#7a7a7a",   # flat grey
    "grieving":  "#7b9eb5",   # muted steel blue
    "surviving": "#c47c7c",   # dull coral
    "flooded":   "#d4893a",   # deep amber-orange
    "manic":     "#b07fd4",   # violet
    "stable":    "#c0bdb4",   # warm neutral
    "grounded":  "#5fa89b",   # teal
    "tender":    "#c97a95",   # muted rose
    "thriving":  "#7ab87e",   # sage green
    "clear":     "#6abdd4",   # clear sky
}

# Backwards compat alias
STATE_COLORS = STATE_RGB

# Severity colors
ALERT_COLOR    = "#e05c5c"
INSIGHT_COLOR  = "#d4a84b"
SURVIVAL_COLOR = "#9e6ba8"

STATE_SYMBOLS = {
    "depleted": "·",
    "grieving": "~",
    "surviving": "▽",
    "flooded": "≋",
    "manic": "↑",
    "stable": "—",
    "grounded": "◇",
    "tender": "♡",
    "thriving": "✦",
    "clear": "◎",
}

INTENTION_SYMBOLS = {
    "met": ("[green]✓[/green]", "met"),
    "missed": ("[dim]·[/dim]", "missed"),
    "partial": ("[yellow]~[/yellow]", "partial"),
}

AMBER = "#f3c97a"
AMBER_DIM = "#8a6c3a"
CREAM = "#f5e8c7"
PALE = "#dbc59a"
MUTED = "#9e8c78"

# ---------------------------------------------------------------------------
# Console + terminal helpers
# ---------------------------------------------------------------------------

_console: Optional[Console] = None


def con() -> Console:
    global _console
    if _console is None:
        _console = Console(highlight=False, force_terminal=True)
    return _console


def rp(*args, **kwargs):
    if HAS_RICH:
        con().print(*args, **kwargs)
    else:
        import re

        text = str(args[0]) if args else ""
        text = re.sub(r"\[/?[^\]]+\]", "", text)
        print(text, **{k: v for k, v in kwargs.items() if k in ("end", "file")})


def _term_width() -> int:
    """Terminal width, defaulting to 80 if not detectable."""
    try:
        return os.get_terminal_size().columns
    except (OSError, AttributeError):
        return 80


def width() -> int:
    return _term_width()


def height() -> int:
    try:
        return os.get_terminal_size().lines
    except OSError:
        return 24


def clr():
    os.system("clear")


def _content_prefix() -> str:
    container_width = min(88, max(40, _term_width() - 8))
    return " " * max(0, (_term_width() - container_width) // 2)


def _content(text: str = "", end: str = "\n"):
    prefix = _content_prefix()
    if text:
        rp(f"{prefix}{text}", end=end)
    else:
        rp("", end=end)


def _status(msg: str) -> None:
    """Overwrite the current line with a status message."""
    if sys.stdout.isatty():
        plain = re.sub(r"\[/?[^\]]+\]", "", msg)
        sys.stdout.write(f"\r\033[2K{_content_prefix()}  {plain}")
        sys.stdout.flush()
    else:
        _content(msg)


def rule(title: str = "", color: str = AMBER_DIM):
    if HAS_RICH:
        con().print(Rule(title, style=color))
    else:
        print(f"── {title} " + "─" * max(0, 40 - len(title)))


def _state_color(tag: str) -> str:
    return STATE_COLORS.get(tag.lower(), AMBER)


def _state_symbol(tag: str) -> str:
    return STATE_SYMBOLS.get(tag.lower(), "·")


# ---------------------------------------------------------------------------
# Keyboard input (raw mode, same as tsundoku)
# ---------------------------------------------------------------------------


def _read_key() -> str:
    if not sys.stdin.isatty():
        line = sys.stdin.readline().strip()
        return line[:1] if line else ""

    def _read_suffix(fd: int, timeout: float = 0.10) -> str:
        suffix = ""
        deadline = time.monotonic() + timeout
        while True:
            rem = deadline - time.monotonic()
            if rem <= 0:
                break
            if not select.select([sys.stdin], [], [], rem)[0]:
                break
            chunk = os.read(fd, 16).decode(errors="ignore")
            suffix += chunk
            deadline = time.monotonic() + 0.01
        return suffix

    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            sfx = _read_suffix(fd)
            if sfx.startswith("[A") or sfx.startswith("OA"):
                return "UP"
            if sfx.startswith("[B") or sfx.startswith("OB"):
                return "DOWN"
            if sfx.startswith("[C") or sfx.startswith("OC"):
                return "RIGHT"
            if sfx.startswith("[D") or sfx.startswith("OD"):
                return "LEFT"
            return "ESC"
        if ch == "\x03":
            return "CTRL_C"
        if ch == "\x04":
            return "CTRL_D"
        if ch == "\r":
            return "ENTER"
        if ch == "\x7f":
            return "BACKSPACE"
        return ch
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


def _read_line(prompt: str = "") -> str:
    """Read a full line in cooked mode (standard input)."""
    if prompt:
        rp(prompt, end=" ")
    try:
        # Restore normal terminal for line editing
        if sys.stdin.isatty():
            fd = sys.stdin.fileno()
            old = termios.tcgetattr(fd)
            termios.tcsetattr(fd, termios.TCSADRAIN, old)
        return input().strip()
    except (KeyboardInterrupt, EOFError):
        print()
        return ""


# ---------------------------------------------------------------------------
# Data fetching
# ---------------------------------------------------------------------------


def _recall(prefix: str, limit: int = 7) -> list[dict]:
    try:
        _REPO_ROOT = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(_REPO_ROOT))
        from environments.local_store import recall_resilient

        entries, _ = recall_resilient(prefix, limit=limit)
        return entries
    except Exception:
        return []


def _extract_tag(e: dict) -> str:
    c = e.get("content", "")
    parts = [p.strip() for p in c.split("|")]
    return parts[1].lower() if len(parts) >= 2 else ""


def _extract_status(e: dict) -> str:
    return _extract_tag(e)


def _extract_note(e: dict) -> str:
    c = e.get("content", "")
    parts = [p.strip() for p in c.split("|")]
    if len(parts) >= 4:
        return parts[3]
    if len(parts) == 3:
        return parts[2]
    return ""


def _extract_category(e: dict) -> str:
    return _extract_tag(e)


def _extract_intent_name(e: dict) -> str:
    c = e.get("content", "")
    if c.startswith("INTENTION:"):
        parts = [p.strip() for p in c.replace("INTENTION:", "", 1).split("|")]
        return parts[0] if parts else ""
    return ""


def _survival_settings() -> dict:
    from environments.maps_os_config import load_config, load_survival_config

    return load_survival_config(load_config())


def _evaluate_survival(state_entries: list):
    import inspect

    from environments.survival_mode import evaluate as eval_survival

    cfg = _survival_settings()
    params = inspect.signature(eval_survival).parameters
    if {"low_states", "window", "threshold"}.issubset(params):
        return eval_survival(
            state_entries,
            low_states=cfg["low_states"],
            window=cfg["window"],
            threshold=cfg["threshold"],
        )
    return eval_survival(state_entries)


def _survival_overridden() -> bool:
    """Returns True if user dismissed survival mode within the last 24 hours."""
    from environments.arc_cooldown import load_cooldowns

    try:
        data = load_cooldowns()
        ts_str = data.get("survival_override")
        if not ts_str:
            return False
        ts = datetime.fromisoformat(ts_str)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - ts) < timedelta(hours=24)
    except Exception:
        return False


def _load_context() -> dict:
    """Pull all recent data in one pass."""
    states = _recall("STATE:", 7)
    states_long = _recall("STATE:", 30)   # for sparkline (needs 30 days)
    body = _recall("BODY:", 30)           # enough for 7-day grid with gap tolerance
    mind = _recall("MIND:", 5)
    spirit = _recall("SPIRIT:", 5)
    intentions = _recall("INTENTION:", 7)
    flash = _recall("FLASH:", 10)

    from environments.pattern_weaver import weave
    from environments.local_store import count_pending

    arcs = weave(states, body, mind, spirit, intentions, flash)
    survival = _evaluate_survival(states)
    if survival.active and _survival_overridden():
        survival.active = False
        survival.days_in_mode = 0
        survival.trigger_state = None
    pending = count_pending()

    return {
        "states": states,
        "states_long": states_long,
        "body": body,
        "mind": mind,
        "spirit": spirit,
        "intentions": intentions,
        "arcs": arcs,
        "survival": survival,
        "pending": pending,
        "current_state": _extract_tag(states[-1]) if states else "unknown",
        "today": date.today().isoformat(),
    }


# ---------------------------------------------------------------------------
# Splash + transitions
# ---------------------------------------------------------------------------


def _draw_splash(message: str = "loading"):
    """Full-screen splash with logo, byline, and status line."""
    clr()
    w, h = _term_width(), height()
    logo = LOGO_LINES if w >= 80 else ["mapsOS"]
    max_logo_w = max(len(line) for line in logo)
    logo_pad = " " * max(0, (w - max_logo_w) // 2)

    total_block = len(logo) + 6
    top_pad = max(0, (h - total_block) // 2)
    for _ in range(top_pad):
        rp("")
    for line in logo:
        rp(f"{logo_pad}[bold {AMBER}]{line}[/bold {AMBER}]")
    rp("")
    tag_pad = " " * max(0, (w - len(TAGLINE)) // 2)
    rp(f"{tag_pad}[{PALE}]{TAGLINE}[/{PALE}]")
    rp("")
    by_pad = " " * max(0, (w - len(BYLINE)) // 2)
    rp(f"{by_pad}[dim]{BYLINE}[/dim]")
    rp("")
    sp_text = f"  {message}..."
    sp_pad = " " * max(0, (w - len(sp_text)) // 2)
    sys.stdout.write(f"{sp_pad}{sp_text}")
    sys.stdout.flush()


def _animated_load(fn, message: str = "loading"):
    """
    Run fn() in a background thread while animating a spinner on the current line.
    Returns fn's return value.
    """
    import threading

    result = [None]
    exc = [None]
    done = [False]

    def worker():
        try:
            result[0] = fn()
        except Exception as err:
            exc[0] = err
        finally:
            done[0] = True

    thread = threading.Thread(target=worker, daemon=True)
    thread.start()

    w = _term_width()
    frame = 0
    while not done[0]:
        sp = SPINNER_FRAMES[frame % len(SPINNER_FRAMES)]
        line = f"  {sp}  {message}..."
        sp_pad = " " * max(0, (w - len(line)) // 2)
        sys.stdout.write(f"\r{sp_pad}{line}")
        sys.stdout.flush()
        time.sleep(0.08)
        frame += 1
    thread.join()

    sys.stdout.write(f"\r{' ' * w}\r")
    sys.stdout.flush()

    if exc[0]:
        raise exc[0]
    return result[0]


# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def _draw_banner():
    w = _term_width()
    logo = LOGO_LINES if w >= 80 else ["mapsOS"]
    color = AMBER

    # Center the block as a whole — preserve internal whitespace, shift by constant offset.
    # DO NOT strip individual lines: the leading spaces inside LOGO_LINES are structural.
    max_logo_width = max(len(line) for line in logo)
    logo_pad = " " * max(0, (w - max_logo_width) // 2)

    for line in logo:
        rp(f"{logo_pad}[bold {color}]{line}[/bold {color}]")

    rp("")
    tag_pad = " " * max(0, (w - len(TAGLINE)) // 2)
    rp(f"{tag_pad}[{PALE}]{TAGLINE}[/{PALE}]")
    rp("")


# ---------------------------------------------------------------------------
# Hotkey bar (shared by dashboard and other screens)
# ---------------------------------------------------------------------------

_HOTKEYS_ROW1 = [
    ("v", "vent"),
    ("t", "tulpa"),
    ("f", "flash"),
    ("s", "state"),
    ("b", "body"),
    ("m", "mind"),
    ("S", "spirit"),
]
_HOTKEYS_ROW2 = [
    ("i", "intention"),
    ("r", "review"),
    ("T", "trend"),
    ("V", "viz"),
    ("a", "about"),
    ("d", "docs"),
    ("y", "sync"),
    ("?", "help"),
    ("q", "quit"),
]


def _hotkey_row_str(pairs: list[tuple[str, str]]) -> tuple[str, str]:
    """Return (plain_text, rich_markup) for a row of hotkey pairs.

    The key letter is embedded at its natural position in the label:
      ("y", "sync")  → s[y]nc
      ("t", "tulpa") → [t]ulpa
      ("?", "help")  → [?]help  (key not in label — prefix fallback)
    """
    sep = "  "
    plain_parts: list[str] = []
    rich_parts: list[str] = []

    for key, label in pairs:
        idx = label.lower().find(key.lower())
        if idx >= 0:
            before, after = label[:idx], label[idx + 1:]
            plain_parts.append(f"{before}[{key}]{after}")
            rich_before = f"[dim]{before}[/dim]" if before else ""
            rich_after = f"[dim]{after}[/dim]" if after else ""
            rich_parts.append(
                f"{rich_before}[{AMBER_DIM}]\\[{key}][/{AMBER_DIM}]{rich_after}"
            )
        else:
            # Key char not in label — prefix style
            plain_parts.append(f"[{key}]{label}")
            rich_parts.append(
                f"[{AMBER_DIM}]\\[{key}][/{AMBER_DIM}][dim]{label}[/dim]"
            )

    return sep.join(plain_parts), sep.join(rich_parts)


def _draw_hotkey_bar():
    w = _term_width()
    for pairs in (_HOTKEYS_ROW1, _HOTKEYS_ROW2):
        plain, rich = _hotkey_row_str(pairs)
        pad = " " * max(0, (w - len(plain)) // 2)
        rp(f"{pad}{rich}")


def _open_docs():
    import webbrowser

    webbrowser.open("https://github.com/nosleepcassette/mapsOS")


# ---------------------------------------------------------------------------
# Dashboard panel helpers (Layout-based)
# ---------------------------------------------------------------------------


def _render_header_panel(ctx: dict, state_color: str) -> "Panel":
    """Compact header: logo text + state glyph + date."""
    state = ctx["current_state"]
    sym = _state_symbol(state)
    today = ctx["today"]
    pending = ctx["pending"]

    left = Text()
    left.append("mapsOS", style=f"bold {AMBER}")
    left.append("  ·  qualitative life OS", style=f"dim {PALE}")

    right = Text()
    right.append(f"{sym}  ", style=state_color)
    right.append(state, style=f"bold {state_color}")
    right.append(f"  ·  {today}", style=f"dim {PALE}")
    if pending > 0:
        right.append(f"  ⚡{pending}", style=f"dim {AMBER_DIM}")

    from rich.columns import Columns as _Cols
    row = _Cols([left, right])

    return Panel(
        row,
        box=_rich_box.ROUNDED if _rich_box else None,
        border_style=f"dim {state_color}",
        padding=(0, 1),
    )


def _render_trend_panel(ctx: dict, state_color: str) -> "Panel":
    """STATE sparkline panel (30 days)."""
    from environments.viz import render_state_sparkline

    entries = ctx.get("states_long", ctx["states"])
    spark = render_state_sparkline(entries, days=30)

    body = Text()
    body.append("30 days\n\n", style=f"dim {PALE}")
    if spark:
        body.append_text(spark)
        body.append("\n\n")
        # Mini legend — one line
        from environments.viz import ENERGY_LEVEL, _SPARK, _color_for_state
        for tag, level in sorted(ENERGY_LEVEL.items(), key=lambda x: x[1]):
            char = _SPARK[min(level, len(_SPARK) - 1)]
            body.append(f"{char}", style=_color_for_state(tag))
        body.append("  ", style="")
        for tag, level in sorted(ENERGY_LEVEL.items(), key=lambda x: x[1]):
            char = _SPARK[min(level, len(_SPARK) - 1)]
            body.append(f" {tag}", style=f"dim {_color_for_state(tag)}")
    else:
        body.append("no state data", style="dim")

    return Panel(
        body,
        title=f"[{AMBER_DIM}]STATE[/{AMBER_DIM}]",
        box=_rich_box.ROUNDED if _rich_box else None,
        border_style=state_color,
        padding=(0, 1),
    )


def _render_body_panel(ctx: dict, state_color: str) -> "Panel":
    """BODY heat grid panel (7 days)."""
    from environments.viz import render_body_heatgrid

    grid = render_body_heatgrid(ctx["body"], days=7)

    if grid:
        content = grid
    else:
        content = Text("no body data", style="dim")

    return Panel(
        content,
        title=f"[{AMBER_DIM}]BODY[/{AMBER_DIM}]",
        box=_rich_box.ROUNDED if _rich_box else None,
        border_style=state_color,
        padding=(0, 1),
    )


def _render_arcs_panel(ctx: dict, state_color: str) -> "Panel":
    """Arc list with severity badges."""
    arcs = ctx["arcs"]

    if not arcs:
        content = Text("all clear", style=f"dim {PALE}")
        return Panel(
            content,
            title=f"[{AMBER_DIM}]ARCS[/{AMBER_DIM}]",
            box=_rich_box.ROUNDED if _rich_box else None,
            border_style=state_color,
            padding=(0, 1),
        )

    tbl = Table(
        box=None,
        show_header=False,
        pad_edge=False,
        expand=True,
        padding=(0, 1, 0, 0),
    )
    tbl.add_column("badge", width=2, no_wrap=True)
    tbl.add_column("msg", overflow="fold")

    for arc in arcs[:8]:
        if arc.severity == "alert":
            badge = Text("●", style=ALERT_COLOR)
        elif arc.severity == "insight":
            badge = Text("◆", style=INSIGHT_COLOR)
        else:
            badge = Text("▲", style=SURVIVAL_COLOR)

        msg_text = arc.message
        msg = Text(overflow="fold")
        # Highlight [recurring × N] prefix in amber
        if msg_text.startswith("[recurring"):
            try:
                end_idx = msg_text.index("]") + 1
                msg.append(msg_text[:end_idx] + " ", style=f"bold {AMBER}")
                msg.append(msg_text[end_idx:].strip(), style=f"dim {PALE}")
            except ValueError:
                msg.append(msg_text, style=f"dim {PALE}")
        else:
            msg.append(msg_text, style=f"dim {PALE}")

        tbl.add_row(badge, msg)

    return Panel(
        tbl,
        title=f"[{AMBER_DIM}]ARCS[/{AMBER_DIM}]",
        box=_rich_box.ROUNDED if _rich_box else None,
        border_style=state_color,
        padding=(0, 1),
    )


def _render_intentions_panel(ctx: dict, state_color: str) -> "Panel":
    """Today's intentions as a horizontal strip."""
    today = ctx["today"]
    intent_today = [e for e in ctx["intentions"] if today in e.get("content", "")]

    body = Text()
    if not intent_today:
        body.append("nothing tracked today", style="dim")
    else:
        for e in intent_today[:6]:
            content = e.get("content", "")
            segs = [s.strip() for s in content.replace("INTENTION:", "", 1).split("|")]
            name = segs[0] if segs else "?"
            status = segs[1].lower() if len(segs) > 1 else "unknown"
            sym_markup, _ = INTENTION_SYMBOLS.get(status, ("[dim]?[/dim]", status))
            body.append(f"{sym_markup} ", style="")
            body.append(f"{name}  ", style=f"dim {PALE}")

    return Panel(
        body,
        title=f"[{AMBER_DIM}]INTENTIONS · today[/{AMBER_DIM}]",
        box=_rich_box.ROUNDED if _rich_box else None,
        border_style=f"dim {state_color}",
        padding=(0, 1),
    )


def _render_hotkeys_text() -> "Text":
    """Hotkey bar as plain Text (no panel border)."""
    text = Text(justify="center")
    for row_idx, pairs in enumerate((_HOTKEYS_ROW1, _HOTKEYS_ROW2)):
        for key, label in pairs:
            text.append(f"[{key}]", style=f"dim {AMBER_DIM}")
            text.append(f"{label}  ", style="dim")
        if row_idx == 0:
            text.append("\n")
    return text


def _draw_dashboard_layout(ctx: dict):
    """Layout-based dashboard using rich.layout. Falls back on import error."""
    try:
        from rich.layout import Layout
    except ImportError:
        _draw_dashboard_flat(ctx)
        return

    state = ctx["current_state"]
    state_color = STATE_RGB.get(state, AMBER)

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="content", ratio=1),
        Layout(name="intentions", size=5),
        Layout(name="hotkeys", size=2),
    )
    layout["content"].split_row(
        Layout(name="trend", ratio=2),
        Layout(name="body", ratio=2),
        Layout(name="arcs", ratio=3),
    )

    layout["header"].update(_render_header_panel(ctx, state_color))
    layout["trend"].update(_render_trend_panel(ctx, state_color))
    layout["body"].update(_render_body_panel(ctx, state_color))
    layout["arcs"].update(_render_arcs_panel(ctx, state_color))
    layout["intentions"].update(_render_intentions_panel(ctx, state_color))
    layout["hotkeys"].update(_render_hotkeys_text())

    # Render at terminal height so layout fills exactly one screen
    h = height()
    if h < 20:
        # Too small for layout — fall back
        _draw_dashboard_flat(ctx)
        return

    dash_console = Console(
        height=h,
        highlight=False,
        force_terminal=True,
    )
    clr()
    dash_console.print(layout)


def _draw_dashboard_flat(ctx: dict):
    """Original flat dashboard — fallback for small terminals or missing rich.layout."""
    today = ctx["today"]
    state = ctx["current_state"]
    color = STATE_RGB.get(state, AMBER)
    sym = _state_symbol(state)

    clr()
    _draw_banner()
    rule(f"  {today}  ")

    if ctx["states"]:
        note = _extract_note(ctx["states"][-1])
        _content(f"[{color}]{sym}  {state:<12}[/{color}]  [dim]{note[:60]}[/dim]")
    else:
        _content("[dim]no state logged  —  vent or drop a word[/dim]")

    rp("")

    today_body = [e for e in ctx["body"] if today in e.get("content", "")]
    today_mind = [e for e in ctx["mind"] if today in e.get("content", "")]
    today_spirit = [e for e in ctx["spirit"] if today in e.get("content", "")]

    def _track_row(label: str, entries: list[dict]):
        if not entries:
            _content(f"[dim]{label:<8}  (nothing today)[/dim]")
            return
        parts_out = []
        for e in entries[:3]:
            content = e.get("content", "")
            segs = [s.strip() for s in content.split("|")]
            if len(segs) >= 3:
                cat, status = segs[1], segs[2]
            else:
                cat, status = "", ""
            parts_out.append(f"[{PALE}]{cat}[/{PALE}]: [dim]{status}[/dim]")
        _content(f"[{AMBER_DIM}]{label:<8}[/{AMBER_DIM}]  " + "  ·  ".join(parts_out))

    _track_row("BODY", today_body)
    _track_row("MIND", today_mind)
    _track_row("SPIRIT", today_spirit)

    intent_today = [e for e in ctx["intentions"] if today in e.get("content", "")]
    if intent_today:
        rp("")
        rule("  intentions  ")
        for e in intent_today[:5]:
            content = e.get("content", "")
            segs = [s.strip() for s in content.replace("INTENTION:", "", 1).split("|")]
            name = segs[0] if segs else ""
            status = segs[1].lower() if len(segs) > 1 else "unknown"
            sym_markup, label = INTENTION_SYMBOLS.get(status, ("[dim]?[/dim]", status))
            _content(f"{sym_markup}  [{PALE}]{name:<14}[/{PALE}]  [dim]{label}[/dim]")

    alerts = [a for a in ctx["arcs"] if a.severity == "alert"]
    insights = [a for a in ctx["arcs"] if a.severity == "insight"]

    if alerts or insights:
        rp("")
        rule("  patterns  ")
        if alerts:
            _content(f"[bold {ALERT_COLOR}]●[/bold {ALERT_COLOR}]  {alerts[0].message}")
        elif insights:
            _content(f"[{INSIGHT_COLOR}]◆[/{INSIGHT_COLOR}]  {insights[0].message}")

    if ctx["pending"] > 0:
        rp("")
        _content(
            f"[dim]⚡ {ctx['pending']} entries pending sync  [/dim]"
            f"[{AMBER_DIM}]\\[y] sync[/{AMBER_DIM}]"
        )

    rp("")
    rule()
    _draw_hotkey_bar()
    rp("")


# ---------------------------------------------------------------------------
# Dashboard view
# ---------------------------------------------------------------------------


def _draw_dashboard(ctx: dict):
    """Route to layout dashboard, with flat fallback."""
    if HAS_RICH and _rich_box is not None:
        _draw_dashboard_layout(ctx)
    else:
        _draw_dashboard_flat(ctx)


# ---------------------------------------------------------------------------
# Survival mode view
# ---------------------------------------------------------------------------


def _draw_survival(ctx: dict):
    clr()
    sv = ctx["survival"]
    days_str = f"day {sv.days_in_mode}" if sv.days_in_mode > 1 else ""

    body = Text(justify="center")
    body.append("\n")
    body.append("·  s u r v i v a l  ·", style=f"bold {SURVIVAL_COLOR}")
    if days_str:
        body.append(f"  {days_str}", style="dim")
    body.append("\n\n")

    items = ["eat something real", "drink water", "sleep when you can"]
    for item in items:
        body.append(f"→  {item}\n", style=f"{AMBER}")

    body.append("\n")
    body.append("that's the whole job.", style="dim")
    body.append("  everything else can wait.", style="dim")
    body.append("\n")

    # Use Panel if rich.box available, else flat
    if HAS_RICH and _rich_box is not None:
        panel = Panel(
            body,
            box=_rich_box.ROUNDED,
            border_style=SURVIVAL_COLOR,
            padding=(1, 4),
        )
        clr()
        w = _term_width()
        # Center vertically
        h = height()
        pad_rows = max(0, (h - 12) // 2)
        for _ in range(pad_rows):
            rp("")
        con().print(panel)
    else:
        # Flat fallback
        w = _term_width()
        rp("")
        rp("")
        title = "·  s u r v i v a l  ·"
        pad = " " * max(0, (w - len(title)) // 2)
        rp(f"{pad}[{SURVIVAL_COLOR}]{title}[/{SURVIVAL_COLOR}]")
        rp("")
        rule()
        rp("")
        for item in items:
            item_pad = " " * max(0, (w - len(item) - 6) // 2)
            rp(f"{item_pad}[{AMBER}]→[/{AMBER}]  [{CREAM}]{item}[/{CREAM}]")
        rp("")
        rule()
        rp("")
        msg = "that's the whole job.  everything else can wait."
        rp(f"{' ' * max(0, (w - len(msg)) // 2)}[dim]{msg}[/dim]")
        rp("")
        rp("")

    _content(
        f"[{AMBER_DIM}]\\[l][/{AMBER_DIM}] log state  "
        f"[{AMBER_DIM}]\\[v][/{AMBER_DIM}] vent  "
        f"[{AMBER_DIM}]\\[i][/{AMBER_DIM}] ignore today  "
        f"[{AMBER_DIM}]\\[q][/{AMBER_DIM}] quit"
    )
    rp("")


def _survival_ignore():
    """Write a 24-hour survival mode override to the cooldown file."""
    from environments.arc_cooldown import load_cooldowns, save_cooldowns

    data = load_cooldowns()
    data["survival_override"] = datetime.now(timezone.utc).isoformat()
    save_cooldowns(data)

    rp("")
    _content("[dim]noted. full mode active for today. check in tomorrow.[/dim]")
    rp("")
    _pause(1.2)


# ---------------------------------------------------------------------------
# Input screens
# ---------------------------------------------------------------------------


def _screen_vent(ctx: dict) -> bool:
    """Full-screen vent input. Returns True if something was logged."""
    clr()
    _draw_banner()
    rule("  vent  ")
    rp("")
    _content(f"[{PALE}]just type. parsing happens after.[/{PALE}]")
    _content("[dim]empty line to cancel[/dim]")
    rp("")
    _content(f"[bold {AMBER}]>[/bold {AMBER}] ", end="")

    text = _read_line()
    if not text:
        return False

    rp("")
    rule()
    _status("[dim]parsing...[/dim]")

    from environments.vent_parser import parse_vent, format_garden_commands
    from environments.local_store import remember as resilient_remember
    from environments.survival_mode import (
        evaluate as eval_survival,
        filter_entries_for_survival,
    )

    entries = parse_vent(text, log_date=ctx["today"])

    survival = ctx["survival"]
    if survival.active:
        entries = filter_entries_for_survival(entries)

    rp("")
    logged = []
    for e in entries:
        content = e.to_garden()
        _, dest = resilient_remember(content)
        color = _state_color(e.category or "stable") if e.track == "STATE" else PALE
        dest_note = " [dim](local)[/dim]" if dest == "local" else ""
        _content(
            f"[{color}]{e.track}[/{color}]  [dim]{e.category} | {e.status or ''} | {(e.note or '')[:40]}[/dim]{dest_note}"
        )
        logged.append(e)

    if not logged:
        _content("[dim](nothing parsed)[/dim]")
        rp("")
        _pause()
        return False

    # Quick pattern check after vent
    rp("")
    from environments.pattern_weaver import weave

    new_states = _recall("STATE:", 7)
    new_body = _recall("BODY:", 7)
    new_mind = _recall("MIND:", 7)
    new_spirit = _recall("SPIRIT:", 7)
    new_intentions = _recall("INTENTION:", 14)
    arcs = weave(new_states, new_body, new_mind, new_spirit, new_intentions)
    alerts = [a for a in arcs if a.severity == "alert"]

    if alerts:
        rp("")
        rule()
        _content(
            f"[bold {STATE_COLORS['manic']}]→[/bold {STATE_COLORS['manic']}]  {alerts[0].message}"
        )

    rp("")
    _pause()
    return True


def _screen_flash(ctx: dict) -> bool:
    """Inline flash capture."""
    clr()
    _draw_banner()
    rule("  flash  ")
    rp("")
    _content(f"[{PALE}]just a word or phrase. no structure needed.[/{PALE}]")
    rp("")
    _content(f"[bold {AMBER}]·[/bold {AMBER}] ", end="")

    text = _read_line()
    if not text:
        return False

    content = f"FLASH: {ctx['today']} | {text.strip()}"
    from environments.local_store import remember as resilient_remember

    _, dest = resilient_remember(content)
    dest_note = " (saved locally)" if dest == "local" else ""
    rp("")
    _content(f"[{PALE}]· {text.strip()}[/{PALE}]  [dim]captured{dest_note}[/dim]")
    rp("")
    _pause(0.8)
    return True


def _screen_state(ctx: dict) -> bool:
    """Select a STATE tag."""
    from environments.vent_parser import VALID_STATE_TAGS

    clr()
    _draw_banner()
    rule("  state  ")
    rp("")

    tags = sorted(VALID_STATE_TAGS)
    for i, tag in enumerate(tags, 1):
        c = _state_color(tag)
        sym = _state_symbol(tag)
        rp(f"  [{AMBER_DIM}]{i}[/{AMBER_DIM}]  [{c}]{sym}  {tag}[/{c}]")

    rp("")
    rp(f"  [dim]enter number, or first letters  ·  empty to cancel[/dim]")
    rp("")
    rp(f"  [bold {AMBER}]>[/bold {AMBER}] ", end="")

    choice = _read_line()
    if not choice:
        return False

    tag = None
    if choice.isdigit():
        idx = int(choice) - 1
        if 0 <= idx < len(tags):
            tag = tags[idx]
    else:
        matches = [t for t in tags if t.startswith(choice.lower())]
        if len(matches) == 1:
            tag = matches[0]
        elif matches:
            rp(f"  [dim]ambiguous: {', '.join(matches)}[/dim]")

    if not tag:
        rp(f"  [dim]unrecognized[/dim]")
        _pause(0.6)
        return False

    rp("")
    rp(f"  [{PALE}]narrative / context  [dim](optional, enter to skip)[/dim][/{PALE}]")
    rp(
        f"  [{_state_color(tag)}]{_state_symbol(tag)}  {tag}[/{_state_color(tag)}]  ",
        end="",
    )
    narrative = _read_line()

    content = f"STATE: {ctx['today']} | {tag} | {narrative}"
    from environments.local_store import remember as resilient_remember

    _, dest = resilient_remember(content)
    dest_note = " (local)" if dest == "local" else ""
    rp(
        f"  [{_state_color(tag)}]{_state_symbol(tag)}  {tag}[/{_state_color(tag)}]  [dim]logged{dest_note}[/dim]"
    )
    rp("")
    _pause(0.6)
    return True


def _screen_body(ctx: dict) -> bool:
    categories = ["sleep", "pain", "hunger", "movement", "substances", "energy"]
    return _screen_generic_track("BODY", "body", categories, ctx)


def _screen_mind(ctx: dict) -> bool:
    categories = ["focus", "clarity", "overwhelm", "flow"]
    return _screen_generic_track("MIND", "mind", categories, ctx)


def _screen_spirit(ctx: dict) -> bool:
    categories = ["connection", "creativity", "purpose", "isolation"]
    return _screen_generic_track("SPIRIT", "spirit", categories, ctx)


def _screen_generic_track(
    track: str, title: str, categories: list[str], ctx: dict
) -> bool:
    clr()
    _draw_banner()
    rule(f"  {title}  ")
    rp("")

    for i, cat in enumerate(categories, 1):
        _content(f"[{AMBER_DIM}]{i}[/{AMBER_DIM}]  [{PALE}]{cat}[/{PALE}]")

    rp("")
    _content("[dim]category:[/dim] ", end="")
    cat_choice = _read_line()
    if not cat_choice:
        return False

    category = None
    if cat_choice.isdigit():
        idx = int(cat_choice) - 1
        if 0 <= idx < len(categories):
            category = categories[idx]
    else:
        matches = [c for c in categories if c.startswith(cat_choice.lower())]
        if len(matches) == 1:
            category = matches[0]

    if not category:
        return False

    _content(
        "[dim]status  (e.g. none, poor, low, present, high, scattered):[/dim] ",
        end="",
    )
    status = _read_line()
    if not status:
        return False

    _content("[dim]note  (optional):[/dim] ", end="")
    note = _read_line()

    content = f"{track}: {ctx['today']} | {category} | {status} | {note}"
    from environments.local_store import remember as resilient_remember

    _, dest = resilient_remember(content)
    dest_note = " (local)" if dest == "local" else ""
    rp("")
    _content(
        f"[{PALE}]{track}: {category} | {status}[/{PALE}]  [dim]logged{dest_note}[/dim]"
    )
    rp("")
    _pause(0.6)
    return True


def _screen_intention(ctx: dict) -> bool:
    clr()
    _draw_banner()
    rule("  intention  ")
    rp("")
    _content(f"[{PALE}]what intention?[/{PALE}] ", end="")
    name = _read_line()
    if not name:
        return False

    rp("")
    _content(f"[{AMBER_DIM}]1[/{AMBER_DIM}]  [green]✓  met[/green]")
    _content(f"[{AMBER_DIM}]2[/{AMBER_DIM}]  [yellow]~  partial[/yellow]")
    _content(f"[{AMBER_DIM}]3[/{AMBER_DIM}]  [dim]·  missed[/dim]")
    rp("")
    _content("[dim]status:[/dim] ", end="")
    s = _read_line()

    status_map = {
        "1": "met",
        "2": "partial",
        "3": "missed",
        "m": "met",
        "p": "partial",
        "miss": "missed",
        "met": "met",
        "partial": "partial",
        "missed": "missed",
    }
    status = status_map.get(s.lower(), "")
    if not status:
        return False

    _content("[dim]note  (optional):[/dim] ", end="")
    note = _read_line()

    content = f"INTENTION: {name.lower()} | {status} | {ctx['today']} | {note}"
    from environments.local_store import remember as resilient_remember

    _, dest = resilient_remember(content)
    sym_markup, _ = INTENTION_SYMBOLS.get(status, ("[dim]?[/dim]", ""))
    dest_note = " (local)" if dest == "local" else ""
    rp("")
    _content(
        f"{sym_markup}  [{PALE}]{name}  {status}[/{PALE}]  [dim]logged{dest_note}[/dim]"
    )
    rp("")
    _pause(0.6)
    return True


# ---------------------------------------------------------------------------
# Paged list helper
# ---------------------------------------------------------------------------


def _page_size() -> int:
    return max(8, height() - 12)

_PAGE_BREAK = "__PAGE_BREAK__"


def _paged_screen(
    title: str,
    lines: list[str],
    actions: dict[str, Callable[[], None]] | None = None,
    footer_note: str = "",
):
    if not lines:
        return

    page_size = _page_size()
    pages: list[list[str]] = []
    current: list[str] = []
    for line in lines:
        if line == _PAGE_BREAK:
            if current:
                pages.append(current)
                current = []
            continue
        current.append(line)
        if len(current) >= page_size:
            pages.append(current)
            current = []
    if current:
        pages.append(current)
    if not pages:
        return

    page = 0
    total_pages = len(pages)
    while True:
        clr()
        _draw_banner()
        rule(title)
        rp("")

        for line in pages[page]:
            _content(line)

        rp("")
        rule()
        footer = f"page {page + 1}/{total_pages}"
        if total_pages > 1:
            footer += "  ·  j next · k prev"
        if footer_note:
            footer += f"  ·  {footer_note}"
        footer += "  ·  ↩ back"
        _content(f"[dim]{footer}[/dim]")
        key = _read_key()
        if actions and key in actions:
            actions[key]()
            continue
        if key == "j" and page < total_pages - 1:
            page += 1
            continue
        if key == "k" and page > 0:
            page -= 1
            continue
        break


# ---------------------------------------------------------------------------
# Review screen
# ---------------------------------------------------------------------------


def _screen_review(ctx: dict):
    _draw_splash("loading review")
    states = _recall("STATE:", 14)
    body = _recall("BODY:", 14)
    spirit = _recall("SPIRIT:", 14)
    intentions = _recall("INTENTION:", 14)
    wins = _recall("WIN:", 14)

    clr()
    _draw_banner()
    rule("  cycle review  ")
    rp("")

    if not states:
        _content("[dim]no state data to review[/dim]")
        rp("")
        _pause()
        return

    tags = [_extract_tag(e) for e in states]
    first, last = tags[0], tags[-1]

    from collections import Counter

    dominant = Counter(tags).most_common(1)[0][0]
    dominant_color = _state_color(dominant)

    met = sum(1 for e in intentions if "| met |" in e.get("content", ""))
    missed = sum(1 for e in intentions if "| missed |" in e.get("content", ""))
    lines = [
        (
            f"[{_state_color(first)}]{_state_symbol(first)}  {first}[/{_state_color(first)}]"
            f"  [dim]→[/dim]  "
            f"[{_state_color(last)}]{_state_symbol(last)}  {last}[/{_state_color(last)}]"
        ),
        "",
        f"[{AMBER_DIM}]what held[/{AMBER_DIM}]",
        f"[{dominant_color}]{dominant}[/{dominant_color}] was the dominant state",
    ]
    if met or missed:
        lines.append(f"[green]✓ {met} met[/green]  [dim]· {missed} missed[/dim]")
    lines.extend(["", f"[{AMBER_DIM}]what dropped[/{AMBER_DIM}]"])

    all_entries = body + spirit
    absent = [
        t
        for t in ("connection", "movement", "sleep")
        if not any(t in e.get("content", "").lower() for e in all_entries)
    ]
    if absent:
        for item in absent:
            lines.append(f"[dim]→ {item} mostly absent[/dim]")
    else:
        lines.append("[dim]→ no major absences detected[/dim]")

    # Pull arcs from context
    from environments.pattern_weaver import weave

    mind = _recall("MIND:", 14)
    arcs = weave(states, body, mind, spirit, intentions)
    insights = [a for a in arcs if a.severity == "insight"]
    if insights:
        lines.extend(
            [
                "",
                f"[{AMBER_DIM}]pattern[/{AMBER_DIM}]",
                f"[{AMBER}]→[/{AMBER}]  {insights[0].message}",
            ]
        )

    if wins:
        lines.extend(["", f"[{AMBER_DIM}]wins[/{AMBER_DIM}]"])
        for entry in wins[:5]:
            note = entry.get("content", "").split("|", 1)[1].strip() if "|" in entry.get("content", "") else entry.get("content", "")
            lines.append(f"[dim]•[/dim] {note}")

    _paged_screen("  cycle review  ", lines)


# ---------------------------------------------------------------------------
# Help screen
# ---------------------------------------------------------------------------


def _screen_help():
    keys = [
        ("\\[v]ent", "free-form text → auto-parsed into STATE/BODY/MIND/SPIRIT"),
        ("\\[f]lash", "sub-threshold phrase capture — just a word, no structure"),
        ("\\[s]tate", "log a STATE tag directly"),
        ("\\[b]ody", "log BODY entry (sleep / pain / hunger / movement / ...)"),
        ("\\[m]ind", "log MIND entry (focus / clarity / overwhelm / flow)"),
        (
            "\\[S]pirit",
            "log SPIRIT entry (connection / creativity / purpose / isolation)",
        ),
        ("\\[i]ntention", "log INTENTION: met / missed / partial"),
        ("\\[r]eview", "cycle review — last 14 days, what held / dropped"),
        ("\\[c]heck", "refresh patterns and arcs"),
        ("\\[y]sync", "flush deferred local entries when available"),
        ("\\[t]ulpa", "multi-line stream capture — dump until /done or blank line"),
        ("\\[T]rend", "show state trend chart"),
        ("\\[V]iz", "show viz dashboard"),
        ("\\[a]bout", "about mapsOS"),
        ("\\[d]ocs", "open GitHub / docs in browser"),
        ("\\[?] / \\[h]", "this screen"),
        ("\\[q]uit", "exit"),
    ]

    lines = [f"[bold {AMBER}]{key:<16}[/bold {AMBER}]  [dim]{desc}[/dim]" for key, desc in keys]
    lines.extend(["", f"[{PALE}]STATE tags:[/{PALE}]", ""])
    for tag in sorted(STATE_SYMBOLS):
        c = _state_color(tag)
        sym = _state_symbol(tag)
        lines.append(f"  [{c}]{sym}  {tag}[/{c}]")
    lines.extend(
        [
            _PAGE_BREAK,
            "",
            "─" * 40,
            "",
            f"[bold {AMBER}]about[/bold {AMBER}]",
            "",
            f"[{PALE}]Most life-tracking tools are built around numbers.[/{PALE}]",
            f"[{PALE}]Mood scores out of ten. Sleep quality percentages.[/{PALE}]",
            f"[{PALE}]Streak counters. Completion rates.[/{PALE}]",
            "",
            f"[dim]That assumption doesn't hold for a lot of people.[/dim]",
            "",
            f"[{PALE}]mapsOS tracks narrative states, surfaces patterns across[/{PALE}]",
            f"[{PALE}]days and weeks, and knows when to drop everything non-essential.[/{PALE}]",
            "",
            f"[dim]Not a mood tracker. Not a habit app. No scores out of ten.[/dim]",
            "",
            f"[bold {AMBER}]docs[/bold {AMBER}]",
            "",
            f"[{AMBER_DIM}]→[/{AMBER_DIM}]  [{PALE}]github.com/nosleepcassette/mapsOS[/{PALE}]",
            f"[{AMBER_DIM}]→[/{AMBER_DIM}]  [dim]README  ·  WALKTHROUGH  ·  SKILL.md[/dim]",
            "",
            f"[{AMBER_DIM}]\\[d][/{AMBER_DIM}] open docs in browser",
            "",
            f"[dim]maps · cassette.help · MIT[/dim]",
        ]
    )

    _paged_screen("  keys  ", lines, actions={"d": _open_docs}, footer_note="d docs")


def _screen_about():
    lines = [
        f"[bold {AMBER}]mapsOS[/bold {AMBER}]  [{PALE}]qualitative life OS[/{PALE}]",
        "",
        f"[{PALE}]Most life-tracking tools are built around numbers.[/{PALE}]",
        f"[{PALE}]Mood scores out of ten. Sleep quality percentages.[/{PALE}]",
        f"[{PALE}]Streak counters. Completion rates.[/{PALE}]",
        "",
        f"[dim]That assumption doesn't hold for a lot of people.[/dim]",
        f"[dim]It especially doesn't hold when the thing you're trying to track[/dim]",
        f"[dim]is how you actually feel — not a proxy metric for it.[/dim]",
        "",
        f"[{PALE}]mapsOS tracks narrative states, surfaces patterns across days[/{PALE}]",
        f"[{PALE}]and weeks, and knows when to drop everything non-essential.[/{PALE}]",
        "",
        f"[dim]Numeric mood scores became qualitative state tags.[/dim]",
        f"[dim]Nine siloed health dimensions collapsed into three tracks.[/dim]",
        f"[dim]Fixed-schedule briefings got replaced with session-triggered logic.[/dim]",
        f"[dim]Streak tracking was removed entirely.[/dim]",
        "",
        f"[{PALE}]The result is a system that meets you where you are.[/{PALE}]",
        f"[{PALE}]It doesn't ask you to score your mood.[/{PALE}]",
        f"[{PALE}]It asks you to say what's happening, and it listens.[/{PALE}]",
        "",
        f"[{AMBER_DIM}]──[/{AMBER_DIM}]",
        "",
        f"[dim]Built by maps · cassette.help · MIT[/dim]",
        f"[dim]github.com/nosleepcassette/mapsOS[/dim]",
        "",
        f"[{AMBER_DIM}]\\[d][/{AMBER_DIM}] open docs in browser",
    ]
    _paged_screen("  about  ", lines, actions={"d": _open_docs}, footer_note="d docs")


# ---------------------------------------------------------------------------
# Sync screen
# ---------------------------------------------------------------------------


def _screen_sync(ctx: dict):
    from environments.local_store import sync_to_garden, count_pending, garden_available

    n = count_pending()
    if n == 0:
        rp("")
        _content("[dim]local store clean — nothing to sync[/dim]")
        rp("")
        _pause(0.8)
        return

    if not garden_available():
        rp("")
        _content(
            f"[{STATE_COLORS['depleted']}]remote backend unavailable — {n} entries waiting[/{STATE_COLORS['depleted']}]"
        )
        rp("")
        _pause(1.0)
        return

    _status(f"[{AMBER}]flushing 0/{n}...[/]")
    result = sync_to_garden()
    _status(f"[{AMBER}]flushing {result.get('synced', 0)}/{n}...[/]")
    rp("")
    if result.get("error"):
        _content(f"[dim]error: {result['error']}[/dim]")
    else:
        _content(f"[green]✓ flushed {result['synced']}[/green]", end="")
        if result["failed"]:
            rp(f"  [dim]{result['failed']} failed[/dim]")
        else:
            rp("")
    rp("")
    _pause(0.8)


def _screen_tulpa(ctx: dict) -> bool:
    """Multi-line tulpa stream capture. Collects lines until /done or blank after content."""
    clr()
    _draw_banner()
    rule("  tulpa  ")
    rp("")
    _content(f"[{PALE}]stream mode. holding, not processing.[/{PALE}]")
    _content("[dim]type /done or leave a blank line when you're finished[/dim]")
    rp("")

    lines: list[str] = []
    while True:
        prompt_sym = ">" if not lines else str(len(lines) + 1)
        _content(f"[bold {AMBER}]{prompt_sym}[/bold {AMBER}] ", end="")
        line = _read_line()
        if line in ("/done", "/d"):
            break
        if not line:
            if lines:
                break
            return False  # cancelled before anything typed
        lines.append(line)

    if not lines:
        return False

    text = "\n".join(lines)

    rp("")
    rule()
    _status(f"[dim]parsing stream ({len(lines)} line{'s' if len(lines) != 1 else ''})...[/dim]")

    from environments.vent_parser import parse_vent
    from environments.local_store import remember as resilient_remember
    from environments.survival_mode import filter_entries_for_survival

    entries = parse_vent(text, log_date=ctx["today"])

    survival = ctx["survival"]
    if survival.active:
        entries = filter_entries_for_survival(entries)

    rp("")
    logged = []
    for e in entries:
        content = e.to_garden()
        _, dest = resilient_remember(content)
        color = _state_color(e.category or "stable") if e.track == "STATE" else PALE
        dest_note = " [dim](local)[/dim]" if dest == "local" else ""
        _content(
            f"[{color}]{e.track}[/{color}]  [dim]{e.category} | {e.status or ''} | {(e.note or '')[:40]}[/dim]{dest_note}"
        )
        logged.append(e)

    if not logged:
        _content("[dim](nothing parsed)[/dim]")
        rp("")
        _pause()
        return False

    from environments.pattern_weaver import weave

    new_states = _recall("STATE:", 7)
    new_body = _recall("BODY:", 7)
    new_mind = _recall("MIND:", 7)
    new_spirit = _recall("SPIRIT:", 7)
    new_intentions = _recall("INTENTION:", 14)
    arcs = weave(new_states, new_body, new_mind, new_spirit, new_intentions)
    alerts = [a for a in arcs if a.severity == "alert"]

    if alerts:
        rp("")
        rule()
        _content(f"[bold {STATE_COLORS['manic']}]→[/bold {STATE_COLORS['manic']}]  {alerts[0].message}")

    rp("")
    _pause()
    return True


def _screen_trend(ctx: dict):
    from environments.viz import render_trend, render_state_distribution
    from environments.local_store import recall_resilient

    _draw_splash("loading trend")
    entries, _ = recall_resilient("STATE:", limit=200)
    clr()
    if not entries:
        rp("")
        _content("[dim]no state data[/dim]")
        rp("")
        _pause(0.8)
        return

    clr()
    try:
        result = render_trend(entries, days=90)
        if result:
            rp("")
            con().print(result)
            rp("")
    except Exception as e:
        _content(f"[dim]trend unavailable: {e}[/dim]")
    _pause(0)


def _screen_viz(ctx: dict):
    from environments.viz import render_viz
    from environments.local_store import recall_resilient
    from environments.arc_cooldown import load_history

    _draw_splash("loading viz")
    body, _ = recall_resilient("BODY:", limit=30)
    state, _ = recall_resilient("STATE:", limit=30)

    # Build arc_history as list of Arc-like objects from arc history file
    try:
        history = load_history()
        from environments.pattern_weaver import Arc
        arc_history = [
            Arc(name=name, severity="insight", message=name)
            for name in history.keys()
            if history[name]  # has at least one fire date
        ]
    except Exception:
        arc_history = []

    try:
        result = render_viz(body, state, arc_history=arc_history)
        if result:
            clr()
            _viz_con = Console(highlight=False, force_terminal=True, width=width())
            _viz_con.print(result)
            rp("")
    except Exception as e:
        _content(f"[dim]viz unavailable: {e}[/dim]")
    _pause(0)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _pause(seconds: float = 0):
    if seconds > 0:
        time.sleep(seconds)
    else:
        _content("[dim]↩  continue[/dim]", end="")
        _read_key()


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------


def run():
    """Main entry point for the TUI."""
    if not HAS_RICH:
        print("mapsOS TUI requires Rich: pip install rich")
        sys.exit(1)

    if not sys.stdin.isatty():
        # Not a TTY — fall through to CLI
        return False

    try:
        _run_loop()
    except KeyboardInterrupt:
        print()
    return True


def _run_loop():
    _draw_splash("loading")
    ctx = _animated_load(_load_context, "loading")

    while True:
        # Choose view
        if ctx["survival"].active:
            _draw_survival(ctx)
        else:
            _draw_dashboard(ctx)

        key = _read_key()
        refresh = False
        refresh_message = "loading"

        if key in ("q", "CTRL_C", "CTRL_D"):
            clr()
            break

        elif key == "v":
            refresh = _screen_vent(ctx)

        elif key == "f":
            refresh = _screen_flash(ctx)

        elif key == "s":
            refresh = _screen_state(ctx)

        elif key == "b":
            refresh = _screen_body(ctx)

        elif key == "m":
            refresh = _screen_mind(ctx)

        elif key == "S":
            refresh = _screen_spirit(ctx)

        elif key == "i" and ctx["survival"].active:
            _survival_ignore()
            refresh = True

        elif key == "i":
            refresh = _screen_intention(ctx)

        elif key == "r":
            _screen_review(ctx)

        elif key == "a":
            _screen_about()

        elif key == "d":
            _open_docs()

        elif key in ("?", "h"):
            _screen_help()

        elif key == "y":
            _screen_sync(ctx)
            refresh = True

        elif key == "t":
            refresh = _screen_tulpa(ctx)

        elif key == "T":
            _screen_trend(ctx)
            refresh = True

        elif key == "V":
            _screen_viz(ctx)
            refresh = True

        elif key == "c":
            refresh = True
            refresh_message = "checking patterns"

        elif key == "l" and ctx["survival"].active:
            refresh = _screen_state(ctx)

        if refresh:
            if refresh_message == "checking patterns":
                _draw_splash(refresh_message)
                ctx = _animated_load(_load_context, refresh_message)
            else:
                ctx = _load_context()
