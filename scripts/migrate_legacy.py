#!/usr/bin/env python3
# maps · cassette.help · MIT
"""
migrate_legacy.py — Migrate life-os garden entries to maps-os schema.

Handles:
  MOOD: {date} | {score 1-10} | {note}   →  STATE: {date} | {inferred_tag} | legacy_mood:{score} {note}
  ENERGY: {date} | {level} | {context}   →  BODY: {date} | energy | {mapped_status} | {context}
  HABIT: {name} | {streak} | {last_done} →  INTENTION: {name} | met | {last_done} | legacy_streak:{streak}

Usage:
  python3 scripts/migrate_legacy.py --input legacy_garden.txt --output migrated.txt
  python3 scripts/migrate_legacy.py --input legacy_garden.txt --dry-run
  python3 scripts/migrate_legacy.py --garden  # read/write directly to garden (requires garden CLI)
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Mood score → STATE tag mapping
# ---------------------------------------------------------------------------

def _mood_score_to_tag(score: int) -> str:
    """
    Map legacy 1-10 mood score to closest qualitative STATE tag.
    We preserve the score in the narrative so no data is lost.
    """
    if score <= 2:
        return "surviving"
    if score <= 4:
        return "depleted"
    if score == 5:
        return "stable"
    if score <= 7:
        return "stable"
    if score <= 9:
        return "thriving"
    return "thriving"


def _energy_level_to_status(level: str) -> str:
    level = level.strip().lower()
    mapping = {
        "low": "exhausted",
        "medium": "low",
        "med": "low",
        "high": "present",
        "very high": "energized",
        "very low": "exhausted",
        "good": "present",
        "bad": "exhausted",
    }
    return mapping.get(level, level)


# ---------------------------------------------------------------------------
# Line parsers
# ---------------------------------------------------------------------------

@dataclass
class MigratedEntry:
    original: str
    migrated: str
    track: str
    note: str = ""


def _parse_mood(line: str) -> Optional[MigratedEntry]:
    """MOOD: {date} | {score} | {note}"""
    m = re.match(r"MOOD:\s*(\S+)\s*\|\s*(\d+(?:\.\d+)?)\s*\|\s*(.*)", line.strip())
    if not m:
        return None
    date, score_str, note = m.group(1), m.group(2), m.group(3).strip()
    try:
        score = int(float(score_str))
    except ValueError:
        score = 5
    tag = _mood_score_to_tag(score)
    narrative = f"legacy_mood:{score}"
    if note:
        narrative += f" | {note}"
    migrated = f"STATE: {date} | {tag} | {narrative}"
    return MigratedEntry(original=line.strip(), migrated=migrated, track="STATE",
                         note=f"mood {score}/10 → {tag}")


def _parse_energy(line: str) -> Optional[MigratedEntry]:
    """ENERGY: {date} | {level} | {context}"""
    m = re.match(r"ENERGY:\s*(\S+)\s*\|\s*([^|]+)\s*\|\s*(.*)", line.strip())
    if not m:
        # Try 2-part: ENERGY: {date} | {level}
        m2 = re.match(r"ENERGY:\s*(\S+)\s*\|\s*([^|]+)", line.strip())
        if not m2:
            return None
        date, level = m2.group(1), m2.group(2)
        context = ""
    else:
        date, level, context = m.group(1), m.group(2), m.group(3).strip()
    status = _energy_level_to_status(level)
    note_parts = [f"legacy_level:{level.strip()}"]
    if context:
        note_parts.append(context)
    migrated = f"BODY: {date} | energy | {status} | {' | '.join(note_parts)}"
    return MigratedEntry(original=line.strip(), migrated=migrated, track="BODY",
                         note=f"energy {level.strip()} → {status}")


def _parse_habit(line: str) -> Optional[MigratedEntry]:
    """HABIT: {name} | {streak} | {last_done}"""
    m = re.match(r"HABIT:\s*([^|]+)\s*\|\s*(\d+)\s*\|\s*(\S+)", line.strip())
    if not m:
        return None
    name, streak, last_done = m.group(1).strip(), m.group(2), m.group(3)
    # A non-zero streak means the habit was being met
    status = "met" if int(streak) > 0 else "missed"
    migrated = f"INTENTION: {name} | {status} | {last_done} | legacy_streak:{streak}"
    return MigratedEntry(original=line.strip(), migrated=migrated, track="INTENTION",
                         note=f"habit '{name}' streak:{streak} → {status}")


def _parse_insight(line: str) -> Optional[MigratedEntry]:
    """INSIGHT: {date} | {observation} | {confidence} — pass through as-is, valid in maps-os"""
    if line.strip().startswith("INSIGHT:"):
        return MigratedEntry(original=line.strip(), migrated=line.strip(), track="INSIGHT",
                             note="passed through unchanged")
    return None


def _parse_win(line: str) -> Optional[MigratedEntry]:
    """WIN: {date} | {description} — pass through"""
    if line.strip().startswith("WIN:"):
        return MigratedEntry(original=line.strip(), migrated=line.strip(), track="WIN",
                             note="passed through unchanged")
    return None


def _parse_struggle(line: str) -> Optional[MigratedEntry]:
    """STRUGGLE: {date} | {description} | {resolved} — pass through"""
    if line.strip().startswith("STRUGGLE:"):
        return MigratedEntry(original=line.strip(), migrated=line.strip(), track="STRUGGLE",
                             note="passed through unchanged")
    return None


PARSERS = [_parse_mood, _parse_energy, _parse_habit, _parse_insight, _parse_win, _parse_struggle]


def migrate_line(line: str) -> Optional[MigratedEntry]:
    """Try all parsers on a line. Return first match or None."""
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    for parser in PARSERS:
        result = parser(stripped)
        if result is not None:
            return result
    return None


def migrate_text(text: str) -> tuple[list[MigratedEntry], list[str]]:
    """
    Migrate all lines in text.
    Returns (migrated_entries, unrecognized_lines).
    """
    entries = []
    unrecognized = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        result = migrate_line(stripped)
        if result:
            entries.append(result)
        else:
            unrecognized.append(stripped)
    return entries, unrecognized


def format_output(entries: list[MigratedEntry], include_comments: bool = True) -> str:
    """Format migrated entries as garden remember commands."""
    lines = []
    if include_comments:
        lines.append("# maps-os garden migration output")
        lines.append("# Generated by scripts/migrate_legacy.py")
        lines.append("")
    for e in entries:
        if include_comments:
            lines.append(f"# was: {e.original}")
        lines.append(f"garden remember '{e.migrated}' --graph cassette")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Migrate life-os garden entries to maps-os schema"
    )
    parser.add_argument("--input", "-i", help="Input file with legacy garden entries")
    parser.add_argument("--output", "-o", help="Output file (default: stdout)")
    parser.add_argument("--dry-run", action="store_true", help="Print migration plan without writing")
    parser.add_argument("--no-comments", action="store_true", help="Suppress # comment lines in output")
    parser.add_argument("--stats", action="store_true", help="Print migration statistics")
    args = parser.parse_args()

    if not args.input:
        parser.print_help()
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"Error: {args.input} not found", file=sys.stderr)
        sys.exit(1)

    text = input_path.read_text(encoding="utf-8")
    entries, unrecognized = migrate_text(text)

    if args.stats or args.dry_run:
        track_counts: dict[str, int] = {}
        for e in entries:
            track_counts[e.track] = track_counts.get(e.track, 0) + 1
        print(f"Migration plan: {len(entries)} entries")
        for track, count in sorted(track_counts.items()):
            print(f"  {track}: {count}")
        if unrecognized:
            print(f"  Unrecognized (skipped): {len(unrecognized)}")
            for line in unrecognized[:5]:
                print(f"    {line}")
            if len(unrecognized) > 5:
                print(f"    ... and {len(unrecognized) - 5} more")
        print()

    if args.dry_run:
        print(format_output(entries, include_comments=not args.no_comments))
        return

    output = format_output(entries, include_comments=not args.no_comments)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Written to {args.output} ({len(entries)} entries)")
    else:
        print(output)


if __name__ == "__main__":
    main()
