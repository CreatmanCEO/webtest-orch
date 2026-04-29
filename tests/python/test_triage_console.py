"""Tests for scripts/triage_console.py."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import triage_console as tc


def test_classify_gtm_is_noise() -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.classify("GET https://www.googletagmanager.com/gtag/js", noise, bugs)
    assert result["decision"] == "ignore"
    assert result["category"] == "gtm"


def test_classify_hydration_is_bug_s1() -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.classify("Hydration failed because text content did not match", noise, bugs)
    assert result["decision"] == "report"
    assert result["severity"] == "S1"
    assert result["category"] == "hydration-mismatch"


def test_classify_typeerror_is_bug_s0() -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.classify("Uncaught TypeError: Cannot read prop 'x'", noise, bugs)
    assert result["decision"] == "report"
    assert result["severity"] == "S0"


def test_classify_unknown_needs_llm() -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.classify("Some entirely novel warning", noise, bugs)
    assert result["decision"] == "needs-llm"
    assert result["category"] == "unknown"


def test_classify_user_extra_pattern() -> None:
    noise, bugs = tc.compile_patterns(["my-app-specific-warning"])
    result = tc.classify("my-app-specific-warning fired", noise, bugs)
    assert result["decision"] == "ignore"
    assert result["category"] == "user-ignore"


def test_classify_stripe_deprecation_is_noise() -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.classify("[Stripe.js] You called .createToken with deprecated arg", noise, bugs)
    assert result["decision"] == "ignore"


def test_triage_buckets_correctly(sample_console_messages: list[dict]) -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.triage(sample_console_messages, noise, bugs)
    assert result["stats"]["total"] == 5
    assert result["stats"]["ignored"] >= 2
    assert result["stats"]["reported"] >= 1
    assert result["stats"]["needsLlm"] >= 1


def test_triage_handles_string_messages() -> None:
    noise, bugs = tc.compile_patterns([])
    result = tc.triage(["plain string message", "GET googletagmanager.com"], noise, bugs)
    assert result["stats"]["total"] == 2


def test_cli_help_runs(scripts_dir: Path) -> None:
    result = subprocess.run(
        [sys.executable, str(scripts_dir / "triage_console.py"), "--help"],
        capture_output=True, text=True, check=True, encoding="utf-8",
    )
    assert "Triage browser console" in result.stdout


def test_cli_writes_output(
    scripts_dir: Path, tmp_path: Path, sample_console_messages: list[dict]
) -> None:
    in_path = tmp_path / "console.json"
    out_path = tmp_path / "triaged.json"
    in_path.write_text(json.dumps(sample_console_messages), encoding="utf-8")

    subprocess.run(
        [sys.executable, str(scripts_dir / "triage_console.py"),
         "--input", str(in_path), "--out", str(out_path)],
        check=True, capture_output=True, text=True, encoding="utf-8",
    )
    data = json.loads(out_path.read_text(encoding="utf-8"))
    assert "stats" in data
    assert data["stats"]["total"] == 5
