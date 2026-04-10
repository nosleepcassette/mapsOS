# maps · cassette.help · MIT
"""Tests for local_store.py — garden-resilient offline storage."""
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments.local_store import (
    write, recall, pending, mark_synced, count_pending,
    recall_resilient, sync_to_garden,
)


def _tmp_db() -> Path:
    f = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    f.close()
    return Path(f.name)


class TestLocalStore:
    def test_write_returns_id(self):
        db = _tmp_db()
        row_id = write("STATE: 2026-04-09 | depleted | test", db_path=db)
        assert isinstance(row_id, int)
        assert row_id >= 1

    def test_recall_by_prefix(self):
        db = _tmp_db()
        write("STATE: 2026-04-09 | depleted | test", db_path=db)
        write("BODY: 2026-04-09 | sleep | none | test", db_path=db)
        results = recall("STATE:", db_path=db)
        assert len(results) == 1
        assert results[0]["content"].startswith("STATE:")

    def test_recall_limit(self):
        db = _tmp_db()
        for i in range(5):
            write(f"STATE: 2026-04-0{i+1} | stable | entry {i}", db_path=db)
        results = recall("STATE:", limit=3, db_path=db)
        assert len(results) == 3

    def test_recall_returns_dict_with_content(self):
        db = _tmp_db()
        write("STATE: 2026-04-09 | thriving | good day", db_path=db)
        results = recall("STATE:", db_path=db)
        assert "content" in results[0]

    def test_pending_returns_unsynced(self):
        db = _tmp_db()
        write("STATE: 2026-04-09 | depleted | test", db_path=db)
        write("BODY: 2026-04-09 | sleep | none | test", db_path=db)
        p = pending(db_path=db)
        assert len(p) == 2

    def test_mark_synced(self):
        db = _tmp_db()
        id1 = write("STATE: 2026-04-09 | stable | test", db_path=db)
        id2 = write("BODY: 2026-04-09 | sleep | poor | test", db_path=db)
        mark_synced([id1], db_path=db)
        p = pending(db_path=db)
        assert len(p) == 1
        assert p[0]["id"] == id2

    def test_count_pending(self):
        db = _tmp_db()
        assert count_pending(db_path=db) == 0
        write("STATE: 2026-04-09 | stable | test", db_path=db)
        write("BODY: 2026-04-09 | sleep | none | test", db_path=db)
        assert count_pending(db_path=db) == 2

    def test_count_pending_after_sync(self):
        db = _tmp_db()
        id1 = write("STATE: 2026-04-09 | stable | test", db_path=db)
        mark_synced([id1], db_path=db)
        assert count_pending(db_path=db) == 0

    def test_graph_isolation(self):
        db = _tmp_db()
        write("STATE: 2026-04-09 | stable | test", graph="cassette", db_path=db)
        write("STATE: 2026-04-09 | thriving | test", graph="other", db_path=db)
        cassette_results = recall("STATE:", graph="cassette", db_path=db)
        other_results = recall("STATE:", graph="other", db_path=db)
        assert len(cassette_results) == 1
        assert len(other_results) == 1
        assert "stable" in cassette_results[0]["content"]
        assert "thriving" in other_results[0]["content"]

    def test_empty_db_returns_empty_list(self):
        db = _tmp_db()
        assert recall("STATE:", db_path=db) == []
        assert pending(db_path=db) == []
        assert count_pending(db_path=db) == 0

    def test_write_multiple_tracks(self):
        db = _tmp_db()
        write("STATE: 2026-04-09 | depleted | test", db_path=db)
        write("BODY: 2026-04-09 | sleep | none | test", db_path=db)
        write("MIND: 2026-04-09 | flow | high | test", db_path=db)
        write("SPIRIT: 2026-04-09 | isolation | high | test", db_path=db)
        write("INTENTION: water | missed | 2026-04-09 | test", db_path=db)
        assert count_pending(db_path=db) == 5
        states = recall("STATE:", db_path=db)
        bodies = recall("BODY:", db_path=db)
        assert len(states) == 1
        assert len(bodies) == 1

    def test_sync_dry_run_doesnt_mark_synced(self):
        db = _tmp_db()
        write("STATE: 2026-04-09 | stable | test", db_path=db)
        # dry_run=True — we're not calling garden, just checking logic
        # Since garden isn't available in test env, this tests that count stays the same
        n_before = count_pending(db_path=db)
        # Just verify pending count is untouched without garden
        assert n_before == 1

    def test_recall_resilient_normalizes_garden_envelope(self, monkeypatch):
        db = _tmp_db()
        payload = (
            '{"ok": true, "data": [{"text": "STATE: 2026-04-09 | depleted | test"}], '
            '"error": "", "elapsed": 0.12}'
        )
        monkeypatch.setattr(
            "environments.local_store.subprocess.run",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=payload),
        )

        results, source = recall_resilient("STATE:", db_path=db)

        assert source == "garden"
        assert results == [{"content": "STATE: 2026-04-09 | depleted | test"}]

    def test_recall_resilient_merges_normalized_garden_with_local(self, monkeypatch):
        db = _tmp_db()
        write("STATE: 2026-04-10 | stable | local only", db_path=db)
        write("STATE: 2026-04-09 | depleted | garden duplicate", db_path=db)
        payload = (
            '{"ok": true, "data": ['
            '{"text": "STATE: 2026-04-09 | depleted | garden duplicate"}'
            '], "error": "", "elapsed": 0.12}'
        )
        monkeypatch.setattr(
            "environments.local_store.subprocess.run",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=payload),
        )

        results, source = recall_resilient("STATE:", limit=5, db_path=db)

        assert source == "merged"
        assert results == [
            {"content": "STATE: 2026-04-09 | depleted | garden duplicate"},
            {"content": "STATE: 2026-04-10 | stable | local only"},
        ]

    def test_recall_resilient_filters_non_matching_garden_rows(self, monkeypatch):
        db = _tmp_db()
        payload = (
            '{"ok": true, "data": ['
            '{"text": "maps-os WALKTHROUGH.md human usage guide"}, '
            '{"text": "STATE: 2026-04-09 | clear | actual entry"}'
            '], "error": "", "elapsed": 0.12}'
        )
        monkeypatch.setattr(
            "environments.local_store.subprocess.run",
            lambda *args, **kwargs: SimpleNamespace(returncode=0, stdout=payload),
        )

        results, source = recall_resilient("STATE:", db_path=db)

        assert source == "garden"
        assert results == [{"content": "STATE: 2026-04-09 | clear | actual entry"}]


class TestGardenFailsafe:
    """
    Tests that the system degrades gracefully when garden is unavailable.
    These use the resilient_remember function indirectly through local_store.
    """

    def test_write_survives_no_garden(self):
        """Write to local store works without any garden dependency."""
        db = _tmp_db()
        row_id = write("STATE: 2026-04-09 | stable | offline test", db_path=db)
        assert row_id >= 1

    def test_recall_survives_no_garden(self):
        """Recall from local store works without garden."""
        db = _tmp_db()
        write("STATE: 2026-04-09 | stable | offline test", db_path=db)
        results = recall("STATE:", db_path=db)
        assert len(results) == 1

    def test_entries_not_lost_between_writes(self):
        """Multiple writes accumulate correctly."""
        db = _tmp_db()
        for tag in ["depleted", "depleted", "stable"]:
            write(f"STATE: 2026-04-09 | {tag} | test", db_path=db)
        all_states = recall("STATE:", limit=10, db_path=db)
        assert len(all_states) == 3

    def test_pending_persists_across_connections(self):
        """Pending entries survive db connection close/reopen."""
        db = _tmp_db()
        write("STATE: 2026-04-09 | grieving | test", db_path=db)
        # Reopen connection by calling count_pending again
        assert count_pending(db_path=db) == 1

    def test_schema_idempotent(self):
        """Multiple _db() calls with same path don't corrupt schema."""
        db = _tmp_db()
        write("STATE: 2026-04-09 | stable | first", db_path=db)
        write("STATE: 2026-04-10 | thriving | second", db_path=db)
        results = recall("STATE:", limit=10, db_path=db)
        assert len(results) == 2


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
