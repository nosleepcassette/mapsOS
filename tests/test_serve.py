# maps · cassette.help · MIT
from __future__ import annotations

from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

from environments import serve


def test_health_noauth():
    client = TestClient(serve.build_app())

    response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_check_requires_token(monkeypatch):
    monkeypatch.setenv("MAPS_SERVE_TOKEN", "secret")
    monkeypatch.setattr(
        serve,
        "check_payload",
        lambda graph="cassette": {"state": None, "arcs": [], "survival": False},
    )
    client = TestClient(serve.build_app())

    assert client.get("/check").status_code == 401
    assert client.get("/check", headers={"Authorization": "Bearer wrong"}).status_code == 401
    ok = client.get("/check", headers={"Authorization": "Bearer secret"})

    assert ok.status_code == 200
    assert ok.json() == {"state": None, "arcs": [], "survival": False}


def test_vent_payload_parses_and_writes(monkeypatch):
    writes: list[tuple[str, str]] = []

    class _Entry:
        def __init__(self, text: str, entry_date: str = "2026-04-17"):
            self._text = text
            self.date = entry_date

        def to_garden(self) -> str:
            return self._text

    monkeypatch.setattr(
        serve,
        "parse_vent",
        lambda text, log_date=None: [_Entry("STATE: 2026-04-17 | stable | testing")],
    )
    monkeypatch.setattr(
        serve,
        "write",
        lambda content, graph="cassette": writes.append((content, graph)) or 7,
    )

    payload = serve.vent_payload("testing", log_date="2026-04-17", graph="cassette")

    assert writes == [("STATE: 2026-04-17 | stable | testing", "cassette")]
    assert payload == {
        "entries": [
            {
                "content": "STATE: 2026-04-17 | stable | testing",
                "ts": "2026-04-17T00:00:00Z",
                "id": 7,
            }
        ],
        "count": 1,
    }


def test_check_payload_shapes_entries(monkeypatch):
    recalled = {
        "STATE:": [{"content": "STATE: 2026-04-16 | clear | note", "id": 2, "ts": "2026-04-16T03:00:00Z"}],
        "BODY:": [],
        "MIND:": [],
        "SPIRIT:": [],
        "INTENTION:": [],
        "FLASH:": [],
    }

    monkeypatch.setattr(
        serve,
        "recall_resilient",
        lambda prefix, graph="cassette", limit=7: (recalled[prefix], "local"),
    )
    monkeypatch.setattr(
        serve,
        "weave",
        lambda *args, **kwargs: [SimpleNamespace(name="test_arc", severity="insight", message="hello")],
    )
    monkeypatch.setattr(serve, "eval_survival", lambda entries: SimpleNamespace(active=False))

    payload = serve.check_payload()

    assert payload == {
        "state": {"content": "STATE: 2026-04-16 | clear | note", "ts": "2026-04-16T03:00:00Z", "id": 2},
        "arcs": [{"name": "test_arc", "severity": "insight", "message": "hello"}],
        "survival": False,
    }
