#!/usr/bin/env python3
"""fingerprint_bugs.py — composite fingerprint + run diff.

Reads raw_bugs.json from the current run (and optionally bugs.json from the
previous run), writes bugs.json with stable IDs + run-diff state.

Black-box. Invoke with --help.

Fingerprint composition: SHA-256 first 8 hex chars of
  (normalized_selector | assertionType | errorClass | urlPathTemplate | message_first_80)

Normalization:
  - selector  : strip :nth-child(N) → :nth-child
  - URL path  : /users/123 → /users/:id, UUIDs → :uuid, query strings stripped
  - message   : first 80 chars
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


SELECTOR_NORMS = [
    (re.compile(r":nth-child\(\d+\)"), ":nth-child"),
    (re.compile(r":nth-of-type\(\d+\)"), ":nth-of-type"),
]

URL_NORMS = [
    (re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I), ":uuid"),
    (re.compile(r"/\d+(?=/|$|\?)"), "/:id"),
    (re.compile(r"\?.*$"), ""),
]


def normalize_selector(s: str) -> str:
    if not s:
        return ""
    out = s
    for pat, repl in SELECTOR_NORMS:
        out = pat.sub(repl, out)
    return out


def normalize_url(url: str) -> str:
    if not url:
        return ""
    m = re.match(r"^https?://[^/]+(.*)", url)
    path = m.group(1) if m else url
    out = path
    for pat, repl in URL_NORMS:
        out = pat.sub(repl, out)
    return out


def extract_assertion_type(error_msg: str) -> str:
    msg = error_msg or ""
    for kw in ("toBeVisible", "toHaveText", "toHaveURL", "toHaveTitle",
               "toHaveAttribute", "toContainText", "toEqual", "toBe"):
        if kw in msg:
            return kw
    if re.search(r"timeout|Timeout", msg):
        return "Timeout"
    if "Navigation" in msg:
        return "Navigation"
    return "Generic"


def extract_error_class(error_msg: str) -> str:
    msg = error_msg or ""
    m = re.match(r"^([A-Z][A-Za-z]+(Error|Exception)):", msg)
    if m:
        return m.group(1)
    if re.search(r"timeout|Timeout", msg):
        return "TimeoutError"
    return "AssertionError"


def extract_selector(error_snippet: str, error_msg: str) -> str:
    haystack = (error_snippet or "") + " " + (error_msg or "")
    for prefix in ("getByRole", "getByLabel", "getByText", "getByTestId",
                   "getByPlaceholder", "getByAltText", "getByTitle", "locator"):
        m = re.search(rf"{prefix}\([^)]+\)", haystack)
        if m:
            return m.group(0)
    return ""


def severity_from_signals(bug: dict) -> str:
    """Infer severity from title + error + issueLine.

    issueLine takes priority because it's the structured tag from spec.ts.tmpl
    (e.g. 'a11y[critical] ...', 'heading-jump: ...', 'touch-target: ...').
    """
    issue_line = (bug.get("issueLine") or "").lower()

    # ── Highest-priority signals: structured issue tags from spec template ──
    if issue_line:
        # axe impact maps directly
        if "a11y[critical]" in issue_line or "a11y[serious]" in issue_line:
            return "S1"
        if "a11y[moderate]" in issue_line:
            return "S2"
        if "a11y[minor]" in issue_line:
            return "S3"
        # other structured tags
        if issue_line.startswith("heading-jump:"):
            return "S2"
        if issue_line.startswith("touch-target:"):
            return "S2"
        if issue_line.startswith("overflow:"):
            return "S1"
        if issue_line.startswith("html-lang:"):
            return "S2"
        if issue_line.startswith("title:"):
            return "S3"

    title = (bug.get("title") or "").lower()
    err = (bug.get("error") or {}).get("message", "").lower()
    text = title + " " + err

    if any(k in text for k in [" auth", "login", "logout", "checkout", "payment",
                                 "5xx", " 500 ", " 502 ", " 503 ", "data loss"]):
        return "S0"
    if any(k in text for k in ["uncaught", "pageerror", "hydration"]):
        return "S0"
    if any(k in text for k in ["form", "submit", "button", " nav ", " 404 "]):
        return "S1"
    if any(k in text for k in ["strict mode violation", "resolved to 2", "resolved to 3"]):
        return "S2"  # locator quality, not user-visible bug
    if any(k in text for k in ["pixel", "screenshot", "snapshot", "visual",
                                 "alignment"]):
        return "S3"
    if any(k in text for k in ["a11y", "accessibility", "aria", "wcag",
                                 "contrast", "alt text"]):
        return "S2"
    return "S2"


def priority_from_severity(sev: str) -> str:
    return {"S0": "P0", "S1": "P1", "S2": "P2", "S3": "P3"}.get(sev, "P2")


def compute_fingerprint(bug: dict) -> str:
    err = bug.get("error") or {}
    msg = (err.get("message") or "")[:120]
    issue_line = (bug.get("issueLine") or "").strip()
    selector = normalize_selector(extract_selector(err.get("snippet", ""), msg))
    assertion = extract_assertion_type(msg)
    error_class = extract_error_class(msg)
    loc = err.get("location") or {}
    url_path = normalize_url(loc.get("file") or "")
    spec_file = bug.get("specFile") or ""

    # Issue line is most discriminating when present (one bug per issue)
    if issue_line:
        # Strip variable node counts: "(3x nodes)" or "(10× nodes)" → ""
        normalized_issue = re.sub(r"\s*\(\d+\s*[x×]\s*nodes\)", "", issue_line)
        # Strip viewport sizes "390x844" → "WxH" so the same bug across
        # viewports collapses to one fingerprint
        normalized_issue = re.sub(r"\d+x\d+", "WxH", normalized_issue)
        composite = f"{spec_file}|{normalized_issue}"
    else:
        composite = f"{selector}|{assertion}|{error_class}|{url_path}|{msg[:80]}|{spec_file}"
    return hashlib.sha256(composite.encode("utf-8")).hexdigest()[:8]


def enrich_bug(bug: dict, run_id: str) -> dict:
    fp = compute_fingerprint(bug)
    sev = severity_from_signals(bug)
    pri = priority_from_severity(sev)
    return {
        **bug,
        "id": f"BUG-{fp}",
        "fingerprintHash": fp,
        "severity": sev,
        "priority": pri,
        "lastSeenRunId": run_id,
        "trackerMappings": {
            "linear": {"priority": {"S0": 1, "S1": 2, "S2": 3, "S3": 4}.get(sev, 3)},
            "github": {"labels": ["bug", f"severity/{sev.lower()}", f"priority/{pri.lower()}"]},
            "jira": {
                "issueType": "Bug",
                "priorityName": {"P0": "Highest", "P1": "High",
                                  "P2": "Medium", "P3": "Low"}.get(pri, "Medium"),
            },
        },
    }


def diff_runs(current: list[dict], previous: list[dict]) -> dict:
    prev_map = {b.get("fingerprintHash"): b for b in previous if b.get("fingerprintHash")}
    summary = {"new": 0, "regression": 0, "persisting": 0, "fixed": 0}
    out: list = []
    cur_hashes: set = set()

    for bug in current:
        fp = bug.get("fingerprintHash")
        cur_hashes.add(fp)
        prev = prev_map.get(fp)

        if prev is None:
            state = "new"
        elif (prev.get("diff") or {}).get("state") == "fixed":
            state = "regression"
        else:
            state = "persisting"
            if prev.get("firstSeenRunId"):
                bug["firstSeenRunId"] = prev["firstSeenRunId"]
            bug["occurrenceCount"] = (prev.get("occurrenceCount") or 1) + 1

        bug["diff"] = {
            "state": state,
            "previousRunId": prev.get("lastSeenRunId") if prev else None,
        }
        summary[state] += 1
        out.append(bug)

    # Newly fixed: present in previous, absent in current, was open
    for fp, prev in prev_map.items():
        if fp in cur_hashes:
            continue
        if (prev.get("diff") or {}).get("state") == "fixed":
            continue
        prev_copy = dict(prev)
        prev_copy["diff"] = {"state": "fixed", "previousRunId": prev.get("lastSeenRunId")}
        out.append(prev_copy)
        summary["fixed"] += 1

    return {"bugs": out, "summary": summary}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fingerprint bugs and compute run diff.")
    p.add_argument("--current", required=True, help="raw_bugs.json from current run")
    p.add_argument("--previous", help="bugs.json from previous run (optional)")
    p.add_argument("--out", required=True, help="output bugs.json with fingerprints + diff")
    p.add_argument("--diff", help="optional diff summary file")
    args = p.parse_args(argv)

    cur_path = Path(args.current)
    if not cur_path.is_file():
        print(f"current file not found: {cur_path}", file=sys.stderr)
        return 1

    cur_data = json.loads(cur_path.read_text(encoding="utf-8"))
    cur_bugs = cur_data.get("bugs", []) if isinstance(cur_data, dict) else cur_data
    run_id = (cur_data.get("runId")
              if isinstance(cur_data, dict) else None) or cur_path.parent.name

    prev_bugs: list = []
    if args.previous and Path(args.previous).is_file():
        prev_data = json.loads(Path(args.previous).read_text(encoding="utf-8"))
        prev_bugs = prev_data.get("bugs", []) if isinstance(prev_data, dict) else prev_data

    enriched = [enrich_bug(b, run_id) for b in cur_bugs]
    diff_result = diff_runs(enriched, prev_bugs)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"runId": run_id, "bugs": diff_result["bugs"]},
                    indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[fingerprint_bugs] {len(diff_result['bugs'])} bugs → {out_path}")

    if args.diff:
        diff_path = Path(args.diff)
        diff_path.parent.mkdir(parents=True, exist_ok=True)
        diff_path.write_text(
            json.dumps({
                "runId": run_id,
                "summary": diff_result["summary"],
                "totalBugs": len(diff_result["bugs"]),
            }, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"[fingerprint_bugs] diff summary → {diff_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
