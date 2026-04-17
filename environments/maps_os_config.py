# maps · cassette.help · MIT
"""
maps_os_config.py — Configuration loader for mapsOS.

Loads ~/.maps_os_config.yaml. Always degrades gracefully — missing file returns {}.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

_CONFIG_PATH = Path.home() / ".maps_os_config.yaml"

_cache: dict[str, Any] | None = None

DEFAULT_STATE_TAGS: dict[str, str] = {
    "surviving": "minimal function, getting through",
    "stable": "neutral baseline",
    "grounded": "anchored, present",
    "thriving": "genuine forward momentum",
    "tender": "emotionally open, soft",
    "grieving": "loss-adjacent",
    "manic": "elevated, fast, possibly unsustainable",
    "depleted": "tank empty",
    "flooded": "overwhelmed, can't process",
    "clear": "sharp, minimal noise",
}

DEFAULT_TRACKS: list[dict[str, Any]] = [
    {
        "name": "BODY",
        "categories": ["sleep", "pain", "energy", "movement", "food", "substance"],
    },
    {
        "name": "MIND",
        "categories": ["focus", "anxiety", "clarity", "load", "creativity"],
    },
    {
        "name": "SPIRIT",
        "categories": ["connection", "meaning", "play", "solitude", "gratitude"],
    },
]


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


def _coerce_positive_int(value: Any, default: int) -> int:
    try:
        coerced = int(value)
    except (TypeError, ValueError):
        return default
    return coerced if coerced > 0 else default


def load_survival_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """
    Returns survival config with defaults.

    Optional keys:
      survival.threshold: int
      survival.window: int
      survival.low_states: list[str]
    """
    if not isinstance(cfg, dict):
        cfg = {}

    sv = cfg.get("survival", {})
    if not isinstance(sv, dict):
        sv = {}

    cap = cfg.get("capacity", {})
    if not isinstance(cap, dict):
        cap = {}

    raw_low_states = cap.get(
        "low_states",
        sv.get("low_states", ["depleted", "grieving", "surviving"]),
    )
    if not isinstance(raw_low_states, list):
        raw_low_states = ["depleted", "grieving", "surviving"]

    low_states = {
        str(state).strip().lower()
        for state in raw_low_states
        if str(state).strip()
    }
    if not low_states:
        low_states = {"depleted", "grieving", "surviving"}

    return {
        "threshold": _coerce_positive_int(cap.get("threshold", sv.get("threshold")), 3),
        "window": _coerce_positive_int(cap.get("window", sv.get("window")), 5),
        "low_states": low_states,
    }


def load_state_tags(cfg: dict[str, Any]) -> dict[str, str]:
    """Returns {tag: description} from config.state.tags, or defaults."""
    state = cfg.get("state", {}) if isinstance(cfg, dict) else {}
    tags = state.get("tags", {}) if isinstance(state, dict) else {}
    if isinstance(tags, dict) and tags:
        return {
            str(key).strip().lower(): str(value).strip()
            for key, value in tags.items()
            if str(key).strip()
        }
    return dict(DEFAULT_STATE_TAGS)


def load_capacity_config(cfg: dict[str, Any]) -> dict[str, Any]:
    """Returns capacity mode configuration with low-capacity defaults."""
    cap = cfg.get("capacity", {}) if isinstance(cfg, dict) else {}
    if not isinstance(cap, dict):
        cap = {}

    survival_mode = bool(cap.get("survival_mode", False))
    if survival_mode:
        mode_label = "survival mode"
        mode_short = "survival"
    else:
        mode_label = str(cap.get("mode_label") or "low capacity")
        mode_short = "low capacity"

    survival_cfg = load_survival_config(cfg)
    return {
        "survival_mode": survival_mode,
        "mode_label": mode_label,
        "mode_short": mode_short,
        "low_states": survival_cfg["low_states"],
        "threshold": survival_cfg["threshold"],
        "window": survival_cfg["window"],
    }


def load_tracks_config(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Returns track configuration or BODY/MIND/SPIRIT defaults."""
    tracks = cfg.get("tracks", []) if isinstance(cfg, dict) else []
    if isinstance(tracks, list) and tracks:
        normalized: list[dict[str, Any]] = []
        for item in tracks:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            categories = item.get("categories")
            if not name or not isinstance(categories, list) or not categories:
                continue
            normalized.append(
                {
                    "name": name,
                    "categories": [str(category).strip() for category in categories],
                }
            )
        if normalized:
            return normalized
    return [dict(track) for track in DEFAULT_TRACKS]


def known_people() -> list[str]:
    """Returns config.get('known_people', []) lowercased."""
    config = load_config()
    people = config.get("known_people", [])
    if isinstance(people, list):
        return [p.lower().strip() for p in people if p]
    return []


def person_context(name: str) -> dict[str, Any]:
    """Returns config.get('people', {}).get(name_lower, {}). Never raises."""
    config = load_config()
    people = config.get("people", {})
    if not isinstance(people, dict):
        return {}
    context = people.get(name.lower().strip(), {})
    return context if isinstance(context, dict) else {}


def _known_people_comments() -> dict[str, str]:
    """Parse inline comments for known_people entries from the raw YAML file."""
    if not _CONFIG_PATH.exists():
        return {}

    try:
        raw = _CONFIG_PATH.read_text(encoding="utf-8")
    except Exception:
        return {}

    comments: dict[str, str] = {}
    in_known_people = False

    for line in raw.splitlines():
        stripped = line.strip()

        if not in_known_people:
            if stripped == "known_people:":
                in_known_people = True
            continue

        if not stripped or stripped.startswith("#"):
            continue

        if not stripped.startswith("-"):
            break

        match = re.match(r"-\s*([A-Za-z0-9_-]+)\s*(?:#\s*(.*))?$", stripped)
        if not match:
            continue

        name = match.group(1).lower().strip()
        comment = (match.group(2) or "").strip()
        comments[name] = comment

    return comments


def person_birth_hint(name: str) -> dict[str, str]:
    """
    Parse optional birth hints from inline known_people comments.

    Supported patterns are intentionally conservative:
      `b. YYYY-MM-DD, Place`
      `lives: Place`
    """
    comment = _known_people_comments().get(name.lower().strip(), "")
    if not comment:
        return {}

    out: dict[str, str] = {"comment": comment}

    birth_match = re.search(r"\bb\.\s*(\d{4}-\d{2}-\d{2})(?:,\s*([^\.]+))?", comment)
    if birth_match:
        out["birth_date"] = birth_match.group(1)
        birth_place = (birth_match.group(2) or "").strip()
        if birth_place:
            out["birth_place"] = birth_place

    lives_match = re.search(r"\blives:\s*([^\.]+)", comment)
    if lives_match:
        current_place = lives_match.group(1).strip()
        if current_place:
            out["current_place"] = current_place

    return out


def clear_cache() -> None:
    """Clear cached config (useful for testing)."""
    global _cache
    _cache = None
