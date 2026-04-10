# maps · cassette.help · MIT
"""
maps_os_config.py — Configuration loader for maps-os.

Loads ~/.maps_os_config.yaml. Always degrades gracefully — missing file returns {}.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".maps_os_config.yaml"

_cache: dict[str, Any] | None = None


def load_config() -> dict[str, Any]:
    """Returns config dict. Returns {} if file missing — never raises."""
    global _cache
    if _cache is not None:
        return _cache

    if not _CONFIG_PATH.exists():
        _cache = {}
        return _cache

    try:
        import yaml

        with open(_CONFIG_PATH) as f:
            _cache = yaml.safe_load(f) or {}
            return _cache
    except Exception:
        _cache = {}
        return _cache


def known_people() -> list[str]:
    """Returns config.get('known_people', []) lowercased."""
    config = load_config()
    people = config.get("known_people", [])
    if isinstance(people, list):
        return [p.lower().strip() for p in people if p]
    return []


def clear_cache() -> None:
    """Clear cached config (useful for testing)."""
    global _cache
    _cache = None
