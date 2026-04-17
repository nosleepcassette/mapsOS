# maps · cassette.help · MIT
"""mapsOS session export helpers for cartographer closed-loop ingest."""

from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path
from typing import Any, Callable

from .local_store import garden_available, recall as recall_local, recall_resilient
from .pattern_weaver import weave


DEFAULT_EXPORT_DIR = Path.home() / ".mapsOS" / "exports"
DEFAULT_ATLAS_TASKS_PATH = Path.home() / "atlas" / "tasks" / "mapsos.md"
TASK_BLOCK_PATTERN = re.compile(
    r'<!-- cart:block id="(?P<id>[^"]+)"(?P<attrs>[^>]*) -->'
    r"(?P<content>.*?)"
    r"<!-- /cart:block -->",
    re.DOTALL,
)


def _recall(prefix: str, graph: str, limit: int) -> list[dict]:
    if not garden_available(timeout=1):
        return recall_local(prefix, graph=graph, limit=limit)
    entries, _ = recall_resilient(prefix, graph=graph, limit=limit)
    return entries


def _parse_state_entry(content: str) -> dict[str, Any] | None:
    if not content.startswith("STATE:"):
        return None
    parts = [part.strip() for part in content.split("|", 2)]
    if len(parts) < 2:
        return None
    try:
        entry_date = datetime.strptime(parts[0].replace("STATE:", "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None
    return {
        "date": entry_date.isoformat(),
        "tag": parts[1].lower(),
        "note": parts[2] if len(parts) > 2 else "",
    }


def _parse_body_entry(content: str) -> dict[str, Any] | None:
    if not content.startswith("BODY:"):
        return None
    parts = [part.strip() for part in content.split("|", 3)]
    if len(parts) < 3:
        return None
    try:
        entry_date = datetime.strptime(parts[0].replace("BODY:", "").strip(), "%Y-%m-%d").date()
    except Exception:
        return None
    return {
        "date": entry_date.isoformat(),
        "category": parts[1].lower(),
        "status": parts[2].lower(),
        "note": parts[3] if len(parts) > 3 else "",
    }


def _parse_intention_entry(content: str) -> dict[str, Any] | None:
    if not content.startswith("INTENTION:"):
        return None
    parts = [part.strip() for part in content.split("|", 3)]
    if len(parts) < 3:
        return None
    return {
        "name": parts[0].replace("INTENTION:", "").strip(),
        "status": parts[1].lower(),
        "date": parts[2],
        "note": parts[3] if len(parts) > 3 else "",
    }


def _parse_goal_entry(content: str) -> dict[str, Any] | None:
    if not content.startswith("GOAL:"):
        return None
    parts = [part.strip() for part in content.split("|", 3)]
    if len(parts) < 4:
        return None
    return {
        "date": parts[0].replace("GOAL:", "").strip(),
        "title": parts[1],
        "due": parts[2],
        "status": parts[3].lower(),
    }


def _latest_by_key(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    latest: dict[str, dict[str, Any]] = {}
    for item in items:
        identifier = str(item.get(key, "")).lower()
        if identifier and identifier not in latest:
            latest[identifier] = item
    return list(latest.values())


def load_brief_text(path: str | Path | None) -> str:
    if path is None:
        return ""
    brief_path = Path(path).expanduser()
    if not brief_path.exists():
        return ""
    return brief_path.read_text(encoding="utf-8").strip()


def load_atlas_task_hints(path: str | Path | None = None) -> list[dict[str, Any]]:
    tasks_path = Path(path).expanduser() if path is not None else DEFAULT_ATLAS_TASKS_PATH
    if not tasks_path.exists():
        return []
    text = tasks_path.read_text(encoding="utf-8")
    tasks: list[dict[str, Any]] = []
    for match in TASK_BLOCK_PATTERN.finditer(text):
        lines = [line.rstrip() for line in match.group("content").strip().splitlines() if line.strip()]
        if not lines:
            continue
        checkbox = re.match(r"^- \[(?P<done>[ xX])\] (?P<text>.+)$", lines[0].strip())
        if checkbox is None or checkbox.group("done").lower() == "x":
            continue
        task = {"title": checkbox.group("text").strip(), "status": "open"}
        for line in lines[1:]:
            meta = re.match(r"^\s{2,}(?P<key>[A-Za-z0-9_-]+):\s*(?P<value>.+)$", line)
            if meta:
                task[meta.group("key")] = meta.group("value")
        tasks.append(task)
    return tasks


def build_session_export(
    *,
    graph: str = "cassette",
    recall_fn: Callable[[str, str, int], list[dict]] = _recall,
    brief_path: str | Path | None = None,
    atlas_tasks_path: str | Path | None = None,
) -> dict[str, Any]:
    state_entries = recall_fn("STATE:", graph, 7)
    body_entries = recall_fn("BODY:", graph, 14)
    mind_entries = recall_fn("MIND:", graph, 7)
    spirit_entries = recall_fn("SPIRIT:", graph, 7)
    intention_entries = recall_fn("INTENTION:", graph, 14)
    flash_entries = recall_fn("FLASH:", graph, 10)
    decision_entries = recall_fn("DECISION:", graph, 14)
    trigger_entries = recall_fn("TRIGGER:", graph, 14)
    goal_entries = recall_fn("GOAL:", graph, 30)
    person_entries = recall_fn("PERSON:", graph, 21)
    resistance_entries = recall_fn("RESISTANCE:", graph, 21)

    arcs = weave(
        state_entries,
        body_entries,
        mind_entries,
        spirit_entries,
        intention_entries,
        flash_entries=flash_entries,
        decision_entries=decision_entries,
        trigger_entries=trigger_entries,
        goal_entries=goal_entries,
        person_entries=person_entries,
        resistance_entries=resistance_entries,
    )

    parsed_states = [parsed for parsed in (_parse_state_entry(entry.get("content", "")) for entry in state_entries) if parsed]
    latest_state = parsed_states[0] if parsed_states else None

    parsed_body = [parsed for parsed in (_parse_body_entry(entry.get("content", "")) for entry in body_entries) if parsed]
    latest_body = _latest_by_key(parsed_body, "category")
    body = {
        item["category"]: item["status"]
        for item in latest_body
        if item["category"] in {"sleep", "energy", "pain"}
    }

    parsed_intentions = [
        parsed for parsed in (_parse_intention_entry(entry.get("content", "")) for entry in intention_entries) if parsed
    ]
    intentions = [item["name"] for item in _latest_by_key(parsed_intentions, "name")[:5]]

    parsed_goals = [parsed for parsed in (_parse_goal_entry(entry.get("content", "")) for entry in goal_entries) if parsed]
    tasks = []
    for goal in _latest_by_key(parsed_goals, "title"):
        if goal["status"] == "done":
            continue
        task = {
            "title": goal["title"],
            "status": "done" if goal["status"] == "done" else "open",
        }
        if goal["due"] and goal["due"].lower() != "none":
            task["due"] = goal["due"]
        tasks.append(task)

    brief_text = load_brief_text(brief_path)
    atlas_task_hints = load_atlas_task_hints(atlas_tasks_path)
    top_arc_message = getattr(arcs[0], "message", "") if arcs else ""

    payload: dict[str, Any] = {
        "date": date.today().isoformat(),
        "state": latest_state["tag"] if latest_state else "unknown",
        "body": body,
        "arcs": [getattr(arc, "name", "") for arc in arcs if getattr(arc, "name", "")],
        "intentions": intentions,
        "tasks": tasks,
        "summary": latest_state["note"] if latest_state and latest_state["note"] else top_arc_message or "mapsOS session export",
        "notes": brief_text[:800] if brief_text else "",
        "atlas_tasks": atlas_task_hints,
    }
    if brief_path is not None:
        payload["brief_source"] = str(Path(brief_path).expanduser())
    return payload


def write_session_export(
    *,
    graph: str = "cassette",
    export_dir: str | Path | None = None,
    brief_path: str | Path | None = None,
    atlas_tasks_path: str | Path | None = None,
) -> Path:
    target_dir = Path(export_dir).expanduser() if export_dir is not None else DEFAULT_EXPORT_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    payload = build_session_export(
        graph=graph,
        brief_path=brief_path,
        atlas_tasks_path=atlas_tasks_path,
    )
    payload["session_id"] = f"session_{ts}"
    destination = target_dir / f"session_{ts}.json"
    destination.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return destination
