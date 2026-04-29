#!/usr/bin/env python3
"""detect_state.py — probe a project for webapp-test-orchestrator state.

Output JSON describing what the skill needs to know to choose between
BOOTSTRAP / REPLAY / HYBRID modes. Designed to be invoked as a black box;
the SKILL.md surfaces the same state via dynamic-context probes.

Usage:
    detect_state.py --json
    detect_state.py --human
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

# Windows stdout often defaults to cp1252; force UTF-8 so Cyrillic paths and
# em-dashes don't crash with UnicodeEncodeError. No-op on Linux/macOS.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


COMMON_DEV_PORTS = (3000, 3001, 5173, 8000, 8080, 8081, 4200, 5000, 5500)


def _is_port_listening(port: int, host: str = "127.0.0.1", timeout: float = 0.2) -> bool:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(timeout)
    try:
        return s.connect_ex((host, port)) == 0
    finally:
        s.close()


def _detect_listening_ports() -> list[int]:
    return [p for p in COMMON_DEV_PORTS if _is_port_listening(p)]


def _detect_skill_dir() -> str | None:
    """Resolve the skill's own directory.

    Priority:
    1. `CLAUDE_SKILL_DIR` env var (set by Claude Code at skill-load)
    2. `__file__`'s parent's parent (the script lives at `<skill_dir>/scripts/<this>.py`)
    """
    env = os.environ.get("CLAUDE_SKILL_DIR")
    if env:
        return env
    try:
        return str(Path(__file__).resolve().parent.parent)
    except (OSError, ValueError):
        return None


def _isolation_verified(skill_dir: str | None) -> bool:
    if not skill_dir:
        return False
    return Path(skill_dir, ".isolation-verified").is_file()


def _credentials_source(project_root: Path) -> str:
    if (project_root / ".env.test").is_file():
        return "project"
    env_var = os.environ.get("TEST_CREDENTIALS_FILE", "")
    if env_var and Path(env_var).is_file():
        return f"env:{env_var}"
    return "missing"


def _last_run(project_root: Path) -> str | None:
    reports = project_root / "reports"
    if not reports.is_dir():
        return None
    runs = sorted(
        (p for p in reports.iterdir() if p.is_dir()),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return runs[0].name if runs else None


def _last_bugs_json(project_root: Path) -> str | None:
    reports = project_root / "reports"
    if not reports.is_dir():
        return None
    candidates = sorted(
        reports.glob("*/bugs.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return str(candidates[0].relative_to(project_root)) if candidates else None


def _git_changed_routes(project_root: Path) -> list[str]:
    if not (project_root / ".git").is_dir():
        return []
    if shutil.which("git") is None:
        return []
    try:
        out = subprocess.run(
            ["git", "-C", str(project_root), "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    if out.returncode != 0:
        return []
    candidates = []
    for line in out.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith(("app/", "pages/", "src/app/", "src/pages/")):
            candidates.append(line)
    return candidates


def collect(project_root: Path) -> dict[str, Any]:
    skill_dir = _detect_skill_dir()
    return {
        "schemaVersion": "1.0.0",
        "projectRoot": str(project_root),
        "skillDir": skill_dir,
        "tests": {
            "dir": (project_root / "tests").is_dir(),
            "specsDir": (project_root / "tests" / "specs").is_dir(),
            "configTs": (project_root / "playwright.config.ts").is_file(),
            "configJs": (project_root / "playwright.config.js").is_file(),
        },
        "deps": {
            "playwright": (project_root / "node_modules" / ".bin" / "playwright").is_file()
            or (project_root / "node_modules" / ".bin" / "playwright.cmd").is_file(),
            "axeCore": (project_root / "node_modules" / "@axe-core" / "playwright").is_dir(),
        },
        "auth": {
            "stateFile": (project_root / "playwright" / ".auth" / "user.json").is_file(),
        },
        "credentials": {
            "envTest": (project_root / ".env.test").is_file(),
            "envExample": (project_root / ".env.test.example").is_file(),
            "credentialsSource": _credentials_source(project_root),
        },
        "servers": {
            "listening": _detect_listening_ports(),
        },
        "history": {
            "lastRunId": _last_run(project_root),
            "lastBugsJson": _last_bugs_json(project_root),
        },
        "isolation": {
            "verified": _isolation_verified(skill_dir),
        },
        "git": {
            "isRepo": (project_root / ".git").is_dir(),
            "changedRoutesSinceHead1": _git_changed_routes(project_root),
        },
    }


def decide_mode(state: dict[str, Any]) -> str:
    has_tests = state["tests"]["specsDir"] or state["tests"]["dir"]
    has_config = state["tests"]["configTs"] or state["tests"]["configJs"]
    if not has_tests and not has_config:
        return "BOOTSTRAP"
    if has_tests and has_config:
        return "REPLAY_OR_HYBRID"
    return "BOOTSTRAP"


def render_human(state: dict[str, Any]) -> str:
    rows = [
        ("Project root", state["projectRoot"]),
        ("Skill dir", state["skillDir"] or "(CLAUDE_SKILL_DIR unset)"),
        ("Tests dir", "yes" if state["tests"]["dir"] else "no"),
        ("Specs dir", "yes" if state["tests"]["specsDir"] else "no"),
        ("Playwright config", "yes" if state["tests"]["configTs"] or state["tests"]["configJs"] else "no"),
        ("Playwright deps", "yes" if state["deps"]["playwright"] else "no"),
        ("axe-core deps", "yes" if state["deps"]["axeCore"] else "no"),
        ("Auth state file", "present" if state["auth"]["stateFile"] else "missing"),
        ("Credentials", state["credentials"]["credentialsSource"]),
        ("Listening ports", ", ".join(map(str, state["servers"]["listening"])) or "none"),
        ("Last run id", state["history"]["lastRunId"] or "never"),
        ("Last bugs json", state["history"]["lastBugsJson"] or "none"),
        ("Isolation verified", "yes" if state["isolation"]["verified"] else "no"),
        ("Git repo", "yes" if state["git"]["isRepo"] else "no"),
        ("Mode hint", decide_mode(state)),
    ]
    width = max(len(k) for k, _ in rows)
    return "\n".join(f"{k.ljust(width)}  {v}" for k, v in rows)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Probe project state for webapp-test-orchestrator skill.",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON to stdout")
    parser.add_argument("--human", action="store_true", help="Output a human-readable table")
    parser.add_argument(
        "--cwd",
        default=".",
        help="Project root to probe (default: current working dir)",
    )
    args = parser.parse_args(argv)

    if not args.json and not args.human:
        args.json = True

    project_root = Path(args.cwd).resolve()
    state = collect(project_root)
    state["modeHint"] = decide_mode(state)

    if args.json:
        json.dump(state, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")
    else:
        sys.stdout.write(render_human(state))
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
