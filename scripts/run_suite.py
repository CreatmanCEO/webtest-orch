#!/usr/bin/env python3
"""run_suite.py — wrap `npx playwright test`, collect artifacts, emit raw_bugs.json.

Black-box. Invoke with --help; do not read source unless --help doesn't cover the case.

Usage:
    run_suite.py --out reports/run-2026-04-28-1430 --project chromium-desktop
    run_suite.py --out reports/<run-id> --project chromium-desktop chromium-mobile
    run_suite.py --out reports/<run-id> --project all
    run_suite.py --out reports/<run-id> --skip-run        # only normalize existing results.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
# Match the issues block: "N issues found:\n" followed by ONLY lines that start with "  - "
# Stop at the first non-matching line (empty, Expected:, Received:, Array, etc.)
_ISSUES_HEADER_RE = re.compile(r"\d+\s+issues found:\s*\n")
_ISSUE_LINE_RE = re.compile(r"^\s+-\s+(.+?)\s*$")


def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s or "")


def extract_issues_from_error(msg: str) -> list[str]:
    """If the spec used issues[] collector, the error message contains
    'N issues found:\\n  - first\\n  - second...\\n\\nExpected: ...'.

    Return clean issue lines. Stop at the first line that isn't an issue (empty,
    Expected:, Received:, Array [..., diff-prefix lines like '+ "..."').
    """
    if not msg:
        return []
    clean = strip_ansi(msg)
    m = _ISSUES_HEADER_RE.search(clean)
    if not m:
        return []
    rest = clean[m.end():]
    issues: list[str] = []
    for line in rest.split("\n"):
        if not line.strip():
            break  # blank line ends the issues block
        match = _ISSUE_LINE_RE.match(line)
        if not match:
            break  # non-bullet line ends the block
        text = match.group(1).strip()
        # Sanity: skip if it looks like an Expected/Received marker that snuck in
        if text.startswith(("Expected:", "Received:", "Array")):
            break
        issues.append(text)
    return issues


def run_playwright(project_root: Path, out_dir: Path, projects: list[str], grep: str | None) -> int:
    cmd = ["npx", "playwright", "test", "--reporter=list,json,html"]

    if projects and projects != ["all"]:
        for p in projects:
            cmd.extend(["--project", p])

    if grep:
        cmd.extend(["--grep", grep])

    env = os.environ.copy()
    env["PLAYWRIGHT_HTML_REPORT"] = str(out_dir / "html")
    env["PLAYWRIGHT_JSON_OUTPUT_NAME"] = str(out_dir / "results.json")
    env["PW_TEST_HTML_REPORT_OPEN"] = "never"

    print(f"[run_suite] cwd: {project_root}")
    print(f"[run_suite] running: {' '.join(cmd)}")

    proc = subprocess.run(cmd, cwd=str(project_root), env=env, shell=os.name == "nt")
    return proc.returncode


def _walk_suite(suite: dict, bugs: list, run_id: str) -> None:
    for spec in suite.get("specs", []):
        for test_case in spec.get("tests", []):
            for result in test_case.get("results", []):
                if result.get("status") not in ("failed", "timedOut"):
                    continue
                err = result.get("error") or {}
                project = test_case.get("projectName", "unknown")
                file_path = spec.get("file", "")
                title_parts = [t for t in (suite.get("title", ""), spec.get("title", "")) if t]
                title = " > ".join(title_parts)

                attachments = result.get("attachments", []) or []
                screenshots = [a.get("path") for a in attachments if a.get("contentType", "").startswith("image/")]
                traces = [a.get("path") for a in attachments if "trace" in (a.get("name", "")).lower()]

                raw_msg = err.get("message", "") or ""
                clean_msg = strip_ansi(raw_msg)
                clean_stack = strip_ansi(err.get("stack", "") or "")
                clean_snippet = strip_ansi(err.get("snippet", "") or "")

                base_record = {
                    "specFile": file_path,
                    "specTitle": spec.get("title"),
                    "project": project,
                    "status": result.get("status"),
                    "duration_ms": result.get("duration"),
                    "retry": result.get("retry", 0),
                    "screenshots": screenshots,
                    "traces": traces,
                    "discoveredAt": datetime.now(timezone.utc).isoformat(),
                    "firstSeenRunId": run_id,
                    "lastSeenRunId": run_id,
                    "occurrenceCount": 1,
                }

                # If spec used issues[] collector, split the test failure
                # into ONE bug record per issue. Otherwise emit ONE record.
                issues = extract_issues_from_error(clean_msg)
                if issues:
                    for issue_line in issues:
                        # Normalize issue label for fingerprint stability:
                        # "a11y[serious] color-contrast: ..." → category=a11y, severity hint inside
                        bugs.append({
                            **base_record,
                            "title": f"{title} :: {issue_line[:90]}",
                            "issueLine": issue_line,
                            "error": {
                                "message": issue_line,
                                "stack": clean_stack[:500],
                                "snippet": clean_snippet,
                                "location": err.get("location", {}),
                            },
                        })
                else:
                    bugs.append({
                        **base_record,
                        "title": title or spec.get("title", "untitled"),
                        "error": {
                            "message": clean_msg,
                            "stack": clean_stack,
                            "snippet": clean_snippet,
                            "location": err.get("location", {}),
                        },
                    })
    for sub in suite.get("suites", []):
        _walk_suite(sub, bugs, run_id)


def normalize_results(results_path: Path, out_path: Path, run_id: str) -> tuple[int, int, int]:
    """Convert Playwright JSON reporter output to raw_bugs.json. Returns (rc, total, failed)."""
    if not results_path.is_file():
        print(f"[run_suite] missing {results_path}", file=sys.stderr)
        return 1, 0, 0

    with open(results_path, encoding="utf-8") as f:
        results = json.load(f)

    bugs: list = []
    for suite in results.get("suites", []):
        _walk_suite(suite, bugs, run_id)

    stats = results.get("stats", {})
    total = stats.get("expected", 0) + stats.get("unexpected", 0) + stats.get("flaky", 0) + stats.get("skipped", 0)
    failed = stats.get("unexpected", 0)

    out_path.write_text(
        json.dumps({"runId": run_id, "stats": stats, "bugs": bugs}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[run_suite] {len(bugs)} failures of {total} tests → {out_path}")
    return 0, total, failed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run Playwright suite and collect artifacts.")
    parser.add_argument("--out", required=True, help="Output dir for this run (reports/<run-id>)")
    parser.add_argument(
        "--project",
        nargs="*",
        default=["chromium-desktop"],
        help="Playwright project(s); use 'all' for every project (default: chromium-desktop)",
    )
    parser.add_argument("--grep", help="Pass-through to playwright --grep")
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Only normalize existing results.json in --out",
    )
    parser.add_argument(
        "--cwd",
        default=".",
        help="Project root (where playwright.config.ts lives)",
    )
    args = parser.parse_args(argv)

    project_root = Path(args.cwd).resolve()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    run_id = out_dir.name

    rc_pw = 0
    if not args.skip_run:
        rc_pw = run_playwright(project_root, out_dir, args.project, args.grep)
        print(f"[run_suite] playwright exit code: {rc_pw}")

    results_path = out_dir / "results.json"
    if not results_path.is_file():
        # Fallbacks: look in test-results/ at project root
        for cand in (
            project_root / "test-results" / "results.json",
            project_root / "playwright-report" / "results.json",
        ):
            if cand.is_file():
                shutil.copy2(cand, results_path)
                break

    rc_norm, _total, _failed = normalize_results(results_path, out_dir / "raw_bugs.json", run_id)

    return rc_pw if not args.skip_run else rc_norm


if __name__ == "__main__":
    sys.exit(main())
