# maps · cassette.help · MIT
"""
local_store.py — Garden-independent local storage for maps-os.

When garden is unavailable, entries are written here instead.
Same format as garden entries — pipes-delimited strings.
A sync command flushes pending entries to garden when it's back.

Storage: ~/.maps_os_local.db (SQLite)
"""
from __future__ import annotations

import sqlite3
import subprocess
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator, Optional


DEFAULT_DB_PATH = Path.home() / ".maps_os_local.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS entries (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    content  TEXT    NOT NULL,
    graph    TEXT    NOT NULL DEFAULT 'cassette',
    synced   INTEGER NOT NULL DEFAULT 0,
    ts       TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_synced ON entries(synced);
CREATE INDEX IF NOT EXISTS idx_ts     ON entries(ts);
"""


@contextmanager
def _db(path: Path = DEFAULT_DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.executescript(_SCHEMA)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Core write / read
# ---------------------------------------------------------------------------

def write(content: str, graph: str = "cassette", db_path: Path = DEFAULT_DB_PATH) -> int:
    """
    Write an entry to local store.
    Returns the new row id.
    """
    ts = datetime.utcnow().isoformat() + "Z"
    with _db(db_path) as conn:
        cur = conn.execute(
            "INSERT INTO entries (content, graph, synced, ts) VALUES (?, ?, 0, ?)",
            (content, graph, ts),
        )
        return cur.lastrowid


def recall(prefix: str, graph: str = "cassette", limit: int = 7,
           db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """
    Recall entries from local store matching a prefix.
    Returns list of dicts with 'content' key (same shape as garden recall).
    """
    with _db(db_path) as conn:
        rows = conn.execute(
            "SELECT content FROM entries WHERE graph = ? AND content LIKE ? "
            "ORDER BY ts DESC LIMIT ?",
            (graph, f"{prefix}%", limit),
        ).fetchall()
    return [{"content": row["content"]} for row in rows]


def pending(graph: str = "cassette", db_path: Path = DEFAULT_DB_PATH) -> list[dict]:
    """Return all unsynced entries."""
    with _db(db_path) as conn:
        rows = conn.execute(
            "SELECT id, content, graph, ts FROM entries WHERE synced = 0 AND graph = ? "
            "ORDER BY ts ASC",
            (graph,),
        ).fetchall()
    return [dict(row) for row in rows]


def mark_synced(entry_ids: list[int], db_path: Path = DEFAULT_DB_PATH) -> int:
    """Mark entries as synced. Returns count updated."""
    if not entry_ids:
        return 0
    placeholders = ",".join("?" * len(entry_ids))
    with _db(db_path) as conn:
        cur = conn.execute(
            f"UPDATE entries SET synced = 1 WHERE id IN ({placeholders})",
            entry_ids,
        )
        return cur.rowcount


def count_pending(graph: str = "cassette", db_path: Path = DEFAULT_DB_PATH) -> int:
    with _db(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM entries WHERE synced = 0 AND graph = ?", (graph,)
        ).fetchone()
    return row[0] if row else 0


# ---------------------------------------------------------------------------
# Garden health check
# ---------------------------------------------------------------------------

def garden_available(timeout: int = 3) -> bool:
    """
    Returns True if garden CLI is reachable.
    Uses a lightweight list-graphs call as a health check.
    """
    try:
        result = subprocess.run(
            ["garden", "list-graphs"],
            capture_output=True, timeout=timeout,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


# ---------------------------------------------------------------------------
# Resilient garden operations
# ---------------------------------------------------------------------------

def _normalize_garden_entry(entry: Any) -> Optional[dict]:
    """
    Normalize garden recall output to the historical {"content": "..."} shape.
    """
    if isinstance(entry, str):
        return {"content": entry}

    if not isinstance(entry, dict):
        return None

    content = entry.get("content")
    if isinstance(content, str):
        return {"content": content}

    text = entry.get("text")
    if isinstance(text, str):
        return {"content": text}

    return None


def _normalize_garden_recall_payload(payload: Any, prefix: str) -> list[dict]:
    """
    Garden has emitted both a raw list and an envelope object over time.
    Normalize both to a list of {"content": "..."} dicts.
    """
    raw_entries: Any = payload

    if isinstance(payload, dict):
        for key in ("data", "entries", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                raw_entries = value
                break
        else:
            raw_entries = [payload]

    if not isinstance(raw_entries, list):
        return []

    normalized: list[dict] = []
    for entry in raw_entries:
        item = _normalize_garden_entry(entry)
        if item is not None and item["content"].startswith(prefix):
            normalized.append(item)
    return normalized

def remember(content: str, graph: str = "cassette",
             db_path: Path = DEFAULT_DB_PATH) -> tuple[bool, str]:
    """
    Write to garden. Falls back to local store if garden is unavailable.

    Returns:
        (wrote_to_garden: bool, destination: 'garden' | 'local')
    """
    cmd = f"garden remember '{content}' --graph {graph}"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return True, "garden"
    except (subprocess.TimeoutExpired, OSError):
        pass

    # Garden failed — write to local store
    write(content, graph=graph, db_path=db_path)
    return False, "local"


def recall_resilient(prefix: str, graph: str = "cassette", limit: int = 7,
                     db_path: Path = DEFAULT_DB_PATH) -> tuple[list[dict], str]:
    """
    Recall from garden. Falls back to local store if garden unavailable.

    Returns:
        (entries: list[dict], source: 'garden' | 'local' | 'merged')
    """
    import json

    garden_entries: list[dict] = []
    local_entries: list[dict] = []
    garden_ok = False

    # Try garden first
    cmd = f"garden recall '{prefix}' --graph {graph} --limit {limit} --json"
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            garden_entries = _normalize_garden_recall_payload(json.loads(result.stdout), prefix=prefix)
            garden_ok = True
    except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        pass

    # Also pull from local (may have unsynced entries)
    local_entries = recall(prefix, graph=graph, limit=limit, db_path=db_path)

    if not local_entries and garden_ok:
        return garden_entries, "garden"
    if not garden_ok and local_entries:
        return local_entries, "local"
    if garden_ok and local_entries:
        # Merge: garden entries take precedence, deduplicate by content prefix
        seen = {e["content"][:40] for e in garden_entries}
        merged = list(garden_entries)
        for e in local_entries:
            if e["content"][:40] not in seen:
                merged.append(e)
        return merged[:limit], "merged"

    return [], "none"


# ---------------------------------------------------------------------------
# Sync — flush local store to garden
# ---------------------------------------------------------------------------

def sync_to_garden(graph: str = "cassette", db_path: Path = DEFAULT_DB_PATH,
                   dry_run: bool = False) -> dict:
    """
    Flush all unsynced local entries to garden.

    Returns:
        {"synced": int, "failed": int, "skipped": int}
    """
    if not garden_available():
        return {"synced": 0, "failed": 0, "skipped": -1, "error": "garden unavailable"}

    unsynced = pending(graph=graph, db_path=db_path)
    if not unsynced:
        return {"synced": 0, "failed": 0, "skipped": 0}

    synced_ids = []
    failed = 0

    for entry in unsynced:
        content = entry["content"]
        cmd = f"garden remember '{content}' --graph {entry['graph']}"

        if dry_run:
            print(f"  [dry] {cmd}")
            synced_ids.append(entry["id"])
            continue

        try:
            result = subprocess.run(
                cmd, shell=True, capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                synced_ids.append(entry["id"])
            else:
                failed += 1
        except (subprocess.TimeoutExpired, OSError):
            failed += 1

    if not dry_run:
        mark_synced(synced_ids, db_path=db_path)

    return {"synced": len(synced_ids), "failed": failed, "skipped": 0}


# ---------------------------------------------------------------------------
# CLI entry point (for `maps sync`)
# ---------------------------------------------------------------------------

def main():
    import argparse
    p = argparse.ArgumentParser(description="Sync local maps-os store to garden")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--graph", default="cassette")
    p.add_argument("--status", action="store_true", help="Show pending count only")
    args = p.parse_args()

    if args.status:
        n = count_pending(graph=args.graph)
        if n == 0:
            print("local store: clean (nothing pending)")
        else:
            print(f"local store: {n} unsynced entries")
            print("  run 'maps sync' when garden is available")
        return

    if not garden_available():
        n = count_pending(graph=args.graph)
        print(f"garden unavailable — {n} entries waiting in local store")
        return

    result = sync_to_garden(graph=args.graph, dry_run=args.dry_run)
    if result.get("error"):
        print(f"sync failed: {result['error']}")
    else:
        print(f"synced {result['synced']} entries to garden")
        if result["failed"]:
            print(f"  {result['failed']} failed — will retry next sync")


if __name__ == "__main__":
    main()
