from __future__ import annotations

from pathlib import Path

from environments import serve_launchd


def _paths(tmp_path: Path) -> serve_launchd.ServeLaunchdPaths:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    (repo_root / "requirements.txt").write_text("fastapi\n", encoding="utf-8")
    (repo_root / "requirements-optional.txt").write_text("uvicorn\n", encoding="utf-8")
    launch_agents = tmp_path / "LaunchAgents"
    support = tmp_path / ".mapsOS" / "serve"
    return serve_launchd.ServeLaunchdPaths(
        repo_root=repo_root,
        launch_agents_dir=launch_agents,
        plist_path=launch_agents / f"{serve_launchd.SERVICE_LABEL}.plist",
        support_dir=support,
        token_path=support / "token",
        stdout_path=support / "launchd.stdout.log",
        stderr_path=support / "launchd.stderr.log",
    )


def test_build_launch_agent_plist_contains_expected_fields(tmp_path):
    paths = _paths(tmp_path)

    payload = serve_launchd.build_launch_agent_plist(
        paths,
        token="secret-token",
        host="127.0.0.1",
        port=7432,
        path_env="/usr/local/bin:/usr/bin:/bin",
        uv_bin="/usr/local/bin/uv",
        python_bin="/usr/local/bin/python3",
    )

    assert payload["Label"] == serve_launchd.SERVICE_LABEL
    assert payload["RunAtLoad"] is True
    assert payload["KeepAlive"] is True
    assert payload["WorkingDirectory"] == str(paths.repo_root)
    assert payload["EnvironmentVariables"]["MAPS_SERVE_TOKEN"] == "secret-token"
    assert payload["EnvironmentVariables"]["PATH"] == "/usr/local/bin:/usr/bin:/bin"
    assert payload["ProgramArguments"] == [
        "/usr/local/bin/uv",
        "run",
        "--python",
        "/usr/local/bin/python3",
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
        "127.0.0.1",
        "--port",
        "7432",
    ]


def test_resolve_token_prefers_explicit_env_then_file(tmp_path, monkeypatch):
    paths = _paths(tmp_path)
    paths.support_dir.mkdir(parents=True, exist_ok=True)
    paths.token_path.write_text("file-token\n", encoding="utf-8")

    token, source = serve_launchd.resolve_token(paths, explicit_token="cli-token")
    assert (token, source) == ("cli-token", "cli")

    monkeypatch.delenv("MAPS_SERVE_TOKEN", raising=False)
    monkeypatch.setenv("MAPS_SERVE_TOKEN", "env-token")
    token, source = serve_launchd.resolve_token(paths)
    assert (token, source) == ("env-token", "env")

    monkeypatch.delenv("MAPS_SERVE_TOKEN", raising=False)
    token, source = serve_launchd.resolve_token(paths)
    assert (token, source) == ("file-token", "file")


def test_parse_launchctl_print_extracts_state_and_pid():
    state, pid = serve_launchd.parse_launchctl_print(
        """
        io.nosleepcassette.mapsos.serve = {
            active count = 1
            path = /Users/maps/Library/LaunchAgents/io.nosleepcassette.mapsos.serve.plist
            state = running
            pid = 4242
        }
        """
    )

    assert state == "running"
    assert pid == 4242
