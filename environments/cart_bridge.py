# maps · cassette.help · MIT
"""
cart_bridge.py — Bidirectional bridge between mapsOS and cartographer atlas.

All functions degrade gracefully. If cart is unavailable, returns empty/False.
"""

from __future__ import annotations

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


def get_open_tasks(priority: str | None = None) -> list[dict[str, Any]]:
    """Return open atlas tasks from cart."""
    if not cart_available():
        return []
    expr = f"priority:{priority} status:open" if priority else "status:open"
    try:
        result = subprocess.run(
            ["cart", "todo", "query", expr],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    tasks: list[dict[str, Any]] = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        tasks.append({"text": line})
    return tasks


def get_daily_brief() -> str:
    """Return cart daily-brief output as plain text."""
    if not cart_available():
        return ""
    try:
        result = subprocess.run(
            ["cart", "daily-brief", "--format", "plain"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except Exception:
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def get_recent_sessions(n: int = 3) -> list[dict[str, Any]]:
    """Return the most recent session note paths from cart."""
    if not cart_available():
        return []
    try:
        result = subprocess.run(
            ["cart", "query", "type:agent-log"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except Exception:
        return []
    if result.returncode != 0:
        return []
    lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return [{"path": path} for path in lines[-n:]]


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
