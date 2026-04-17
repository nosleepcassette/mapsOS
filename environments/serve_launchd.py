"""launchd management for the optional mapsOS HTTP server."""

from __future__ import annotations

import os
import plistlib
import re
import secrets
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SERVICE_LABEL = "io.nosleepcassette.mapsos.serve"


@dataclass(frozen=True)
class ServeLaunchdPaths:
    repo_root: Path
    launch_agents_dir: Path
    plist_path: Path
    support_dir: Path
    token_path: Path
    stdout_path: Path
    stderr_path: Path


@dataclass(frozen=True)
class ServeLaunchdStatus:
    installed: bool
    loaded: bool
    running: bool
    pid: int | None
    state: str | None
    plist_path: Path
    stdout_path: Path
    stderr_path: Path
    token_path: Path


def default_paths() -> ServeLaunchdPaths:
    repo_root = Path(__file__).resolve().parent.parent
    launch_agents_dir = Path.home() / "Library" / "LaunchAgents"
    support_dir = Path.home() / ".mapsOS" / "serve"
    return ServeLaunchdPaths(
        repo_root=repo_root,
        launch_agents_dir=launch_agents_dir,
        plist_path=launch_agents_dir / f"{SERVICE_LABEL}.plist",
        support_dir=support_dir,
        token_path=support_dir / "token",
        stdout_path=support_dir / "launchd.stdout.log",
        stderr_path=support_dir / "launchd.stderr.log",
    )


def launchd_domain_target() -> str:
    return f"gui/{os.getuid()}"


def launchd_service_target() -> str:
    return f"{launchd_domain_target()}/{SERVICE_LABEL}"


def _bin_path(name: str, fallback: str) -> str:
    return shutil.which(name) or fallback


def _launchctl(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["/bin/launchctl", *args],
        capture_output=True,
        text=True,
        check=False,
    )
    if check and completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or f"launchctl {' '.join(args)} failed"
        raise RuntimeError(detail)
    return completed


def _write_text(path: Path, content: str, *, mode: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    os.chmod(path, mode)


def resolve_token(paths: ServeLaunchdPaths, explicit_token: str | None = None) -> tuple[str, str]:
    if explicit_token and explicit_token.strip():
        return explicit_token.strip(), "cli"

    env_token = os.environ.get("MAPS_SERVE_TOKEN", "").strip()
    if env_token:
        return env_token, "env"

    if paths.token_path.exists():
        existing = paths.token_path.read_text(encoding="utf-8").strip()
        if existing:
            return existing, "file"

    return secrets.token_hex(32), "generated"


def build_program_arguments(
    paths: ServeLaunchdPaths,
    *,
    host: str,
    port: int,
    uv_bin: str | None = None,
    python_bin: str | None = None,
) -> list[str]:
    uv_path = uv_bin or _bin_path("uv", "/usr/local/bin/uv")
    python_path = python_bin or _bin_path("python3", "/usr/local/bin/python3")
    return [
        uv_path,
        "run",
        "--python",
        python_path,
        "--directory",
        str(paths.repo_root),
        "--with-requirements",
        str(paths.repo_root / "requirements.txt"),
        "--with-requirements",
        str(paths.repo_root / "requirements-optional.txt"),
        "python3",
        "bin/maps",
        "serve",
        "--host",
        host,
        "--port",
        str(port),
    ]


def build_launch_agent_plist(
    paths: ServeLaunchdPaths,
    *,
    token: str,
    host: str,
    port: int,
    path_env: str | None = None,
    uv_bin: str | None = None,
    python_bin: str | None = None,
) -> dict[str, Any]:
    program_arguments = build_program_arguments(
        paths,
        host=host,
        port=port,
        uv_bin=uv_bin,
        python_bin=python_bin,
    )
    resolved_path = path_env or os.environ.get("PATH", "").strip() or "/usr/local/bin:/usr/bin:/bin:/opt/homebrew/bin"
    return {
        "Label": SERVICE_LABEL,
        "ProgramArguments": program_arguments,
        "WorkingDirectory": str(paths.repo_root),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "EnvironmentVariables": {
            "MAPS_SERVE_TOKEN": token,
            "PATH": resolved_path,
        },
        "StandardOutPath": str(paths.stdout_path),
        "StandardErrorPath": str(paths.stderr_path),
    }


def parse_launchctl_print(text: str) -> tuple[str | None, int | None]:
    state_match = re.search(r"^\s*state = (.+)$", text, re.MULTILINE)
    pid_match = re.search(r"^\s*pid = (\d+)$", text, re.MULTILINE)
    state = state_match.group(1).strip() if state_match else None
    pid = int(pid_match.group(1)) if pid_match else None
    return state, pid


def serve_launchd_status(paths: ServeLaunchdPaths | None = None) -> ServeLaunchdStatus:
    resolved_paths = paths or default_paths()
    installed = resolved_paths.plist_path.exists()
    if not installed:
        return ServeLaunchdStatus(
            installed=False,
            loaded=False,
            running=False,
            pid=None,
            state=None,
            plist_path=resolved_paths.plist_path,
            stdout_path=resolved_paths.stdout_path,
            stderr_path=resolved_paths.stderr_path,
            token_path=resolved_paths.token_path,
        )

    completed = _launchctl("print", launchd_service_target(), check=False)
    if completed.returncode != 0:
        return ServeLaunchdStatus(
            installed=True,
            loaded=False,
            running=False,
            pid=None,
            state=None,
            plist_path=resolved_paths.plist_path,
            stdout_path=resolved_paths.stdout_path,
            stderr_path=resolved_paths.stderr_path,
            token_path=resolved_paths.token_path,
        )

    state, pid = parse_launchctl_print(completed.stdout)
    return ServeLaunchdStatus(
        installed=True,
        loaded=True,
        running=state == "running" or pid is not None,
        pid=pid,
        state=state,
        plist_path=resolved_paths.plist_path,
        stdout_path=resolved_paths.stdout_path,
        stderr_path=resolved_paths.stderr_path,
        token_path=resolved_paths.token_path,
    )


def install_serve_launchd(
    *,
    host: str,
    port: int,
    token: str | None = None,
    paths: ServeLaunchdPaths | None = None,
) -> dict[str, Any]:
    resolved_paths = paths or default_paths()
    resolved_paths.launch_agents_dir.mkdir(parents=True, exist_ok=True)
    resolved_paths.support_dir.mkdir(parents=True, exist_ok=True)
    resolved_token, token_source = resolve_token(resolved_paths, explicit_token=token)
    _write_text(resolved_paths.token_path, resolved_token + "\n", mode=0o600)

    plist_payload = build_launch_agent_plist(
        resolved_paths,
        token=resolved_token,
        host=host,
        port=port,
    )
    with resolved_paths.plist_path.open("wb") as handle:
        plistlib.dump(plist_payload, handle, sort_keys=True)
    os.chmod(resolved_paths.plist_path, 0o644)

    _launchctl("bootout", launchd_domain_target(), str(resolved_paths.plist_path), check=False)
    _launchctl("bootstrap", launchd_domain_target(), str(resolved_paths.plist_path))
    _launchctl("kickstart", "-k", launchd_service_target())

    status = serve_launchd_status(resolved_paths)
    return {
        "label": SERVICE_LABEL,
        "host": host,
        "port": port,
        "token_source": token_source,
        "token_path": resolved_paths.token_path,
        "plist_path": resolved_paths.plist_path,
        "stdout_path": resolved_paths.stdout_path,
        "stderr_path": resolved_paths.stderr_path,
        "status": status,
    }


def start_serve_launchd(paths: ServeLaunchdPaths | None = None) -> ServeLaunchdStatus:
    resolved_paths = paths or default_paths()
    if not resolved_paths.plist_path.exists():
        raise FileNotFoundError(f"launchd plist not found: {resolved_paths.plist_path}")

    status = serve_launchd_status(resolved_paths)
    if not status.loaded:
        _launchctl("bootstrap", launchd_domain_target(), str(resolved_paths.plist_path))
    _launchctl("kickstart", "-k", launchd_service_target())
    return serve_launchd_status(resolved_paths)


def stop_serve_launchd(paths: ServeLaunchdPaths | None = None) -> ServeLaunchdStatus:
    resolved_paths = paths or default_paths()
    if resolved_paths.plist_path.exists():
        _launchctl("bootout", launchd_domain_target(), str(resolved_paths.plist_path), check=False)
    return serve_launchd_status(resolved_paths)


def restart_serve_launchd(paths: ServeLaunchdPaths | None = None) -> ServeLaunchdStatus:
    resolved_paths = paths or default_paths()
    if not resolved_paths.plist_path.exists():
        raise FileNotFoundError(f"launchd plist not found: {resolved_paths.plist_path}")
    _launchctl("bootout", launchd_domain_target(), str(resolved_paths.plist_path), check=False)
    _launchctl("bootstrap", launchd_domain_target(), str(resolved_paths.plist_path))
    _launchctl("kickstart", "-k", launchd_service_target())
    return serve_launchd_status(resolved_paths)


def uninstall_serve_launchd(paths: ServeLaunchdPaths | None = None) -> dict[str, Path]:
    resolved_paths = paths or default_paths()
    if resolved_paths.plist_path.exists():
        _launchctl("bootout", launchd_domain_target(), str(resolved_paths.plist_path), check=False)
        resolved_paths.plist_path.unlink()
    return {
        "plist_path": resolved_paths.plist_path,
        "token_path": resolved_paths.token_path,
        "stdout_path": resolved_paths.stdout_path,
        "stderr_path": resolved_paths.stderr_path,
    }
