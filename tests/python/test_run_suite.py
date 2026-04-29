"""Tests for scripts/run_suite.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import run_suite


def test_strip_ansi_removes_codes() -> None:
    raw = "\x1b[2mhello\x1b[22m \x1b[31mworld\x1b[0m"
    assert run_suite.strip_ansi(raw) == "hello world"


def test_strip_ansi_handles_empty() -> None:
    assert run_suite.strip_ansi("") == ""
    assert run_suite.strip_ansi(None) == ""  # type: ignore[arg-type]


def test_extract_issues_from_error_basic() -> None:
    msg = "Error: 3 issues found:\n  - first issue\n  - second issue\n  - third issue\n\nExpected: []"
    issues = run_suite.extract_issues_from_error(msg)
    assert issues == ["first issue", "second issue", "third issue"]


def test_extract_issues_strips_ansi() -> None:
    msg = "\x1b[2mError: 1 issues found:\x1b[22m\n  - real issue\n\nExpected: []"
    issues = run_suite.extract_issues_from_error(msg)
    assert issues == ["real issue"]


def test_extract_issues_returns_empty_when_no_marker() -> None:
    assert run_suite.extract_issues_from_error("just a regular error") == []
    assert run_suite.extract_issues_from_error("") == []


def test_extract_issues_stops_at_blank_line() -> None:
    msg = "Error: 2 issues found:\n  - first\n  - second\n\n+ Array [\n+   \"first\",\n+ ]"
    issues = run_suite.extract_issues_from_error(msg)
    assert issues == ["first", "second"]
    assert "Array" not in str(issues)


def test_extract_issues_stops_at_non_bullet_line() -> None:
    msg = "Error: 1 issues found:\n  - real issue\n  not a bullet\n  - missed"
    issues = run_suite.extract_issues_from_error(msg)
    assert issues == ["real issue"]


def test_normalize_results_creates_one_record_per_issue(
    sample_playwright_results: dict, tmp_path: Path
) -> None:
    results_path = tmp_path / "results.json"
    out_path = tmp_path / "raw_bugs.json"
    results_path.write_text(json.dumps(sample_playwright_results), encoding="utf-8")

    rc, _total, _failed = run_suite.normalize_results(results_path, out_path, "run-test")
    assert rc == 0

    data = json.loads(out_path.read_text(encoding="utf-8"))
    # 1 test failure with issues[] collector → 2 individual bug records
    assert len(data["bugs"]) == 2
    issue_lines = [b["issueLine"] for b in data["bugs"]]
    assert any("color-contrast" in line for line in issue_lines)
    assert any("touch-target" in line for line in issue_lines)


def test_normalize_results_falls_back_to_single_record_without_collector(
    tmp_path: Path,
) -> None:
    raw_results = {
        "stats": {},
        "suites": [{
            "title": "X",
            "specs": [{"title": "t", "file": "x.ts", "tests": [{
                "projectName": "chromium",
                "results": [{
                    "status": "failed",
                    "error": {"message": "Plain old failure", "stack": "", "snippet": "", "location": {}},
                    "attachments": [],
                }],
            }]}],
            "suites": [],
        }],
    }
    results_path = tmp_path / "results.json"
    out_path = tmp_path / "raw_bugs.json"
    results_path.write_text(json.dumps(raw_results), encoding="utf-8")
    rc, _, _ = run_suite.normalize_results(results_path, out_path, "run-x")
    assert rc == 0
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert len(data["bugs"]) == 1
    assert "issueLine" not in data["bugs"][0]


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "run_suite.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "Run Playwright suite" in result.stdout


def test_cli_skip_run_with_existing_results(
    scripts_dir: Path, tmp_path: Path, sample_playwright_results: dict
) -> None:
    out_dir = tmp_path / "run-x"
    out_dir.mkdir()
    (out_dir / "results.json").write_text(
        json.dumps(sample_playwright_results), encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, str(scripts_dir / "run_suite.py"),
         "--cwd", str(tmp_path), "--out", str(out_dir), "--skip-run"],
        capture_output=True, text=True, encoding="utf-8",
    )
    assert (out_dir / "raw_bugs.json").is_file()
