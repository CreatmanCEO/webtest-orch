"""Tests for scripts/_image_isolation_check.py."""
from __future__ import annotations

import importlib
import subprocess
import sys
from pathlib import Path


def _import_iso(monkeypatch, skill_dir: Path):
    monkeypatch.setenv("CLAUDE_SKILL_DIR", str(skill_dir))
    if "_image_isolation_check" in sys.modules:
        del sys.modules["_image_isolation_check"]
    return importlib.import_module("_image_isolation_check")


def test_gen_fixtures_writes_three_pngs(monkeypatch, tmp_path: Path) -> None:
    iso = _import_iso(monkeypatch, tmp_path)
    rc = iso.gen_fixtures()
    assert rc == 0
    fixtures = tmp_path / "fixtures" / "iso-test"
    for name in ("a.png", "b.png", "c.png"):
        assert (fixtures / name).is_file()
        # Valid PNG signature
        with open(fixtures / name, "rb") as f:
            assert f.read(8) == b"\x89PNG\r\n\x1a\n"


def test_verify_fails_without_marker(monkeypatch, tmp_path: Path) -> None:
    iso = _import_iso(monkeypatch, tmp_path)
    iso.gen_fixtures()
    rc = iso.verify()
    assert rc == 1


def test_verify_fails_without_fixtures(monkeypatch, tmp_path: Path) -> None:
    iso = _import_iso(monkeypatch, tmp_path)
    rc = iso.verify()
    assert rc == 1


def test_mark_verified_then_verify_passes(monkeypatch, tmp_path: Path) -> None:
    iso = _import_iso(monkeypatch, tmp_path)
    iso.gen_fixtures()
    iso.mark_verified()
    rc = iso.verify()
    assert rc == 0
    assert (tmp_path / ".isolation-verified").is_file()


def test_reset_removes_marker_and_fixtures(monkeypatch, tmp_path: Path) -> None:
    iso = _import_iso(monkeypatch, tmp_path)
    iso.gen_fixtures()
    iso.mark_verified()
    iso.reset()
    assert not (tmp_path / ".isolation-verified").is_file()
    fixtures = tmp_path / "fixtures" / "iso-test"
    for name in ("a.png", "b.png", "c.png"):
        assert not (fixtures / name).is_file()


def test_status_does_not_crash(monkeypatch, tmp_path: Path, capsys) -> None:
    iso = _import_iso(monkeypatch, tmp_path)
    rc = iso.status()
    assert rc == 0
    captured = capsys.readouterr()
    assert "Skill dir" in captured.out


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "_image_isolation_check.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "image-budget" in result.stdout.lower()
