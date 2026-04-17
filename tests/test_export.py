# maps · cassette.help · MIT
"""Tests for cartographer closed-loop export helpers."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from environments import export as export_mod


def test_build_session_export_collects_recent_state_body_goals_and_arcs(monkeypatch):
    recalled = {
        "STATE:": [{"content": "STATE: 2026-04-17 | stable | shipped phase 3"}],
        "BODY:": [
            {"content": "BODY: 2026-04-17 | sleep | ok | slept enough"},
            {"content": "BODY: 2026-04-17 | energy | medium | not terrible"},
        ],
        "MIND:": [],
        "SPIRIT:": [],
        "INTENTION:": [{"content": "INTENTION: water | met | 2026-04-17 | good enough"}],
        "FLASH:": [],
        "DECISION:": [],
        "TRIGGER:": [],
        "GOAL:": [{"content": "GOAL: 2026-04-17 | ship phase 3 | 2026-04-18 | open"}],
        "PERSON:": [],
        "RESISTANCE:": [],
    }

    monkeypatch.setattr(
        export_mod,
        "weave",
        lambda *args, **kwargs: [SimpleNamespace(name="income", message="invoice pressure remains")],
    )

    payload = export_mod.build_session_export(
        graph="cassette",
        recall_fn=lambda prefix, graph, limit: recalled[prefix],
    )

    assert payload["state"] == "stable"
    assert payload["body"]["sleep"] == "ok"
    assert payload["body"]["energy"] == "medium"
    assert payload["arcs"] == ["income"]
    assert payload["intentions"] == ["water"]
    assert payload["tasks"][0]["title"] == "ship phase 3"
    assert payload["summary"] == "shipped phase 3"


def test_load_atlas_task_hints_parses_open_cartographer_tasks(tmp_path: Path):
    tasks_path = tmp_path / "mapsos.md"
    tasks_path.write_text(
        '# mapsOS Tasks\n\n'
        '<!-- cart:block id="m123" type="task" source="mapsos" source_id="arc-1" -->\n'
        '- [ ] send invoice\n'
        '  status: open\n'
        '  priority: P0\n'
        '  due: 2026-04-18\n'
        '<!-- /cart:block -->\n\n'
        '<!-- cart:block id="m124" type="task" source="mapsos" source_id="arc-2" -->\n'
        '- [x] archived task\n'
        '  status: done\n'
        '<!-- /cart:block -->\n',
        encoding="utf-8",
    )

    tasks = export_mod.load_atlas_task_hints(tasks_path)

    assert len(tasks) == 1
    assert tasks[0]["title"] == "send invoice"
    assert tasks[0]["due"] == "2026-04-18"
