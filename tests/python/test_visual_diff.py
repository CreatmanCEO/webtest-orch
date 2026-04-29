"""Tests for scripts/visual_diff.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import visual_diff as vd


def test_make_task_returns_none_without_image_path() -> None:
    failure = {"specFile": "x.spec.ts", "actual": None, "expected": None, "diff": None}
    assert vd.make_task(failure) is None


def test_make_task_uses_diff_path_first() -> None:
    failure = {
        "specFile": "x.spec.ts",
        "specTitle": "test",
        "project": "chromium-mobile",
        "actual": "/path/actual.png",
        "expected": "/path/expected.png",
        "diff": "/path/diff.png",
        "errorMessage": "snapshot mismatch",
    }
    task = vd.make_task(failure)
    assert task is not None
    assert "diff.png" in task["imagePath"]
    assert task["viewport"] == "390×844"
    assert "<verdict>" in task["suggestedPrompt"]


def test_make_task_falls_back_to_actual_when_no_diff() -> None:
    failure = {
        "specFile": "x.spec.ts",
        "actual": "/path/actual.png",
        "diff": None,
    }
    task = vd.make_task(failure)
    assert task is not None
    assert "actual.png" in task["imagePath"]


def test_viewport_lookup_for_known_projects() -> None:
    for project, expected in [
        ("chromium-desktop", "1920×1080"),
        ("chromium-laptop", "1366×768"),
        ("chromium-mobile", "390×844"),
        ("pixel5", "393×851"),
        ("mobile-safari", "390×844"),
    ]:
        task = vd.make_task({"specFile": "x.ts", "project": project, "diff": "/x.png"})
        assert task["viewport"] == expected


def test_viewport_unknown_for_custom_project() -> None:
    task = vd.make_task({"specFile": "x.ts", "project": "weird-project", "diff": "/x.png"})
    assert "unknown" in task["viewport"]


def test_find_visual_failures_extracts_screenshot_failures(tmp_path: Path) -> None:
    results = {
        "stats": {},
        "suites": [{
            "title": "Visual",
            "specs": [{"title": "homepage", "file": "v.spec.ts", "tests": [{
                "projectName": "chromium-desktop",
                "results": [{
                    "status": "failed",
                    "error": {"message": "expected toHaveScreenshot, snapshot mismatch"},
                    "attachments": [
                        {"name": "actual", "path": "/a.png"},
                        {"name": "expected", "path": "/e.png"},
                        {"name": "diff", "path": "/d.png"},
                    ],
                }],
            }]}],
            "suites": [],
        }],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")
    failures = vd.find_visual_failures(results_path)
    assert len(failures) == 1
    assert failures[0]["actual"] == "/a.png"
    assert failures[0]["expected"] == "/e.png"
    assert failures[0]["diff"] == "/d.png"


def test_find_visual_failures_skips_non_screenshot_failures(tmp_path: Path) -> None:
    results = {
        "stats": {},
        "suites": [{
            "title": "X",
            "specs": [{"title": "t", "file": "x.ts", "tests": [{
                "projectName": "chromium",
                "results": [{
                    "status": "failed",
                    "error": {"message": "totally unrelated assertion"},
                    "attachments": [],
                }],
            }]}],
            "suites": [],
        }],
    }
    results_path = tmp_path / "results.json"
    results_path.write_text(json.dumps(results), encoding="utf-8")
    failures = vd.find_visual_failures(results_path)
    assert failures == []


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "visual_diff.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "vision" in result.stdout.lower()
