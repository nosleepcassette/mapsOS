# maps · cassette.help · MIT
"""Tests for persisted arc cooldown behavior."""

import json
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments import arc_cooldown
from environments.pattern_weaver import weave


def _state(tag: str) -> dict:
    return {"content": f"STATE: 2026-04-10 | {tag} | note"}


def _body(category: str, status: str) -> dict:
    return {"content": f"BODY: 2026-04-10 | {category} | {status} | note"}


def _mind(category: str, status: str) -> dict:
    return {"content": f"MIND: 2026-04-10 | {category} | {status} | note"}


def test_arc_not_in_cooldowns_still_fires(tmp_path, monkeypatch):
    path = tmp_path / "cooldowns.json"
    monkeypatch.setattr(arc_cooldown, "cooldown_path", lambda: path)

    arcs = weave(
        [_state("manic")],
        [_body("sleep", "none")],
        [_mind("flow", "high")],
        [],
        [],
        apply_cooldown=True,
    )

    names = [arc.name for arc in arcs]
    assert "manic_spike" in names

    stored = json.loads(path.read_text(encoding="utf-8"))
    assert stored["manic_spike"] == date.today().isoformat()


def test_arc_in_cooldown_fires_when_window_expired(tmp_path, monkeypatch):
    path = tmp_path / "cooldowns.json"
    expired = (date.today() - timedelta(days=2)).isoformat()
    path.write_text(json.dumps({"manic_spike": expired}), encoding="utf-8")
    monkeypatch.setattr(arc_cooldown, "cooldown_path", lambda: path)

    arcs = weave(
        [_state("manic")],
        [_body("sleep", "none")],
        [_mind("flow", "high")],
        [],
        [],
        apply_cooldown=True,
    )

    names = [arc.name for arc in arcs]
    assert "manic_spike" in names


def test_arc_in_cooldown_is_suppressed(tmp_path, monkeypatch):
    path = tmp_path / "cooldowns.json"
    path.write_text(
        json.dumps({"manic_spike": date.today().isoformat()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(arc_cooldown, "cooldown_path", lambda: path)

    arcs = weave(
        [_state("manic")],
        [_body("sleep", "none")],
        [_mind("flow", "high")],
        [],
        [],
        apply_cooldown=True,
    )

    names = [arc.name for arc in arcs]
    assert "manic_spike" not in names


def test_survival_arcs_are_never_suppressed(tmp_path, monkeypatch):
    path = tmp_path / "cooldowns.json"
    path.write_text(
        json.dumps({"state_dip_holding": date.today().isoformat()}),
        encoding="utf-8",
    )
    monkeypatch.setattr(arc_cooldown, "cooldown_path", lambda: path)
    monkeypatch.setitem(arc_cooldown.ARC_COOLDOWNS, "state_dip_holding", 7)

    arcs = weave(
        [_state("depleted"), _state("depleted"), _state("grieving")],
        [],
        [],
        [],
        [],
        apply_cooldown=True,
    )

    names = [arc.name for arc in arcs]
    assert "state_dip_holding" in names
