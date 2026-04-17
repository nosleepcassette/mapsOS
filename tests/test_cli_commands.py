# maps · cassette.help · MIT
"""CLI regression tests for schema-aware command behavior."""

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace
from datetime import datetime as real_datetime
from importlib.machinery import SourceFileLoader

sys.path.insert(0, str(Path(__file__).parent.parent))

_MAPS_PATH = Path(__file__).parent.parent / "bin" / "maps"
_LOADER = SourceFileLoader("maps_cli", str(_MAPS_PATH))
_SPEC = importlib.util.spec_from_loader("maps_cli", _LOADER)
maps_cli = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(maps_cli)


def test_goal_list_uses_status_field_and_latest_entry(monkeypatch, capsys):
    entries = [
        {"content": "GOAL: 2026-04-10 | finish taxes | 2026-04-15 | done"},
        {"content": "GOAL: 2026-04-01 | finish taxes | 2026-04-15 | open"},
        {"content": "GOAL: 2026-04-02 | book dentist | none | open"},
    ]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)

    args = SimpleNamespace(
        list=True,
        done=None,
        goal=[],
        due=None,
        graph="cassette",
        dry_run=False,
    )
    rc = maps_cli.cmd_goal(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "book dentist" in out
    assert "finish taxes" not in out


def test_goal_done_preserves_due_field(monkeypatch, capsys):
    remembered = []
    entries = [{"content": "GOAL: 2026-04-01 | finish taxes | 2026-04-15 | open"}]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)
    monkeypatch.setattr(maps_cli, "_remember", lambda content, **kwargs: remembered.append(content))
    monkeypatch.setattr(maps_cli, "_today", lambda: "2026-04-10")

    args = SimpleNamespace(
        list=False,
        done=["taxes"],
        goal=[],
        due=None,
        graph="cassette",
        dry_run=False,
    )
    rc = maps_cli.cmd_goal(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert remembered == ["GOAL: 2026-04-10 | finish taxes | 2026-04-15 | done"]
    assert "goal marked done: finish taxes" in out


def test_goal_update_preserves_due_field_and_sets_in_progress(monkeypatch, capsys):
    remembered = []
    entries = [{"content": "GOAL: 2026-04-01 | finish taxes | 2026-04-15 | open"}]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)
    monkeypatch.setattr(
        maps_cli,
        "_remember",
        lambda content, **kwargs: remembered.append(content),
    )
    monkeypatch.setattr(maps_cli, "_today", lambda: "2026-04-10")

    args = SimpleNamespace(
        list=False,
        done=None,
        update=["taxes"],
        goal=[],
        due=None,
        graph="cassette",
        dry_run=False,
    )
    rc = maps_cli.cmd_goal(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert remembered == ["GOAL: 2026-04-10 | finish taxes | 2026-04-15 | in_progress"]
    assert "goal updated: in_progress" in out


def test_group_wins_by_week_keeps_related_entries_together():
    wins = [
        maps_cli._parse_win_entry("WIN: 2026-04-10 | shipped parser fixes"),
        maps_cli._parse_win_entry("WIN: 2026-04-08 | finished stage 6"),
        maps_cli._parse_win_entry("WIN: 2026-03-28 | survived hard week"),
    ]

    grouped = maps_cli._group_wins_by_week([w for w in wins if w is not None])

    assert len(grouped) == 2
    assert [item["note"] for item in grouped[0][1]] == [
        "shipped parser fixes",
        "finished stage 6",
    ]
    assert [item["note"] for item in grouped[1][1]] == ["survived hard week"]


def test_wins_week_filters_to_current_iso_week(monkeypatch, capsys):
    entries = [
        {"content": "WIN: 2026-04-10 | fixed cli schema"},
        {"content": "WIN: 2026-04-07 | added person command"},
        {"content": "WIN: 2026-03-29 | older win"},
    ]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)

    args = SimpleNamespace(
        graph="cassette",
        week=True,
        month=False,
        date="2026-04-10",
    )
    rc = maps_cli.cmd_wins(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "fixed cli schema" in out
    assert "added person command" in out
    assert "older win" not in out


def test_summarize_eval_counts_partial_as_half_credit():
    intentions = [
        {"content": "INTENTION: water | met | 2026-04-10 | note"},
        {"content": "INTENTION: movement | partial | 2026-04-09 | note"},
        {"content": "INTENTION: email | missed | 2026-04-08 | note"},
        {"content": "INTENTION: sleep | met | 2026-04-07 | note"},
    ]
    states = [
        {"content": "STATE: 2026-04-10 | stable | note"},
        {"content": "STATE: 2026-04-09 | depleted | note"},
        {"content": "STATE: 2026-04-08 | stable | note"},
    ]

    summary = maps_cli._summarize_eval(
        intentions,
        states,
        today=real_datetime(2026, 4, 10).date(),
        days=7,
    )

    assert summary["intentions_total"] == 4
    assert abs(summary["met_rate"] - 0.625) < 1e-9
    assert summary["state_counts"]["stable"] == 2
    assert summary["state_counts"]["depleted"] == 1


def test_summarize_eval_filters_entries_outside_window():
    intentions = [
        {"content": "INTENTION: water | met | 2026-04-10 | note"},
        {"content": "INTENTION: old | missed | 2026-03-01 | note"},
    ]
    states = [
        {"content": "STATE: 2026-04-10 | thriving | note"},
        {"content": "STATE: 2026-03-01 | depleted | note"},
    ]

    summary = maps_cli._summarize_eval(
        intentions,
        states,
        today=real_datetime(2026, 4, 10).date(),
        days=7,
    )

    assert summary["intentions_total"] == 1
    assert summary["intention_counts"]["met"] == 1
    assert "missed" not in summary["intention_counts"]
    assert summary["state_counts"] == {"thriving": 1}


def test_events_reads_stored_event_schema(monkeypatch, capsys):
    entries = [{"content": "EVENT: 2026-04-10 | 2099-04-15 | therapy on tuesday"}]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)

    args = SimpleNamespace(graph="cassette", week=False)
    rc = maps_cli.cmd_events(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "2099-04-15" in out
    assert "therapy on tuesday" in out


def test_events_week_filters_future_items(monkeypatch, capsys):
    entries = [
        {"content": "EVENT: 2026-04-10 | 2099-04-15 | near term"},
        {"content": "EVENT: 2026-04-10 | 2099-05-15 | far term"},
    ]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)

    class _FakeDateTime:
        @classmethod
        def now(cls):
            return real_datetime(2099, 4, 10)

        @classmethod
        def strptime(cls, *args, **kwargs):
            return real_datetime.strptime(*args, **kwargs)

    import sys as _sys

    dt_module = _sys.modules["datetime"]
    monkeypatch.setattr(dt_module, "datetime", _FakeDateTime)

    args = SimpleNamespace(graph="cassette", week=True)
    rc = maps_cli.cmd_events(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "near term" in out
    assert "far term" not in out


def test_check_passes_new_entry_types_to_weave(monkeypatch):
    recalled = {
        "STATE:": [{"content": "STATE: 2026-04-10 | stable | note"}],
        "BODY:": [],
        "MIND:": [],
        "SPIRIT:": [],
        "INTENTION:": [],
        "FLASH:": [],
        "DECISION:": [{"content": "DECISION: 2026-04-10 | leave?"}],
        "TRIGGER:": [{"content": "TRIGGER: 2026-04-10 | text from alex | reaction"}],
        "GOAL:": [{"content": "GOAL: 2026-04-01 | finish taxes | none | open"}],
        "PERSON:": [{"content": "PERSON: 2026-04-10 | alex | check-in | negative"}],
        "RESISTANCE:": [{"content": "RESISTANCE: 2026-04-10 | starting taxes | high"}],
    }
    captured = {}

    def fake_recall(prefix, graph, limit):
        return recalled[prefix]

    def fake_weave(*args, **kwargs):
        captured["kwargs"] = kwargs
        return []

    monkeypatch.setattr(maps_cli, "_recall", fake_recall)
    monkeypatch.setattr(
        maps_cli,
        "eval_survival",
        lambda entries: SimpleNamespace(active=False),
    )
    monkeypatch.setattr(maps_cli, "weave", fake_weave)
    monkeypatch.setattr(maps_cli, "count_pending", lambda graph: 0)

    args = SimpleNamespace(graph="cassette")
    rc = maps_cli.cmd_check(args, quiet=True)

    assert rc == 0
    assert captured["kwargs"]["decision_entries"] == recalled["DECISION:"]
    assert captured["kwargs"]["trigger_entries"] == recalled["TRIGGER:"]
    assert captured["kwargs"]["goal_entries"] == recalled["GOAL:"]
    assert captured["kwargs"]["person_entries"] == recalled["PERSON:"]
    assert captured["kwargs"]["resistance_entries"] == recalled["RESISTANCE:"]


def test_person_list_uses_known_people_order_and_last_contact(monkeypatch, capsys):
    entries = [
        {"content": "PERSON: 2026-04-08 | maggie | support group plans | positive"},
        {"content": "PERSON: 2026-04-02 | maggie | checked in briefly | neutral"},
        {"content": "PERSON: 2026-03-15 | sarah | coffee | positive"},
    ]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)
    monkeypatch.setattr(maps_cli, "known_people", lambda: ["maggie", "sarah", "chris"])
    monkeypatch.setattr(
        maps_cli,
        "person_context",
        lambda name: {
            "maggie": {"role": "ex, support"},
            "sarah": {"role": "crush"},
            "chris": {"role": "colleague"},
        }.get(name, {}),
    )

    args = SimpleNamespace(
        graph="cassette", list=True, init_astrolog=False, name=[], dry_run=False
    )
    rc = maps_cli.cmd_person(args)
    out_lines = capsys.readouterr().out.strip().splitlines()

    assert rc == 0
    assert out_lines[0].startswith("maggie")
    assert "2026-04-08" in out_lines[0]
    assert out_lines[1].startswith("sarah")
    assert "2026-03-15" in out_lines[1]
    assert out_lines[2].startswith("chris")
    assert "no contacts logged" in out_lines[2]


def test_person_list_includes_people_seen_only_in_garden(monkeypatch, capsys):
    entries = [{"content": "PERSON: 2026-04-08 | alex | check-in | positive"}]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)
    monkeypatch.setattr(maps_cli, "known_people", lambda: [])
    monkeypatch.setattr(maps_cli, "person_context", lambda name: {})

    args = SimpleNamespace(
        graph="cassette", list=True, init_astrolog=False, name=[], dry_run=False
    )
    rc = maps_cli.cmd_person(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "alex" in out
    assert "2026-04-08" in out


def test_person_profile_matches_exact_name_not_prefix(monkeypatch, capsys):
    entries = [
        {"content": "PERSON: 2026-04-08 | emma | slo context | positive"},
        {"content": "PERSON: 2026-04-09 | emma-x | sf context | neutral"},
    ]
    monkeypatch.setattr(maps_cli, "_recall", lambda *args, **kwargs: entries)
    monkeypatch.setattr(
        maps_cli,
        "person_context",
        lambda name: {
            "emma": {"role": "maggie's connection", "notes": "SLO"},
            "emma-x": {"role": "friend, neighbor", "notes": "SF"},
        }.get(name, {}),
    )
    monkeypatch.setattr(
        maps_cli,
        "_astrolog_profile_path",
        lambda name: Path("/tmp") / f"{name}.json",
    )

    args = SimpleNamespace(
        graph="cassette", list=False, init_astrolog=False, name=["emma"], dry_run=False
    )
    rc = maps_cli.cmd_person(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "maggie's connection" in out
    assert "slo context" in out
    assert "sf context" not in out


def test_check_prints_loaded_brief_and_atlas_carry_over(monkeypatch, capsys):
    recalled = {
        "STATE:": [{"content": "STATE: 2026-04-17 | stable | note"}],
        "BODY:": [],
        "MIND:": [],
        "SPIRIT:": [],
        "INTENTION:": [],
        "FLASH:": [],
        "DECISION:": [],
        "TRIGGER:": [],
        "GOAL:": [],
        "PERSON:": [],
        "RESISTANCE:": [],
    }
    monkeypatch.setattr(maps_cli, "_recall", lambda prefix, graph, limit: recalled[prefix])
    monkeypatch.setattr(
        maps_cli,
        "eval_survival",
        lambda entries: SimpleNamespace(active=False),
    )
    monkeypatch.setattr(maps_cli, "weave", lambda *args, **kwargs: [])
    monkeypatch.setattr(maps_cli, "count_pending", lambda graph: 0)
    monkeypatch.setattr(maps_cli, "load_brief_text", lambda path: "# atlas brief\n\n- ship phase 3")
    monkeypatch.setattr(
        maps_cli,
        "load_atlas_task_hints",
        lambda: [{"title": "send invoice", "due": "2026-04-18"}],
    )

    args = SimpleNamespace(graph="cassette", role=False, load_brief="~/atlas/daily/brief.md")
    rc = maps_cli.cmd_check(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "atlas brief:" in out
    assert "ship phase 3" in out
    assert "atlas carry-over:" in out
    assert "send invoice due 2026-04-18" in out


def test_cmd_export_reports_written_path(monkeypatch, capsys):
    monkeypatch.setattr(
        maps_cli,
        "write_session_export",
        lambda **kwargs: Path("/tmp/session_20260417_120000.json"),
    )
    args = SimpleNamespace(graph="cassette", load_brief=None)
    rc = maps_cli.cmd_export(args)
    out = capsys.readouterr().out

    assert rc == 0
    assert "session_20260417_120000.json" in out
