# maps · cassette.help · MIT
"""
tui.py — Rich terminal UI for maps-os.

Launches when `maps` is run with no arguments in a TTY.
Matches the tsundoku/augury aesthetic: warm amber palette, vim keys, raw input.
"""
from __future__ import annotations

import os
import sys
import time
import select
import termios
import tty
from datetime import date
from pathlib import Path
from typing import Optional

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.rule import Rule
    from rich.text import Text
    from rich.table import Table
    from rich.markup import escape
    from rich.columns import Columns
    from rich.padding import Padding
    HAS_RICH = True
except ImportError:
    HAS_RICH = False


# ---------------------------------------------------------------------------
# ASCII logo
# ---------------------------------------------------------------------------

LOGO_LINES = [
    "                                      MMP\"\"\"\"\"YMM MP\"\"\"\"\"\"`MM",
    "                                      M' .mmm. `M M  mmmmm..M",
    "88d8b.d8b. .d8888b. 88d888b. .d8888b. M  MMMMM  M M.      `YM",
    "88'`88'`88 88'  `88 88'  `88 Y8ooooo. M  MMMMM  M MMMMMMM.  M",
    "88  88  88 88.  .88 88.  .88       88 M. `MMM' .M M. .MMM'  M",
    "dP  dP  dP `88888P8 88Y888P' `88888P' MMb     dMM Mb.     .dM",
    "                    88                MMMMMMMMMMM MMMMMMMMMMM",
    "                    dP",
]

TAGLINE = "qualitative life operating system"

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------

# STATE tag → Rich color
STATE_COLORS = {
    "depleted":  "#9e9e9e",    # worn grey
    "grieving":  "#90a4ae",    # muted blue-grey
    "surviving": "#ef9a9a",    # pale red
    "flooded":   "#ffb74d",    # amber-orange
    "manic":     "#ce93d8",    # soft violet
    "stable":    "#e0e0e0",    # near-white neutral
    "thriving":  "#a5d6a7",    # soft green
    "clear":     "#80deea",    # clear cyan
}

STATE_SYMBOLS = {
    "depleted":  "·",
    "grieving":  "~",
    "surviving": "▽",
    "flooded":   "≋",
    "manic":     "↑",
    "stable":    "—",
    "thriving":  "✦",
    "clear":     "◎",
}

INTENTION_SYMBOLS = {
    "met":     ("[green]✓[/green]", "met"),
    "missed":  ("[dim]·[/dim]",    "missed"),
    "partial": ("[yellow]~[/yellow]", "partial"),
}

AMBER     = "#f3c97a"
AMBER_DIM = "#8a6c3a"
CREAM     = "#f5e8c7"
PALE      = "#dbc59a"
MUTED     = "#9e8c78"

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
        text = re.sub(r'\[/?[^\]]+\]', '', text)
        print(text, **{k: v for k, v in kwargs.items() if k in ("end", "file")})


def width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def height() -> int:
    try:
        return os.get_terminal_size().lines
    except OSError:
        return 24


def clr():
    os.system("clear")


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
            if sfx.startswith("[A") or sfx.startswith("OA"): return "UP"
            if sfx.startswith("[B") or sfx.startswith("OB"): return "DOWN"
            if sfx.startswith("[C") or sfx.startswith("OC"): return "RIGHT"
            if sfx.startswith("[D") or sfx.startswith("OD"): return "LEFT"
            return "ESC"
        if ch == "\x03": return "CTRL_C"
        if ch == "\x04": return "CTRL_D"
        if ch == "\r":   return "ENTER"
        if ch == "\x7f": return "BACKSPACE"
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


def _load_context() -> dict:
    """Pull all recent data in one pass."""
    states     = _recall("STATE:",     7)
    body       = _recall("BODY:",      5)
    mind       = _recall("MIND:",      5)
    spirit     = _recall("SPIRIT:",    5)
    intentions = _recall("INTENTION:", 7)
    flash      = _recall("FLASH:",     10)

    from environments.pattern_weaver import weave, check_survival_trigger
    from environments.survival_mode import evaluate as eval_survival
    from environments.local_store import count_pending

    arcs = weave(states, body, mind, spirit, intentions, flash)
    survival = eval_survival(states)
    pending = count_pending()

    return {
        "states": states,
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
# Banner
# ---------------------------------------------------------------------------

def _draw_banner():
    w = width()
    logo = LOGO_LINES if w >= 64 else ["  maps · os"]
    color = AMBER

    # Center the whole block as a unit — not each line independently.
    # Per-line centering makes the short trailing lines (like "dP") drift
    # to the wrong column.
    max_logo_w = max(len(line) for line in logo)
    left_pad = max(0, (w - max_logo_w) // 2)

    for line in logo:
        rp(f"{' ' * left_pad}[bold {color}]{line}[/bold {color}]")

    rp("")
    tag_pad = max(0, (w - len(TAGLINE)) // 2)
    rp(f"{' ' * tag_pad}[{PALE}]{TAGLINE}[/{PALE}]")
    rp("")


# ---------------------------------------------------------------------------
# Dashboard view
# ---------------------------------------------------------------------------

def _draw_dashboard(ctx: dict):
    clr()
    _draw_banner()

    today = ctx["today"]
    state = ctx["current_state"]
    color = _state_color(state)
    sym   = _state_symbol(state)

    # ── today ──────────────────────────────────────────────────────────────
    rule(f"  {today}  ")

    # STATE row
    if ctx["states"]:
        note = _extract_note(ctx["states"][-1])
        rp(f"  [{color}]{sym}  {state:<12}[/{color}]  [dim]{note[:60]}[/dim]")
    else:
        rp(f"  [dim]no state logged  —  vent or drop a word[/dim]")

    rp("")

    # BODY / MIND / SPIRIT compact row
    body_today   = [e for e in ctx["body"]   if today in e.get("content", "")]
    mind_today   = [e for e in ctx["mind"]   if today in e.get("content", "")]
    spirit_today = [e for e in ctx["spirit"] if today in e.get("content", "")]

    def _track_row(label: str, entries: list[dict]):
        if not entries:
            rp(f"  [dim]{label:<8}  (nothing today)[/dim]")
            return
        parts = []
        for e in entries[:3]:
            cat    = _extract_category(e)
            status = _extract_tag(e) if label == "BODY" else _extract_status(e)
            # For BODY: content is "BODY: date | category | status | note"
            content = e.get("content", "")
            segs = [s.strip() for s in content.split("|")]
            if len(segs) >= 3:
                cat    = segs[1]
                status = segs[2]
            parts.append(f"[{PALE}]{cat}[/{PALE}]: [dim]{status}[/dim]")
        rp(f"  [{AMBER_DIM}]{label:<8}[/{AMBER_DIM}]  " + "  ·  ".join(parts))

    _track_row("BODY",   body_today)
    _track_row("MIND",   mind_today)
    _track_row("SPIRIT", spirit_today)

    # ── intentions ─────────────────────────────────────────────────────────
    intent_today = [e for e in ctx["intentions"] if today in e.get("content", "")]
    if intent_today:
        rp("")
        rule("  intentions  ")
        for e in intent_today[:5]:
            content = e.get("content", "")
            segs    = [s.strip() for s in content.replace("INTENTION:", "", 1).split("|")]
            name    = segs[0] if segs else ""
            status  = segs[1].lower() if len(segs) > 1 else "unknown"
            sym_markup, label = INTENTION_SYMBOLS.get(status, ("[dim]?[/dim]", status))
            rp(f"  {sym_markup}  [{PALE}]{name:<14}[/{PALE}]  [dim]{label}[/dim]")

    # ── patterns ───────────────────────────────────────────────────────────
    alerts  = [a for a in ctx["arcs"] if a.severity == "alert"]
    insights = [a for a in ctx["arcs"] if a.severity == "insight"]

    if alerts or insights:
        rp("")
        rule("  patterns  ")
        if alerts:
            rp(f"  [bold {STATE_COLORS['manic']}]![/bold {STATE_COLORS['manic']}]  {alerts[0].message}")
        elif insights:
            rp(f"  [{AMBER}]·[/{AMBER}]  {insights[0].message}")

    # ── pending local store ────────────────────────────────────────────────
    if ctx["pending"] > 0:
        rp("")
        rp(f"  [dim]⚡ {ctx['pending']} entries in local store  (garden may be down)  [/dim]"
           f"[{AMBER_DIM}]\\[y] sync[/{AMBER_DIM}]")

    # ── keys ───────────────────────────────────────────────────────────────
    rp("")
    rule()
    rp(
        f"  [{AMBER_DIM}]\\[v][/{AMBER_DIM}]ent  "
        f"[{AMBER_DIM}]\\[f][/{AMBER_DIM}]lash  "
        f"[{AMBER_DIM}]\\[s][/{AMBER_DIM}]tate  "
        f"[{AMBER_DIM}]\\[b][/{AMBER_DIM}]ody  "
        f"[{AMBER_DIM}]\\[m][/{AMBER_DIM}]ind  "
        f"[{AMBER_DIM}]\\[S][/{AMBER_DIM}]pirit  "
        f"[{AMBER_DIM}]\\[i][/{AMBER_DIM}]ntention  "
        f"[{AMBER_DIM}]\\[r][/{AMBER_DIM}]eview  "
        f"[{AMBER_DIM}]\\[?][/{AMBER_DIM}]help  "
        f"[{AMBER_DIM}]\\[q][/{AMBER_DIM}]uit"
    )
    rp("")


# ---------------------------------------------------------------------------
# Survival mode view
# ---------------------------------------------------------------------------

def _draw_survival(ctx: dict):
    clr()
    w = width()
    sv = ctx["survival"]
    days_str = f"day {sv.days_in_mode}" if sv.days_in_mode > 1 else ""

    rp("")
    rp("")

    title = "·  s u r v i v a l  ·"
    pad = max(0, (w - len(title)) // 2)
    rp(f"{' ' * pad}[{STATE_COLORS['depleted']}]{title}[/{STATE_COLORS['depleted']}]", end="")
    if days_str:
        rp(f"  [dim]{days_str}[/dim]")
    else:
        rp("")

    rp("")
    rule()
    rp("")

    items = [
        "eat something real",
        "drink water",
        "sleep when you can",
    ]
    for item in items:
        item_pad = max(0, (w - len(item) - 6) // 2)
        rp(f"{' ' * item_pad}[{AMBER}]→[/{AMBER}]  [{CREAM}]{item}[/{CREAM}]")

    rp("")
    rule()
    rp("")

    msg = "that's the whole job.  everything else can wait."
    msg_pad = max(0, (w - len(msg)) // 2)
    rp(f"{' ' * msg_pad}[dim]{msg}[/dim]")

    rp("")
    rp("")
    rp(
        f"  [{AMBER_DIM}]\\[l][/{AMBER_DIM}] log state  "
        f"[{AMBER_DIM}]\\[v][/{AMBER_DIM}] vent  "
        f"[{AMBER_DIM}]\\[q][/{AMBER_DIM}] quit"
    )
    rp("")


# ---------------------------------------------------------------------------
# Input screens
# ---------------------------------------------------------------------------

def _screen_vent(ctx: dict) -> bool:
    """Full-screen vent input. Returns True if something was logged."""
    clr()
    _draw_banner()
    rule("  vent  ")
    rp("")
    rp(f"  [{PALE}]just type. parsing happens after.[/{PALE}]")
    rp(f"  [dim]empty line to cancel[/dim]")
    rp("")
    rp(f"  [bold {AMBER}]>[/bold {AMBER}] ", end="")

    text = _read_line()
    if not text:
        return False

    rp("")
    rule()
    rp(f"  [dim]parsing...[/dim]")

    from environments.vent_parser import parse_vent, format_garden_commands
    from environments.local_store import remember as resilient_remember
    from environments.survival_mode import evaluate as eval_survival, filter_entries_for_survival

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
        rp(f"  [{color}]{e.track}[/{color}]  [dim]{e.category} | {e.status or ''} | {(e.note or '')[:40]}[/dim]{dest_note}")
        logged.append(e)

    if not logged:
        rp(f"  [dim](nothing parsed)[/dim]")
        rp("")
        _pause()
        return False

    # Quick pattern check after vent
    rp("")
    from environments.pattern_weaver import weave
    new_states     = _recall("STATE:", 7)
    new_body       = _recall("BODY:", 7)
    new_mind       = _recall("MIND:", 7)
    new_spirit     = _recall("SPIRIT:", 7)
    new_intentions = _recall("INTENTION:", 14)
    arcs = weave(new_states, new_body, new_mind, new_spirit, new_intentions)
    alerts = [a for a in arcs if a.severity == "alert"]

    if alerts:
        rp("")
        rule()
        rp(f"  [bold {STATE_COLORS['manic']}]→[/bold {STATE_COLORS['manic']}]  {alerts[0].message}")

    rp("")
    _pause()
    return True


def _screen_flash(ctx: dict) -> bool:
    """Inline flash capture."""
    clr()
    _draw_banner()
    rule("  flash  ")
    rp("")
    rp(f"  [{PALE}]just a word or phrase. no structure needed.[/{PALE}]")
    rp("")
    rp(f"  [bold {AMBER}]·[/bold {AMBER}] ", end="")

    text = _read_line()
    if not text:
        return False

    content = f"FLASH: {ctx['today']} | {text.strip()}"
    from environments.local_store import remember as resilient_remember
    _, dest = resilient_remember(content)
    dest_note = " (saved locally)" if dest == "local" else ""
    rp("")
    rp(f"  [{PALE}]· {text.strip()}[/{PALE}]  [dim]captured{dest_note}[/dim]")
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
    rp(f"  [{_state_color(tag)}]{_state_symbol(tag)}  {tag}[/{_state_color(tag)}]  ", end="")
    narrative = _read_line()

    content = f"STATE: {ctx['today']} | {tag} | {narrative}"
    from environments.local_store import remember as resilient_remember
    _, dest = resilient_remember(content)
    dest_note = " (local)" if dest == "local" else ""
    rp(f"  [{_state_color(tag)}]{_state_symbol(tag)}  {tag}[/{_state_color(tag)}]  [dim]logged{dest_note}[/dim]")
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


def _screen_generic_track(track: str, title: str, categories: list[str], ctx: dict) -> bool:
    clr()
    _draw_banner()
    rule(f"  {title}  ")
    rp("")

    for i, cat in enumerate(categories, 1):
        rp(f"  [{AMBER_DIM}]{i}[/{AMBER_DIM}]  [{PALE}]{cat}[/{PALE}]")

    rp("")
    rp(f"  [dim]category:[/dim] ", end="")
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

    rp(f"  [dim]status  (e.g. none, poor, low, present, high, scattered):[/dim] ", end="")
    status = _read_line()
    if not status:
        return False

    rp(f"  [dim]note  (optional):[/dim] ", end="")
    note = _read_line()

    content = f"{track}: {ctx['today']} | {category} | {status} | {note}"
    from environments.local_store import remember as resilient_remember
    _, dest = resilient_remember(content)
    dest_note = " (local)" if dest == "local" else ""
    rp("")
    rp(f"  [{PALE}]{track}: {category} | {status}[/{PALE}]  [dim]logged{dest_note}[/dim]")
    rp("")
    _pause(0.6)
    return True


def _screen_intention(ctx: dict) -> bool:
    clr()
    _draw_banner()
    rule("  intention  ")
    rp("")
    rp(f"  [{PALE}]what intention?[/{PALE}] ", end="")
    name = _read_line()
    if not name:
        return False

    rp("")
    rp(f"  [{AMBER_DIM}]1[/{AMBER_DIM}]  [green]✓  met[/green]")
    rp(f"  [{AMBER_DIM}]2[/{AMBER_DIM}]  [yellow]~  partial[/yellow]")
    rp(f"  [{AMBER_DIM}]3[/{AMBER_DIM}]  [dim]·  missed[/dim]")
    rp("")
    rp(f"  [dim]status:[/dim] ", end="")
    s = _read_line()

    status_map = {"1": "met", "2": "partial", "3": "missed",
                  "m": "met", "p": "partial", "miss": "missed",
                  "met": "met", "partial": "partial", "missed": "missed"}
    status = status_map.get(s.lower(), "")
    if not status:
        return False

    rp(f"  [dim]note  (optional):[/dim] ", end="")
    note = _read_line()

    content = f"INTENTION: {name.lower()} | {status} | {ctx['today']} | {note}"
    from environments.local_store import remember as resilient_remember
    _, dest = resilient_remember(content)
    sym_markup, _ = INTENTION_SYMBOLS.get(status, ("[dim]?[/dim]", ""))
    dest_note = " (local)" if dest == "local" else ""
    rp("")
    rp(f"  {sym_markup}  [{PALE}]{name}  {status}[/{PALE}]  [dim]logged{dest_note}[/dim]")
    rp("")
    _pause(0.6)
    return True


# ---------------------------------------------------------------------------
# Review screen
# ---------------------------------------------------------------------------

def _screen_review(ctx: dict):
    clr()
    _draw_banner()
    rule("  cycle review  ")
    rp("")

    states = _recall("STATE:", 14)
    body   = _recall("BODY:", 14)
    spirit = _recall("SPIRIT:", 14)
    intentions = _recall("INTENTION:", 14)

    if not states:
        rp(f"  [dim]no state data to review[/dim]")
        rp("")
        _pause()
        return

    tags = [_extract_tag(e) for e in states]
    first, last = tags[0], tags[-1]

    from collections import Counter
    dominant = Counter(tags).most_common(1)[0][0]
    dominant_color = _state_color(dominant)

    met    = sum(1 for e in intentions if "| met |" in e.get("content", ""))
    missed = sum(1 for e in intentions if "| missed |" in e.get("content", ""))

    rp(f"  [{_state_color(first)}]{_state_symbol(first)}  {first}[/{_state_color(first)}]"
       f"  [dim]→[/dim]  "
       f"[{_state_color(last)}]{_state_symbol(last)}  {last}[/{_state_color(last)}]")
    rp("")
    rule("  what held  ")
    rp(f"  [{dominant_color}]{dominant}[/{dominant_color}] was the dominant state")
    if met or missed:
        rp(f"  [green]✓ {met} met[/green]  [dim]· {missed} missed[/dim]")
    rp("")
    rule("  what dropped  ")

    all_entries = body + spirit
    absent = [t for t in ("connection", "movement", "sleep")
              if not any(t in e.get("content", "").lower() for e in all_entries)]
    if absent:
        for item in absent:
            rp(f"  [dim]→ {item} mostly absent[/dim]")
    else:
        rp(f"  [dim]→ no major absences detected[/dim]")

    rp("")

    # Pull arcs from context
    from environments.pattern_weaver import weave
    mind = _recall("MIND:", 14)
    arcs = weave(states, body, mind, spirit, intentions)
    insights = [a for a in arcs if a.severity == "insight"]
    if insights:
        rule("  pattern  ")
        rp(f"  [{AMBER}]→[/{AMBER}]  {insights[0].message}")
        rp("")

    rule()
    rp(f"  [dim]↩ to return[/dim]")
    _read_key()


# ---------------------------------------------------------------------------
# Help screen
# ---------------------------------------------------------------------------

def _screen_help():
    clr()
    _draw_banner()
    rule("  keys  ")
    rp("")

    keys = [
        ("\\[v]ent",       "free-form text → auto-parsed into STATE/BODY/MIND/SPIRIT"),
        ("\\[f]lash",      "sub-threshold phrase capture — just a word, no structure"),
        ("\\[s]tate",      "log a STATE tag directly"),
        ("\\[b]ody",       "log BODY entry (sleep / pain / hunger / movement / ...)"),
        ("\\[m]ind",       "log MIND entry (focus / clarity / overwhelm / flow)"),
        ("\\[S]pirit",     "log SPIRIT entry (connection / creativity / purpose / isolation)"),
        ("\\[i]ntention",  "log INTENTION: met / missed / partial"),
        ("\\[r]eview",     "cycle review — last 14 days, what held / dropped"),
        ("\\[c]heck",      "refresh patterns and arcs"),
        ("\\[y]sync",      "flush local store to garden (use when garden was down)"),
        ("\\[?] / \\[h]",  "this screen"),
        ("\\[q]uit",       "exit"),
    ]

    for key, desc in keys:
        rp(f"  [bold {AMBER}]{key:<16}[/bold {AMBER}]  [dim]{desc}[/dim]")

    rp("")
    rule()
    rp("")
    rp(f"  [{PALE}]STATE tags:[/{PALE}]")
    rp("")
    for tag in sorted(STATE_SYMBOLS):
        c   = _state_color(tag)
        sym = _state_symbol(tag)
        rp(f"    [{c}]{sym}  {tag}[/{c}]")

    rp("")
    rule()
    rp(f"  [dim]↩ or [q] to return[/dim]")
    key = _read_key()


# ---------------------------------------------------------------------------
# Sync screen
# ---------------------------------------------------------------------------

def _screen_sync(ctx: dict):
    from environments.local_store import sync_to_garden, count_pending, garden_available

    n = count_pending()
    if n == 0:
        rp(f"\n  [dim]local store clean — nothing to sync[/dim]\n")
        _pause(0.8)
        return

    if not garden_available():
        rp(f"\n  [{STATE_COLORS['depleted']}]garden unavailable — {n} entries waiting[/{STATE_COLORS['depleted']}]\n")
        _pause(1.0)
        return

    rp(f"\n  [{AMBER}]syncing {n} entries...[/{AMBER}]")
    result = sync_to_garden()
    if result.get("error"):
        rp(f"  [dim]error: {result['error']}[/dim]")
    else:
        rp(f"  [green]✓ synced {result['synced']}[/green]", end="")
        if result["failed"]:
            rp(f"  [dim]{result['failed']} failed[/dim]")
        else:
            rp("")
    rp("")
    _pause(0.8)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pause(seconds: float = 0):
    if seconds > 0:
        time.sleep(seconds)
    else:
        rp(f"  [dim]↩  continue[/dim]", end="")
        _read_key()


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------

def run():
    """Main entry point for the TUI."""
    if not HAS_RICH:
        print("maps-os TUI requires Rich: pip install rich")
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
    ctx = _load_context()

    while True:
        # Choose view
        if ctx["survival"].active:
            _draw_survival(ctx)
        else:
            _draw_dashboard(ctx)

        key = _read_key()
        refresh = False

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

        elif key == "i":
            refresh = _screen_intention(ctx)

        elif key == "r":
            _screen_review(ctx)

        elif key in ("?", "h"):
            _screen_help()

        elif key == "y":
            _screen_sync(ctx)
            refresh = True

        elif key == "c":
            refresh = True  # force reload

        elif key == "l" and ctx["survival"].active:
            refresh = _screen_state(ctx)

        if refresh:
            ctx = _load_context()
