"""Tests for scripts/with_server.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import with_server


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "with_server.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "Spawn dev server" in result.stdout
    assert "--frontend" in result.stdout
    assert "--wait-only" in result.stdout


def test_requires_at_least_one_port(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "with_server.py")],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode != 0
    assert "frontend" in result.stderr.lower() or "backend" in result.stderr.lower()


def test_wait_only_incompatible_with_command(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "with_server.py"),
         "--frontend", "3000", "--wait-only", "--command", "echo"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode != 0


def test_command_required_unless_wait_only(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "with_server.py"), "--frontend", "3000"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode != 0
    assert "command" in result.stderr.lower()


def test_is_port_listening_returns_bool() -> None:
    result = with_server._is_port_listening(1, timeout=0.1)
    assert isinstance(result, bool)
    assert result is False  # port 1 should not be listening


def test_wait_for_port_times_out_quickly() -> None:
    import time
    start = time.monotonic()
    result = with_server._wait_for_port(port=2, timeout_s=1.0, label="t")
    elapsed = time.monotonic() - start
    assert result is False
    assert elapsed < 2.5
