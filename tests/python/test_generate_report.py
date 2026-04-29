"""Tests for scripts/generate_report.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import generate_report as gr


def test_strip_ansi_removes_codes() -> None:
    assert gr.strip_ansi("\x1b[2mhello\x1b[22m") == "hello"
    assert gr.strip_ansi("") == ""
    assert gr.strip_ansi(None) == ""  # type: ignore[arg-type]


def test_severity_breakdown_counts_correctly() -> None:
    bugs = [
        {"severity": "S0"},
        {"severity": "S1"},
        {"severity": "S1"},
        {"severity": "S2"},
        {"severity": "S2"},
        {"severity": "S2"},
        # missing severity defaults to S2
        {"title": "no severity"},
    ]
    counts = gr.severity_breakdown(bugs)
    assert counts["S0"] == 1
    assert counts["S1"] == 2
    assert counts["S2"] == 4


def test_render_markdown_verdict_critical() -> None:
    bugs = [{"severity": "S0", "title": "broken auth", "diff": {"state": "new"}}]
    md = gr.render_markdown(bugs, {}, "run-1", "App")
    assert "NOT SHIP-READY" in md
    assert "1 S0 critical" in md


def test_render_markdown_verdict_hold() -> None:
    bugs = [{"severity": "S1", "title": "broken nav", "diff": {"state": "new"}}]
    md = gr.render_markdown(bugs, {}, "run-1", "App")
    assert "HOLD" in md
    assert "1 S1 major" in md


def test_render_markdown_verdict_ship_ready_with_minor() -> None:
    bugs = [{"severity": "S2", "title": "alt text wrong", "diff": {"state": "new"}}]
    md = gr.render_markdown(bugs, {}, "run-1", "App")
    assert "SHIP-READY" in md
    assert "1 minor issue" in md


def test_render_markdown_verdict_clean_run() -> None:
    md = gr.render_markdown([], {}, "run-1", "App")
    assert "SHIP-READY (clean run)" in md


def test_render_markdown_includes_run_diff_section_when_summary_provided() -> None:
    bugs = [{"severity": "S2", "title": "x", "diff": {"state": "new"}}]
    summary = {"new": 1, "regression": 0, "persisting": 0, "fixed": 0}
    md = gr.render_markdown(bugs, summary, "run-1", "App")
    assert "Run diff" in md
    assert "🆕" in md


def test_render_markdown_strips_ansi_in_error_messages() -> None:
    bugs = [{
        "severity": "S2",
        "title": "x",
        "diff": {"state": "new"},
        "error": {"message": "\x1b[31mError text\x1b[0m"},
    }]
    md = gr.render_markdown(bugs, {}, "run-1", "App")
    assert "Error text" in md
    assert "\x1b" not in md


def test_render_html_includes_severity_cards() -> None:
    bugs = [{"severity": "S0", "title": "x"}, {"severity": "S2", "title": "y"}]
    html = gr.render_html(bugs, {}, "run-1", "App", "# md content")
    assert "S0 Critical" in html
    assert "S2 Moderate" in html
    assert "<!doctype html>" in html


def test_render_markdown_sorts_by_severity() -> None:
    bugs = [
        {"severity": "S2", "title": "S2 issue", "diff": {"state": "new"}},
        {"severity": "S0", "title": "S0 issue", "diff": {"state": "new"}},
        {"severity": "S1", "title": "S1 issue", "diff": {"state": "new"}},
    ]
    md = gr.render_markdown(bugs, {}, "run-1", "App")
    s0_pos = md.find("S0 issue")
    s1_pos = md.find("S1 issue")
    s2_pos = md.find("S2 issue")
    assert s0_pos < s1_pos < s2_pos


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "generate_report.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "report" in result.stdout.lower()


def test_cli_end_to_end(scripts_dir: Path, tmp_path: Path) -> None:
    run_dir = tmp_path / "run-x"
    run_dir.mkdir()
    bugs = {"runId": "run-x", "bugs": [
        {"id": "BUG-1", "severity": "S1", "title": "broken", "diff": {"state": "new"},
         "error": {"message": "x"}},
    ]}
    diff = {"runId": "run-x", "summary": {"new": 1, "regression": 0,
                                            "persisting": 0, "fixed": 0}}
    (run_dir / "bugs.json").write_text(json.dumps(bugs), encoding="utf-8")
    (run_dir / "diff.json").write_text(json.dumps(diff), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(scripts_dir / "generate_report.py"),
         "--run-dir", str(run_dir), "--app-name", "TestApp"],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    assert (run_dir / "report.md").is_file()
    assert (run_dir / "index.html").is_file()
