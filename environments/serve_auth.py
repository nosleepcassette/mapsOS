"""Auth helpers for the optional mapsOS HTTP server."""

from __future__ import annotations

import os
from dataclasses import dataclass


TOKEN_ENV = "MAPS_SERVE_TOKEN"


@dataclass(slots=True)
class ServeAuthError(Exception):
    status_code: int
    detail: str


def validate_bearer_token(authorization: str | None) -> None:
    expected = os.environ.get(TOKEN_ENV, "").strip()
    if not expected:
        raise ServeAuthError(503, f"{TOKEN_ENV} not set on server")

    provided = (authorization or "").removeprefix("Bearer ").strip()
    if provided != expected:
        raise ServeAuthError(401, "unauthorized")
