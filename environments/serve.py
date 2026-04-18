# maps · cassette.help · MIT
"""Optional HTTP server exposing mapsOS helpers over FastAPI."""

from __future__ import annotations

import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from typing import Any

from environments.local_store import recall_resilient, write
from environments.pattern_weaver import weave
from environments.survival_mode import evaluate as eval_survival
from environments.vent_parser import parse_vent

from .serve_auth import ServeAuthError, TOKEN_ENV, validate_bearer_token

try:
    from fastapi import FastAPI, Header, HTTPException
    import uvicorn

    _FASTAPI_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    FastAPI = Any  # type: ignore[assignment]
    Header = HTTPException = None  # type: ignore[assignment]
    uvicorn = None  # type: ignore[assignment]
    _FASTAPI_AVAILABLE = False


VERSION = "0.1.0"
_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
_SESSION_START_TIMEOUT = 12.0
_CHECK_TRACKS: tuple[tuple[str, int], ...] = (
    ("STATE:", 14),
    ("BODY:", 14),
    ("MIND:", 14),
    ("SPIRIT:", 14),
    ("INTENTION:", 21),
    ("FLASH:", 14),
)


def is_available() -> bool:
    return _FASTAPI_AVAILABLE


def _parse_entry_date(content: str) -> date | None:
    match = _DATE_RE.search(content)
    if not match:
        return None
    try:
        return date.fromisoformat(match.group(0))
    except ValueError:
        return None


def _entry_ts(raw: dict[str, Any]) -> str:
    value = str(raw.get("ts") or "").strip()
    if value:
        return value

    parsed_date = _parse_entry_date(str(raw.get("content") or ""))
    if parsed_date is not None:
        return f"{parsed_date.isoformat()}T00:00:00Z"

    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _normalized_entry(raw: dict[str, Any], fallback_id: int) -> dict[str, Any]:
    return {
        "content": str(raw.get("content") or "").strip(),
        "ts": _entry_ts(raw),
        "id": int(raw.get("id") or fallback_id),
    }


def _entry_sort_key(entry: dict[str, Any]) -> tuple[str, int]:
    return (str(entry.get("ts") or ""), int(entry.get("id") or 0))


def _entry_content_parts(entry: dict[str, Any], *, maxsplit: int) -> list[str]:
    return [part.strip() for part in str(entry.get("content") or "").split("|", maxsplit)]


def _latest_body_state(entries: list[dict[str, Any]]) -> dict[str, str]:
    latest: dict[str, str] = {}
    for entry in reversed(entries):
        parts = _entry_content_parts(entry, maxsplit=3)
        if len(parts) < 3:
            continue
        category = parts[1].lower()
        status = parts[2].lower()
        if category and category not in latest:
            latest[category] = status
    return latest


def _latest_intention_state(entries: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, str]]:
    latest: dict[str, dict[str, str]] = {}
    for entry in reversed(entries):
        parts = _entry_content_parts(entry, maxsplit=3)
        if len(parts) < 3:
            continue
        name = parts[0].replace("INTENTION:", "").strip().lower()
        if not name or name in latest:
            continue
        latest[name] = {
            "name": name,
            "status": parts[1].lower(),
            "date": parts[2],
            "note": parts[3] if len(parts) > 3 else "",
        }
    return list(latest.values())[:limit]


def _flash_texts(entries: list[dict[str, Any]], *, limit: int = 5) -> list[str]:
    snippets: list[str] = []
    for entry in entries[-limit:]:
        parts = _entry_content_parts(entry, maxsplit=1)
        if len(parts) < 2:
            continue
        text = parts[1].strip()
        if text:
            snippets.append(text)
    return snippets


def _state_tag(entry: dict[str, Any] | None) -> str:
    if not isinstance(entry, dict):
        return "unknown"
    parts = _entry_content_parts(entry, maxsplit=2)
    if len(parts) < 2:
        return "unknown"
    return parts[1].lower()


def _session_summary(check: dict[str, Any]) -> str:
    state_entry = check.get("state")
    if isinstance(state_entry, dict):
        parts = _entry_content_parts(state_entry, maxsplit=2)
        if len(parts) > 2 and parts[2]:
            return parts[2]
    arcs = check.get("arcs")
    if isinstance(arcs, list):
        for arc in arcs:
            if isinstance(arc, dict):
                message = str(arc.get("message") or "").strip()
                if message:
                    return message
    return "mapsOS session start"


def _normalize_role(role: str | None) -> str:
    normalized = str(role or "").strip().lower()
    if normalized in {"", "default", "maps", "surface", "intake"}:
        return "intake"
    if normalized in {"librarian", "sysadmin", "maintainer", "ops"}:
        return "librarian"
    return "intake"


def _safe_future_result(
    name: str,
    future: Any,
    *,
    fallback: Any,
    sources: dict[str, dict[str, Any]],
    degradation_reasons: list[str],
    timeout: float = _SESSION_START_TIMEOUT,
) -> Any:
    try:
        value = future.result(timeout=timeout)
    except Exception as exc:
        sources[name] = {
            "ok": False,
            "degraded": True,
            "error": type(exc).__name__,
        }
        degradation_reasons.append(f"{name} unavailable")
        return fallback
    sources[name] = {
        "ok": True,
        "degraded": False,
    }
    return value


def _state_guidance(state_tag: str, arcs: list[dict[str, Any]]) -> dict[str, Any]:
    from .roles import ARC_MODE_HINTS, MODE_PROFILES, STATE_MODE_MAP

    mode, energy = STATE_MODE_MAP.get(state_tag, ("low-demand", "Low"))
    profile = MODE_PROFILES.get(mode, {})
    arc_hints: list[dict[str, str]] = []
    for arc in arcs[:4]:
        name = str(arc.get("name") or "").strip()
        if not name:
            continue
        hint = ARC_MODE_HINTS.get(name)
        if not hint:
            continue
        arc_hints.append(
            {
                "arc": name,
                "severity": str(arc.get("severity") or ""),
                "hint": hint,
            }
        )
    return {
        "mode": mode,
        "energy": energy,
        "description": str(profile.get("description") or ""),
        "nd_note": str(profile.get("nd_note") or ""),
        "suspend": list(profile.get("suspend") or []),
        "arc_hints": arc_hints,
    }


def _role_context(
    *,
    role: str,
    state_tag: str,
    arcs: list[dict[str, Any]],
    bridge: dict[str, Any],
    cart_doctor: dict[str, Any],
    degraded: bool,
    degradation_reasons: list[str],
) -> dict[str, Any]:
    state_guidance = _state_guidance(state_tag, arcs)
    if role == "librarian":
        instructions = [
            "stabilize bridge and durable memory surfaces before doing synthesis work",
            "verify recalled operational facts against live service or filesystem state before acting",
            "treat bridge warnings as maintenance tasks, not background noise",
        ]
        load_refs = [
            "bridge health",
            "cart doctor warnings",
            "recent session notes",
            "daily brief",
        ]
        priority = (
            "recover degraded services first"
            if degraded
            else "maintain bridge, atlas, and session hygiene"
        )
    else:
        instructions = [
            "orient to current state, arcs, body, and intention context first",
            "draft reviewable synthesis and relation candidates instead of hardening facts silently",
            "defer infrastructure debugging unless the session packet is degraded",
        ]
        load_refs = [
            "state + arc summary",
            "body + intention context",
            "recent sessions",
            "daily brief",
        ]
        priority = (
            "continue intake, but acknowledge degraded context explicitly"
            if degraded
            else "qualitative intake and surfaced context"
        )
    return {
        "role": role,
        "priority": priority,
        "load_refs": load_refs,
        "instructions": instructions,
        "state_guidance": state_guidance,
        "bridge_warnings": list(bridge.get("warnings") or []),
        "cart_warnings": list(cart_doctor.get("warnings") or []),
        "degradation_reasons": degradation_reasons,
    }


def _collect_entries(prefix: str, *, limit: int, days: int | None = None, graph: str = "cassette") -> list[dict[str, Any]]:
    recalled, _source = recall_resilient(prefix, graph=graph, limit=limit)
    normalized = [
        _normalized_entry(raw, fallback_id=index + 1)
        for index, raw in enumerate(recalled)
        if isinstance(raw, dict) and str(raw.get("content") or "").startswith(prefix)
    ]
    normalized.sort(key=_entry_sort_key)

    if days is None:
        return normalized

    today = date.today()
    filtered: list[dict[str, Any]] = []
    for entry in normalized:
        parsed_date = _parse_entry_date(entry["content"])
        if parsed_date is None:
            continue
        if (today - parsed_date).days <= days:
            filtered.append(entry)
    return filtered


def check_payload(*, graph: str = "cassette") -> dict[str, Any]:
    with ThreadPoolExecutor(max_workers=len(_CHECK_TRACKS)) as executor:
        futures = {
            prefix: executor.submit(_collect_entries, prefix, limit=limit, graph=graph)
            for prefix, limit in _CHECK_TRACKS
        }
        states = futures["STATE:"].result()
        body = futures["BODY:"].result()
        mind = futures["MIND:"].result()
        spirit = futures["SPIRIT:"].result()
        intentions = futures["INTENTION:"].result()
        flash = futures["FLASH:"].result()

    arcs = weave(
        states,
        body,
        mind,
        spirit,
        intentions,
        flash_entries=flash,
    )
    survival = eval_survival(states)
    return {
        "state": states[-1] if states else None,
        "arcs": [
            {"name": arc.name, "severity": arc.severity, "message": arc.message}
            for arc in arcs
        ],
        "survival": bool(getattr(survival, "active", False)),
    }


def session_start_payload(*, graph: str = "cassette", role: str = "intake") -> dict[str, Any]:
    from .cart_bridge import (
        bridge_health,
        get_doctor_payload,
        get_daily_brief,
        get_open_tasks,
        get_recent_sessions,
    )

    normalized_role = _normalize_role(role)
    sources: dict[str, dict[str, Any]] = {}
    degradation_reasons: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as executor:
        future_check = executor.submit(check_payload, graph=graph)
        future_body = executor.submit(_collect_entries, "BODY:", limit=21, days=7, graph=graph)
        future_intentions = executor.submit(_collect_entries, "INTENTION:", limit=28, days=21, graph=graph)
        future_flash = executor.submit(_collect_entries, "FLASH:", limit=10, graph=graph)
        future_p0 = executor.submit(get_open_tasks, "P0")
        future_p1 = executor.submit(get_open_tasks, "P1")
        future_sessions = executor.submit(get_recent_sessions, 5)
        future_daily_brief = executor.submit(get_daily_brief)
        future_bridge = executor.submit(bridge_health)
        future_cart_doctor = executor.submit(get_doctor_payload)

        check = _safe_future_result(
            "check",
            future_check,
            fallback={"state": None, "arcs": [], "survival": False},
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        body_entries = _safe_future_result(
            "body",
            future_body,
            fallback=[],
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        intention_entries = _safe_future_result(
            "intentions",
            future_intentions,
            fallback=[],
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        flash_entries = _safe_future_result(
            "flash",
            future_flash,
            fallback=[],
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        p0_tasks = _safe_future_result(
            "cart_tasks_p0",
            future_p0,
            fallback=[],
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        p1_tasks = _safe_future_result(
            "cart_tasks_p1",
            future_p1,
            fallback=[],
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        recent_sessions = _safe_future_result(
            "cart_sessions",
            future_sessions,
            fallback=[],
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        daily_brief = _safe_future_result(
            "daily_brief",
            future_daily_brief,
            fallback="",
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        bridge = _safe_future_result(
            "cart_bridge",
            future_bridge,
            fallback={
                "available": False,
                "doctor": False,
                "tasks": False,
                "sessions": False,
                "warnings": ["cart bridge unavailable"],
            },
            sources=sources,
            degradation_reasons=degradation_reasons,
        )
        cart_doctor = _safe_future_result(
            "cart_doctor",
            future_cart_doctor,
            fallback={"available": False, "warnings": ["cart doctor unavailable"]},
            sources=sources,
            degradation_reasons=degradation_reasons,
        )

    if not bridge.get("available"):
        degradation_reasons.append("cart bridge unavailable")
    if not bridge.get("doctor"):
        degradation_reasons.append("cart doctor unavailable")
    if not bridge.get("tasks"):
        degradation_reasons.append("cart task surface unavailable")
    if not bridge.get("sessions"):
        degradation_reasons.append("cart session surface unavailable")
    degraded = bool(degradation_reasons)
    state_tag = _state_tag(check.get("state"))
    role_context = _role_context(
        role=normalized_role,
        state_tag=state_tag,
        arcs=list(check.get("arcs") or []),
        bridge=bridge,
        cart_doctor=cart_doctor,
        degraded=degraded,
        degradation_reasons=sorted(set(degradation_reasons)),
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "role": normalized_role,
        "degraded": degraded,
        "degradation_reasons": sorted(set(degradation_reasons)),
        "sources": sources,
        "state": check.get("state"),
        "state_tag": state_tag,
        "summary": _session_summary(check),
        "arcs": check.get("arcs") or [],
        "survival": bool(check.get("survival")),
        "body": _latest_body_state(body_entries),
        "intentions": _latest_intention_state(intention_entries),
        "flash": _flash_texts(flash_entries),
        "role_context": role_context,
        "cart": {
            "bridge": bridge,
            "doctor": cart_doctor,
            "tasks": {
                "p0": p0_tasks,
                "p1": p1_tasks,
            },
            "recent_sessions": recent_sessions,
            "daily_brief": daily_brief,
        },
    }


def trend_payload(*, days: int = 30, graph: str = "cassette") -> dict[str, Any]:
    return {"entries": _collect_entries("STATE:", limit=max(days * 8, 240), days=days, graph=graph), "days": days}


def body_payload(*, days: int = 7, graph: str = "cassette") -> dict[str, Any]:
    return {"entries": _collect_entries("BODY:", limit=max(days * 8, 120), days=days, graph=graph), "days": days}


def intentions_payload(*, days: int = 7, graph: str = "cassette") -> dict[str, Any]:
    return {"entries": _collect_entries("INTENTION:", limit=max(days * 8, 120), days=days, graph=graph), "days": days}


def flash_payload(*, limit: int = 10, graph: str = "cassette") -> dict[str, Any]:
    return {"entries": _collect_entries("FLASH:", limit=max(limit, 10), graph=graph)[-limit:]}


def vent_payload(text: str, *, log_date: str | None = None, graph: str = "cassette") -> dict[str, Any]:
    if not text.strip():
        raise ValueError("text is required")

    entries = parse_vent(text, log_date=log_date or date.today().isoformat())
    written: list[dict[str, Any]] = []
    for entry in entries:
        content = entry.to_garden()
        row_id = write(content, graph=graph)
        written.append(
            {
                "content": content,
                "ts": f"{entry.date}T00:00:00Z",
                "id": row_id,
            }
        )

    return {"entries": written, "count": len(written)}


def log_payload(content: str, *, graph: str = "cassette") -> dict[str, Any]:
    if not content.strip():
        raise ValueError("content is required")
    row_id = write(content.strip(), graph=graph)
    return {"id": row_id, "dest": "local"}


def flash_post_payload(text: str, *, graph: str = "cassette", log_date: str | None = None) -> dict[str, Any]:
    if not text.strip():
        raise ValueError("text is required")
    content = f"FLASH: {log_date or date.today().isoformat()} | {text.strip()}"
    row_id = write(content, graph=graph)
    return {"id": row_id}


def build_app() -> "FastAPI":
    if not _FASTAPI_AVAILABLE:  # pragma: no cover - dependency guard
        raise RuntimeError("fastapi is not installed")

    app = FastAPI(title="mapsOS", version=VERSION)

    def _require_token(authorization: str | None) -> None:
        try:
            validate_bearer_token(authorization)
        except ServeAuthError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    @app.get("/health")
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": VERSION}

    @app.get("/check")
    def check(authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        return check_payload()

    @app.get("/session-start")
    def session_start(
        role: str | None = None,
        authorization: str | None = Header(default=None),
        x_maps_role: str | None = Header(default=None, alias="X-Maps-Role"),
    ) -> dict[str, Any]:
        _require_token(authorization)
        return session_start_payload(role=x_maps_role or role or "intake")

    @app.get("/trend")
    def trend(days: int = 30, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        return trend_payload(days=days)

    @app.get("/body")
    def body(days: int = 7, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        return body_payload(days=days)

    @app.get("/intentions")
    def intentions(days: int = 7, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        return intentions_payload(days=days)

    @app.get("/flash")
    def flash(limit: int = 10, authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        return flash_payload(limit=limit)

    @app.post("/vent")
    def vent(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        try:
            return vent_payload(
                str(body.get("text") or ""),
                log_date=str(body.get("date") or "").strip() or None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/log")
    def log(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        try:
            return log_payload(str(body.get("content") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/flash")
    def create_flash(body: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        _require_token(authorization)
        try:
            return flash_post_payload(str(body.get("text") or ""))
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def run(*, host: str = "0.0.0.0", port: int = 7432) -> None:
    if not _FASTAPI_AVAILABLE:
        raise SystemExit(
            "maps serve requires fastapi + uvicorn:\n"
            "  pip install -r requirements-optional.txt"
        )
    if not os.environ.get(TOKEN_ENV, "").strip():
        raise SystemExit(
            f"Refusing to start: set {TOKEN_ENV} first.\n"
            f"  export {TOKEN_ENV}=$(openssl rand -hex 32)"
        )

    uvicorn.run(build_app(), host=host, port=port, log_level="warning")
