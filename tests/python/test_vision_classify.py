"""Tests for scripts/vision_classify.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import vision_classify as vc


def test_parse_verdict_bug_s2() -> None:
    result = vc.parse_verdict("bug-S2: horizontal overflow in .product-grid")
    assert result["valid"] is True
    assert result["verdict"] == "bug-s2"
    assert result["severity"] == "S2"
    assert result["decision"] == "report"


def test_parse_verdict_noise() -> None:
    result = vc.parse_verdict("noise: antialiasing jitter")
    assert result["valid"] is True
    assert result["verdict"] == "noise"
    assert result["severity"] is None
    assert result["decision"] == "ignore"


def test_parse_verdict_redesign() -> None:
    result = vc.parse_verdict("redesign: navbar layout was intentionally updated")
    assert result["valid"] is True
    assert result["decision"] == "regenerate-baseline"


def test_parse_verdict_invalid_format() -> None:
    result = vc.parse_verdict("This is not the right format")
    assert result["valid"] is False
    assert "could not parse" in result["reason"].lower()


def test_parse_verdict_empty() -> None:
    result = vc.parse_verdict("")
    assert result["valid"] is False


def test_parse_verdict_takes_first_non_empty_line() -> None:
    text = "\n\nbug-S0: page is fully broken\nignore this second line\n"
    result = vc.parse_verdict(text)
    assert result["valid"] is True
    assert result["severity"] == "S0"


def test_append_to_bugs_writes_visual_record(tmp_path: Path) -> None:
    bugs_path = tmp_path / "bugs.json"
    bugs_path.write_text(json.dumps({"runId": "r", "bugs": []}), encoding="utf-8")
    parsed = {"valid": True, "verdict": "bug-s2", "severity": "S2",
              "decision": "report", "reason": "test reason"}
    rc = vc.append_to_bugs(bugs_path, "img-001", parsed)
    assert rc == 0
    data = json.loads(bugs_path.read_text(encoding="utf-8"))
    assert len(data["bugs"]) == 1
    assert data["bugs"][0]["id"] == "VIS-img-001"
    assert data["bugs"][0]["severity"] == "S2"
    assert data["bugs"][0]["category"] == "visual"


def test_append_to_bugs_missing_file(tmp_path: Path) -> None:
    rc = vc.append_to_bugs(tmp_path / "nope.json", "x", {"valid": True})
    assert rc == 1


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "vision_classify.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "verdict" in result.stdout.lower()


def test_cli_parses_stdin(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "vision_classify.py"), "--task-id", "x"],
        input="bug-S1: button broken\n",
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    out = json.loads(result.stdout)
    assert out["valid"] is True
    assert out["severity"] == "S1"


def test_cli_strict_exits_nonzero_on_invalid(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "vision_classify.py"),
         "--task-id", "x", "--strict"],
        input="not a verdict\n",
        capture_output=True, text=True, encoding="utf-8",
    )
    assert result.returncode == 2
