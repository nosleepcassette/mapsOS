# maps · cassette.help · MIT
"""
cart_bridge.py — Bidirectional bridge between mapsOS and cartographer atlas.

All functions degrade gracefully. If cart is unavailable, returns empty/False.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any


def cart_available() -> bool:
    """Check if the cart CLI is on PATH."""
    try:
        result = subprocess.run(
            ["cart", "--help"],
            capture_output=True,
            timeout=3,
            check=False,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False


def _run_cart(
    command: list[str],
    *,
    timeout: int = 8,
    text: bool = True,
) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(
            ["cart", *command],
            capture_output=True,
            text=text,
            timeout=timeout,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def _run_cart_json(command: list[str], *, timeout: int = 8) -> dict[str, Any] | None:
    result = _run_cart(command, timeout=timeout, text=True)
    if result is None or result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


def _surface_ok(payload: dict[str, Any] | None, surface: str) -> bool:
    return isinstance(payload, dict) and str(payload.get("surface") or "") == surface


def _note_summary(path: Path) -> dict[str, Any]:
    title = path.stem
    note_id = path.stem
    note_type = "note"
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []

    if lines[:1] == ["---"]:
        for line in lines[1:40]:
            if line == "---":
                break
            key, _, value = line.partition(":")
            if not _:
                continue
            normalized_key = key.strip().lower()
            normalized_value = value.strip().strip("'\"")
            if normalized_key == "title" and normalized_value:
                title = normalized_value
            elif normalized_key == "id" and normalized_value:
                note_id = normalized_value
            elif normalized_key == "type" and normalized_value:
                note_type = normalized_value

    modified = None
    try:
        modified = path.stat().st_mtime
    except OSError:
        modified = None
    return {
        "id": note_id,
        "title": title,
        "type": note_type,
        "path": str(path),
        "modified": modified,
    }


def get_open_tasks(priority: str | None = None) -> list[dict[str, Any]]:
    """Return open atlas tasks from cart."""
    if not cart_available():
        return []
    expr = f"priority:{priority} status:open" if priority else "status:open"
    payload = _run_cart_json(["todo", "query", "--json", expr], timeout=5)
    if payload is None:
        return []
    raw_tasks = payload.get("tasks")
    if not isinstance(raw_tasks, list):
        return []
    tasks: list[dict[str, Any]] = []
    for raw in raw_tasks:
        if not isinstance(raw, dict):
            continue
        text = str(raw.get("text") or "").strip()
        if not text:
            continue
        tasks.append(
            {
                "id": str(raw.get("id") or ""),
                "text": text,
                "status": str(raw.get("status") or ""),
                "priority": str(raw.get("priority") or ""),
                "project": str(raw.get("project") or ""),
                "due": str(raw.get("due") or ""),
                "path": str(raw.get("path") or ""),
            }
        )
    return tasks


def get_daily_brief() -> str:
    """Return cart daily-brief output as plain text."""
    if not cart_available():
        return ""
    result = _run_cart(["daily-brief", "--format", "plain"], timeout=10, text=True)
    if result is None:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def get_recent_sessions(n: int = 3) -> list[dict[str, Any]]:
    """Return the most recent session and agent-log note summaries from cart."""
    if not cart_available():
        return []
    payload = _run_cart_json(["sessions", "recent", "--json", "--limit", str(max(n, 0))], timeout=6)
    if payload is not None:
        raw_sessions = payload.get("sessions")
        if isinstance(raw_sessions, list):
            sessions: list[dict[str, Any]] = []
            for raw in raw_sessions:
                if not isinstance(raw, dict):
                    continue
                sessions.append(
                    {
                        "id": str(raw.get("id") or ""),
                        "title": str(raw.get("title") or ""),
                        "agent": str(raw.get("agent") or ""),
                        "type": str(raw.get("type") or ""),
                        "date": str(raw.get("date") or ""),
                        "summary_preview": str(raw.get("summary_preview") or ""),
                        "path": str(raw.get("path") or ""),
                        "source_type": str(raw.get("source_type") or ""),
                    }
                )
            return sessions

    # Fallback for older cart versions that do not yet expose sessions.recent.
    results: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    for note_type in ("agent-log", "session"):
        payload = _run_cart_json(["query", "--json", f"type:{note_type}"], timeout=6)
        if payload is None:
            continue
        raw_results = payload.get("results")
        if not isinstance(raw_results, list):
            continue
        for raw_path in raw_results:
            path = Path(str(raw_path)).expanduser()
            if not path.exists():
                continue
            resolved = str(path)
            if resolved in seen_paths:
                continue
            seen_paths.add(resolved)
            results.append(_note_summary(path))
    results.sort(
        key=lambda item: float(item.get("modified") or 0.0),
        reverse=True,
    )
    trimmed = results[: max(n, 0)]
    for item in trimmed:
        item.pop("modified", None)
    return trimmed


def get_doctor_payload() -> dict[str, Any]:
    """Return `cart doctor --json` payload when available."""
    if not cart_available():
        return {"available": False, "warnings": ["cart CLI is unavailable"]}
    payload = _run_cart_json(["doctor", "--json"], timeout=8)
    if payload is None:
        return {"available": False, "warnings": ["cart doctor failed"]}
    payload["available"] = True
    return payload


def bridge_health() -> dict[str, Any]:
    """Return a summarized health view for the mapsOS -> Cart bridge."""
    if not cart_available():
        return {
            "available": False,
            "tasks": False,
            "sessions": False,
            "doctor": False,
            "warnings": ["cart CLI is unavailable"],
        }

    doctor = get_doctor_payload()
    tasks_payload = _run_cart_json(["todo", "list", "--json"], timeout=5)
    sessions_payload = _run_cart_json(
        ["sessions", "recent", "--json", "--limit", "1"],
        timeout=6,
    )
    tasks_ok = _surface_ok(tasks_payload, "todo.list")
    sessions_ok = _surface_ok(sessions_payload, "sessions.recent")
    warnings = list(doctor.get("warnings") or [])
    if not tasks_ok:
        warnings.append("cart task surface unavailable")
    if not sessions_ok:
        warnings.append("cart session surface unavailable")
    return {
        "available": True,
        "tasks": tasks_ok,
        "sessions": sessions_ok,
        "doctor": bool(doctor.get("available")),
        "warnings": warnings,
    }


def ingest_export(export_path: str | None = None) -> bool:
    """Tell cart to ingest the latest mapsOS export."""
    if not cart_available():
        return False
    command = (
        ["cart", "mapsos", "ingest", export_path]
        if export_path
        else ["cart", "mapsos", "ingest-exports", "--latest"]
    )
    try:
        result = subprocess.run(command, capture_output=True, timeout=15, check=False)
    except Exception:
        return False
    return result.returncode == 0


def push_intention(text: str, category: str = "mind") -> bool:
    """Write a mapsOS intention into cartographer's native task surface."""
    if not cart_available():
        return False
    project = f"mapsos-{category.strip().lower()}" if category.strip() else "mapsos"
    try:
        result = subprocess.run(
            ["cart", "todo", "add", text, "-p", "P2", "--project", project],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def push_intention_to_tasks(text: str, priority: str = "P2") -> bool:
    """Backward-compatible alias for older handoff notes."""
    if not cart_available():
        return False
    try:
        result = subprocess.run(
            ["cart", "todo", "add", text, "-p", priority],
            capture_output=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return False
    return result.returncode == 0


def cart_repo_root() -> Path | None:
    """Return the common local checkout path when present."""
    root = Path.home() / "dev" / "cartographer"
    return root if root.exists() else None
