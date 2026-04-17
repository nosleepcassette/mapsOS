# maps · cassette.help · MIT
"""Optional HTTP server exposing mapsOS helpers over FastAPI."""

from __future__ import annotations

import os
import re
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
    states = _collect_entries("STATE:", limit=14, graph=graph)
    body = _collect_entries("BODY:", limit=14, graph=graph)
    mind = _collect_entries("MIND:", limit=14, graph=graph)
    spirit = _collect_entries("SPIRIT:", limit=14, graph=graph)
    intentions = _collect_entries("INTENTION:", limit=21, graph=graph)
    flash = _collect_entries("FLASH:", limit=14, graph=graph)

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
