"""Tests for scripts/fingerprint_bugs.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import fingerprint_bugs as fb


def test_normalize_selector() -> None:
    assert fb.normalize_selector("div:nth-child(3) > span") == "div:nth-child > span"
    assert fb.normalize_selector("a:nth-of-type(2)") == "a:nth-of-type"
    assert fb.normalize_selector("") == ""


def test_normalize_url_strips_ids_and_uuids() -> None:
    assert fb.normalize_url("https://x.com/users/123/profile") == "/users/:id/profile"
    assert fb.normalize_url(
        "https://x.com/run/abc123de-1234-1234-1234-123456789abc/info"
    ) == "/run/:uuid/info"
    assert fb.normalize_url("https://x.com/x?id=1&t=2") == "/x"


def test_extract_assertion_type() -> None:
    assert fb.extract_assertion_type("toBeVisible failed") == "toBeVisible"
    assert fb.extract_assertion_type("Expected toHaveURL but got") == "toHaveURL"
    assert fb.extract_assertion_type("TimeoutError exceeded") == "Timeout"
    assert fb.extract_assertion_type("strange") == "Generic"


def test_extract_error_class() -> None:
    assert fb.extract_error_class("TimeoutError: ...") == "TimeoutError"
    assert fb.extract_error_class("AssertionError: x") == "AssertionError"
    assert fb.extract_error_class("plain text") == "AssertionError"


def test_extract_selector_finds_get_by_role() -> None:
    snippet = "await page.getByRole('button', { name: 'Sign in' }).click()"
    assert "getByRole" in fb.extract_selector(snippet, "")


def test_severity_from_signals_a11y_serious() -> None:
    bug = {"issueLine": "a11y[serious] color-contrast: text fails"}
    assert fb.severity_from_signals(bug) == "S1"


def test_severity_override_inline_in_issue_line() -> None:
    bug = {"issueLine": "[severity:S0] auth completely broken on prod"}
    assert fb.severity_from_signals(bug) == "S0"


def test_severity_override_inline_in_title() -> None:
    bug = {"title": "[severity:S1] payment fails", "issueLine": "checkout-button broken"}
    assert fb.severity_from_signals(bug) == "S1"


def test_severity_override_from_spec_file_comment() -> None:
    bug = {"specTitle": "checkout fails", "issueLine": "some non-structured failure"}
    overrides = {"checkout fails": "S0"}
    assert fb.severity_from_signals(bug, overrides) == "S0"


def test_severity_override_from_spec_file_does_not_affect_unrelated_test() -> None:
    bug = {"specTitle": "unrelated test", "issueLine": "a11y[moderate] x: y"}
    overrides = {"checkout fails": "S0"}
    assert fb.severity_from_signals(bug, overrides) == "S2"  # axe-moderate fallback


def test_severity_overrides_from_spec_file_parses_comments(tmp_path: Path) -> None:
    spec = tmp_path / "x.spec.ts"
    spec.write_text(
        "import { test } from '@playwright/test';\n"
        "test.describe('X', () => {\n"
        "  // @severity: S0\n"
        "  test('checkout broken', async () => { });\n"
        "  test('something fine', async () => { });\n"
        "  // @severity: S2\n"
        "  test('minor visual issue', async () => { });\n"
        "});\n",
        encoding="utf-8",
    )
    overrides = fb.severity_overrides_from_spec_file(spec)
    assert overrides.get("checkout broken") == "S0"
    assert overrides.get("minor visual issue") == "S2"
    assert "something fine" not in overrides


def test_severity_overrides_from_missing_file_returns_empty(tmp_path: Path) -> None:
    assert fb.severity_overrides_from_spec_file(tmp_path / "nope.ts") == {}


def test_severity_from_signals_a11y_moderate() -> None:
    bug = {"issueLine": "a11y[moderate] some-rule: ..."}
    assert fb.severity_from_signals(bug) == "S2"


def test_severity_from_signals_heading_jump() -> None:
    bug = {"issueLine": "heading-jump: h1->h3 at \"X\""}
    assert fb.severity_from_signals(bug) == "S2"


def test_severity_from_signals_overflow() -> None:
    bug = {"issueLine": "overflow: scroll @ 390px"}
    assert fb.severity_from_signals(bug) == "S1"


def test_severity_from_signals_auth_critical() -> None:
    bug = {"title": "login flow broken", "error": {"message": "auth failed 500"}}
    assert fb.severity_from_signals(bug) == "S0"


def test_priority_mapping() -> None:
    assert fb.priority_from_severity("S0") == "P0"
    assert fb.priority_from_severity("S1") == "P1"
    assert fb.priority_from_severity("S2") == "P2"
    assert fb.priority_from_severity("S3") == "P3"


def test_compute_fingerprint_stable() -> None:
    bug = {
        "issueLine": "heading-jump: h1->h3 at \"X\"",
        "specFile": "tests/x.spec.ts",
        "error": {"message": "..."},
    }
    fp1 = fb.compute_fingerprint(bug)
    fp2 = fb.compute_fingerprint(bug)
    assert fp1 == fp2
    assert len(fp1) == 8  # 8-hex-char prefix


def test_compute_fingerprint_normalizes_node_count() -> None:
    a = {"issueLine": "a11y[serious] color-contrast: x (3x nodes)", "specFile": "y.ts", "error": {}}
    b = {"issueLine": "a11y[serious] color-contrast: x (10x nodes)", "specFile": "y.ts", "error": {}}
    assert fb.compute_fingerprint(a) == fb.compute_fingerprint(b)


def test_enrich_bug_adds_id_and_tracker() -> None:
    bug = {
        "title": "auth login",
        "issueLine": "a11y[serious] x: y (3x nodes)",
        "error": {"message": "", "snippet": "", "location": {}},
    }
    enriched = fb.enrich_bug(bug, "run-1")
    assert enriched["id"].startswith("BUG-")
    assert enriched["severity"] == "S1"
    assert enriched["priority"] == "P1"
    assert "linear" in enriched["trackerMappings"]
    assert "github" in enriched["trackerMappings"]
    assert "jira" in enriched["trackerMappings"]


def test_diff_runs_marks_new_bugs() -> None:
    cur = [{"fingerprintHash": "abc", "title": "t", "occurrenceCount": 1}]
    prev: list = []
    result = fb.diff_runs(cur, prev)
    assert result["summary"]["new"] == 1
    assert result["bugs"][0]["diff"]["state"] == "new"


def test_diff_runs_marks_persisting() -> None:
    cur = [{"fingerprintHash": "abc", "title": "t"}]
    prev = [{"fingerprintHash": "abc", "lastSeenRunId": "r0", "firstSeenRunId": "r0",
              "occurrenceCount": 1}]
    result = fb.diff_runs(cur, prev)
    assert result["summary"]["persisting"] == 1
    assert result["bugs"][0]["diff"]["state"] == "persisting"
    assert result["bugs"][0]["occurrenceCount"] == 2


def test_diff_runs_marks_fixed() -> None:
    cur: list = []
    prev = [{"fingerprintHash": "abc", "title": "old", "lastSeenRunId": "r0",
              "diff": {"state": "persisting"}}]
    result = fb.diff_runs(cur, prev)
    assert result["summary"]["fixed"] == 1
    assert any(b["diff"]["state"] == "fixed" for b in result["bugs"])


def test_diff_runs_marks_regression() -> None:
    cur = [{"fingerprintHash": "abc", "title": "t"}]
    prev = [{"fingerprintHash": "abc", "diff": {"state": "fixed"}, "lastSeenRunId": "r0"}]
    result = fb.diff_runs(cur, prev)
    assert result["summary"]["regression"] == 1
    assert result["bugs"][0]["diff"]["state"] == "regression"


def test_cli_end_to_end(scripts_dir: Path, tmp_path: Path, sample_raw_bugs: dict) -> None:
    raw_path = tmp_path / "raw.json"
    out_path = tmp_path / "bugs.json"
    diff_path = tmp_path / "diff.json"
    raw_path.write_text(json.dumps(sample_raw_bugs), encoding="utf-8")
    subprocess.run(
        [sys.executable, str(scripts_dir / "fingerprint_bugs.py"),
         "--current", str(raw_path), "--out", str(out_path), "--diff", str(diff_path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    bugs = json.loads(out_path.read_text(encoding="utf-8"))
    assert "bugs" in bugs
    assert bugs["bugs"][0]["id"].startswith("BUG-")
    diff = json.loads(diff_path.read_text(encoding="utf-8"))
    assert diff["summary"]["new"] >= 1
