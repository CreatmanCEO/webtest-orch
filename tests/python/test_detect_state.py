"""Tests for scripts/detect_state.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import detect_state


def test_collect_returns_schema(tmp_path: Path) -> None:
    state = detect_state.collect(tmp_path)
    for key in ("schemaVersion", "projectRoot", "tests", "deps", "auth",
                "credentials", "servers", "history", "isolation", "git"):
        assert key in state
    assert state["schemaVersion"] == "1.0.0"


def test_collect_empty_project(tmp_path: Path) -> None:
    state = detect_state.collect(tmp_path)
    assert state["tests"]["dir"] is False
    assert state["tests"]["specsDir"] is False
    assert state["tests"]["configTs"] is False
    assert state["deps"]["playwright"] is False
    assert state["history"]["lastRunId"] is None


def test_collect_detects_tests_dir(tmp_path: Path) -> None:
    (tmp_path / "tests" / "specs").mkdir(parents=True)
    (tmp_path / "playwright.config.ts").write_text("// stub")
    state = detect_state.collect(tmp_path)
    assert state["tests"]["dir"] is True
    assert state["tests"]["specsDir"] is True
    assert state["tests"]["configTs"] is True


def test_decide_mode_bootstrap_when_empty(tmp_path: Path) -> None:
    state = detect_state.collect(tmp_path)
    assert detect_state.decide_mode(state) == "BOOTSTRAP"


def test_decide_mode_replay_when_configured(tmp_path: Path) -> None:
    (tmp_path / "tests" / "specs").mkdir(parents=True)
    (tmp_path / "playwright.config.ts").write_text("// stub")
    state = detect_state.collect(tmp_path)
    assert detect_state.decide_mode(state) == "REPLAY_OR_HYBRID"


def test_human_render_has_all_rows(tmp_path: Path) -> None:
    state = detect_state.collect(tmp_path)
    output = detect_state.render_human(state)
    for required in ("Project root", "Tests dir", "Playwright deps",
                      "Mode hint", "Isolation verified"):
        assert required in output


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "detect_state.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "Probe project state" in result.stdout


def test_cli_json_output_is_valid(scripts_dir: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "detect_state.py"), "--cwd", str(tmp_path), "--json"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    data = json.loads(result.stdout)
    assert data["schemaVersion"] == "1.0.0"
    assert data["modeHint"] == "BOOTSTRAP"


def test_credentials_source_missing_when_no_env_test(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TEST_CREDENTIALS_FILE", raising=False)
    state = detect_state.collect(tmp_path)
    assert state["credentials"]["credentialsSource"] == "missing"


def test_credentials_source_project_when_env_test_present(tmp_path: Path) -> None:
    (tmp_path / ".env.test").write_text("TEST_BASE_URL=https://x")
    state = detect_state.collect(tmp_path)
    assert state["credentials"]["credentialsSource"] == "project"
