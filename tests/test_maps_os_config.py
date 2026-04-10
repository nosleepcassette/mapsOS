# maps · cassette.help · MIT
"""Tests for maps_os_config helpers."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from environments import maps_os_config


def test_person_context_returns_mapping_when_present(tmp_path, monkeypatch):
    config_path = tmp_path / "maps_os_config.yaml"
    config_path.write_text(
        "known_people:\n"
        "  - maggie\n"
        "people:\n"
        "  maggie:\n"
        "    role: ex\n"
        "    notes: still close\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(maps_os_config, "_CONFIG_PATH", config_path)
    maps_os_config.clear_cache()

    assert maps_os_config.person_context("Maggie") == {
        "role": "ex",
        "notes": "still close",
    }


def test_person_context_returns_empty_mapping_when_missing(tmp_path, monkeypatch):
    config_path = tmp_path / "maps_os_config.yaml"
    config_path.write_text("known_people:\n  - maggie\n", encoding="utf-8")
    monkeypatch.setattr(maps_os_config, "_CONFIG_PATH", config_path)
    maps_os_config.clear_cache()

    assert maps_os_config.person_context("sarah") == {}


def test_person_birth_hint_parses_inline_comment_metadata(tmp_path, monkeypatch):
    config_path = tmp_path / "maps_os_config.yaml"
    config_path.write_text(
        "known_people:\n"
        "  - irene  # best friend. b. 2000-06-10, Jackson MS (city uncertain). lives: San Francisco CA\n"
        "people:\n"
        "  irene:\n"
        "    role: friend\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(maps_os_config, "_CONFIG_PATH", config_path)
    maps_os_config.clear_cache()

    assert maps_os_config.person_birth_hint("irene") == {
        "comment": "best friend. b. 2000-06-10, Jackson MS (city uncertain). lives: San Francisco CA",
        "birth_date": "2000-06-10",
        "birth_place": "Jackson MS (city uncertain)",
        "current_place": "San Francisco CA",
    }
