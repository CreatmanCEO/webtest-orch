#!/usr/bin/env python3
"""generate_report.py — emit markdown + index.html + bugs.json triple.

Reads bugs.json (post-fingerprint) and optional diff.json from a run directory,
emits human-readable report.md and a self-contained index.html (no external CDN).

Black-box. Invoke with --help.

Usage:
    generate_report.py --run-dir reports/run-2026-04-28-1430
    generate_report.py --run-dir reports/<run-id> --bugs bugs.json --diff diff.json
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
VERDICT_EMOJI = {"new": "🆕", "regression": "🚨", "persisting": "⚠️", "fixed": "✅"}
SEV_EMOJI = {"S0": "🔴", "S1": "🟠", "S2": "🟡", "S3": "🟢"}


def strip_ansi(s: str) -> str:
    return _ANSI_RE.sub("", s or "")


def severity_breakdown(bugs: list[dict]) -> dict[str, int]:
    out = {"S0": 0, "S1": 0, "S2": 0, "S3": 0}
    for b in bugs:
        sev = b.get("severity") or "S2"
        out[sev] = out.get(sev, 0) + 1
    return out


def render_markdown(bugs: list, summary: dict, run_id: str, app_name: str) -> str:
    sev = severity_breakdown(bugs)
    total = len(bugs)
    open_bugs = [b for b in bugs if (b.get("diff") or {}).get("state") != "fixed"]
    fixed_bugs = [b for b in bugs if (b.get("diff") or {}).get("state") == "fixed"]

    open_count = len(open_bugs)
    if sev.get("S0", 0) > 0:
        verdict = f"❌ NOT SHIP-READY — {sev['S0']} S0 critical bug(s)"
    elif sev.get("S1", 0) > 0:
        verdict = f"⚠️ HOLD — {sev['S1']} S1 major bug(s)"
    elif open_count > 0:
        minor = sev.get("S2", 0) + sev.get("S3", 0)
        s = "" if minor == 1 else "s"
        verdict = f"✅ SHIP-READY ({minor} minor issue{s} open — review before next release)"
    else:
        verdict = "✅ SHIP-READY (clean run)"

    lines = [
        f"# Test run — {app_name}",
        f"**Run ID:** {run_id}  ·  **Generated:** {datetime.now(timezone.utc).isoformat()}",
        "",
        f"**Verdict:** {verdict}",
        "",
        "## 📊 Summary",
        "",
        "| Metric | Value |",
        "|---|---:|",
        f"| Total bugs | {total} |",
        f"| └ {SEV_EMOJI['S0']} S0 Critical | {sev.get('S0', 0)} |",
        f"| └ {SEV_EMOJI['S1']} S1 Major | {sev.get('S1', 0)} |",
        f"| └ {SEV_EMOJI['S2']} S2 Moderate | {sev.get('S2', 0)} |",
        f"| └ {SEV_EMOJI['S3']} S3 Minor | {sev.get('S3', 0)} |",
        f"| Open | {len(open_bugs)} |",
        f"| Fixed (vs prev run) | {len(fixed_bugs)} |",
    ]

    if summary:
        lines += [
            "",
            "## 🔁 Run diff",
            "",
            "| State | Count |",
            "|---|---:|",
            f"| 🆕 New | {summary.get('new', 0)} |",
            f"| 🚨 Regression | {summary.get('regression', 0)} |",
            f"| ⚠️ Persisting | {summary.get('persisting', 0)} |",
            f"| ✅ Fixed | {summary.get('fixed', 0)} |",
        ]

    # Sort: S0 first, then S1, then S2, then S3
    sev_order = {"S0": 0, "S1": 1, "S2": 2, "S3": 3}
    sorted_open = sorted(
        open_bugs,
        key=lambda b: (sev_order.get(b.get("severity") or "S2", 4), b.get("title") or ""),
    )

    if sorted_open:
        lines += ["", "## 🚨 Open issues", ""]
        for i, b in enumerate(sorted_open, 1):
            sev = b.get("severity") or "S2"
            pri = b.get("priority") or "P2"
            state = (b.get("diff") or {}).get("state") or "new"
            emoji = SEV_EMOJI.get(sev, "•") + " " + VERDICT_EMOJI.get(state, "")
            title = b.get("title") or "untitled"
            bug_id = b.get("id") or "BUG-?"
            occ = b.get("occurrenceCount", 1)
            lines += [
                f"### {i}. [{bug_id}] {sev}/{pri} — {title}  {emoji}",
                "",
                f"- **State:** `{state}`  ·  **Occurrences:** {occ}",
                f"- **Spec:** `{b.get('specFile', '?')}` :: {b.get('specTitle', '?')}",
                f"- **Project:** `{b.get('project', '?')}`",
            ]
            err = b.get("error") or {}
            msg = strip_ansi((err.get("message") or "")).strip()
            if msg:
                lines += ["", "```", msg[:600], "```"]
            screenshots = b.get("screenshots") or []
            traces = b.get("traces") or []
            if screenshots or traces:
                refs = []
                for s in screenshots[:3]:
                    refs.append(f"[📸 screenshot]({s})")
                for t in traces[:1]:
                    refs.append(f"[🎬 trace]({t})")
                lines += ["", " · ".join(refs)]
            lines += [""]

    if fixed_bugs:
        lines += ["", "## ✅ Newly fixed", ""]
        for b in fixed_bugs:
            lines += [f"- [{b.get('id')}] {b.get('title', '?')}"]

    lines += ["", "---", "", f"_Report generated by webapp-test-orchestrator. bugs.json + diff.json sit alongside this file._"]
    return "\n".join(lines) + "\n"


def render_html(bugs: list, summary: dict, run_id: str, app_name: str, md: str) -> str:
    sev = severity_breakdown(bugs)
    total = len(bugs)
    body_md_html = html.escape(md)
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>{html.escape(app_name)} — {html.escape(run_id)}</title>
<style>
  body {{ font: 14px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 980px; margin: 2em auto; padding: 0 1em; color: #1f2937; }}
  h1, h2, h3 {{ line-height: 1.2; }}
  .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: .5em; margin: 1em 0; }}
  .card {{ padding: 1em; border-radius: 6px; text-align: center; }}
  .card.s0 {{ background: #fee2e2; }}
  .card.s1 {{ background: #fed7aa; }}
  .card.s2 {{ background: #fef3c7; }}
  .card.s3 {{ background: #dcfce7; }}
  .card .n {{ font: bold 24px monospace; }}
  pre {{ background: #f3f4f6; padding: 1em; border-radius: 6px; overflow: auto; white-space: pre-wrap; }}
  code {{ font: 12px/1 "SF Mono", Monaco, Consolas, monospace; background: #f3f4f6;
    padding: 1px 4px; border-radius: 3px; }}
  .verdict {{ padding: 1em; border-radius: 6px; font-weight: 600; }}
  .verdict.ok {{ background: #dcfce7; }}
  .verdict.warn {{ background: #fef3c7; }}
  .verdict.bad {{ background: #fee2e2; }}
</style>
</head>
<body>
<h1>{html.escape(app_name)}</h1>
<p>Run ID: <code>{html.escape(run_id)}</code></p>
<div class="summary">
  <div class="card s0"><div class="n">{sev.get('S0', 0)}</div>S0 Critical</div>
  <div class="card s1"><div class="n">{sev.get('S1', 0)}</div>S1 Major</div>
  <div class="card s2"><div class="n">{sev.get('S2', 0)}</div>S2 Moderate</div>
  <div class="card s3"><div class="n">{sev.get('S3', 0)}</div>S3 Minor</div>
</div>
<p>Total bugs: <strong>{total}</strong></p>
<hr>
<pre>{body_md_html}</pre>
</body>
</html>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Generate markdown + HTML report from bugs.json + diff.json.")
    p.add_argument("--run-dir", required=True, help="reports/<run-id> directory")
    p.add_argument("--bugs", help="bugs.json path (default: <run-dir>/bugs.json)")
    p.add_argument("--diff", help="diff.json path (default: <run-dir>/diff.json)")
    p.add_argument(
        "--app-name",
        default=None,
        help="App display name (default: parent dir name from --run-dir)",
    )
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.is_dir():
        run_dir.mkdir(parents=True, exist_ok=True)
    run_id = run_dir.name

    bugs_path = Path(args.bugs) if args.bugs else (run_dir / "bugs.json")
    diff_path = Path(args.diff) if args.diff else (run_dir / "diff.json")
    app_name = args.app_name or run_dir.parent.parent.name or "webapp"

    bugs: list = []
    if bugs_path.is_file():
        bugs_data = json.loads(bugs_path.read_text(encoding="utf-8"))
        bugs = bugs_data.get("bugs", []) if isinstance(bugs_data, dict) else bugs_data

    summary: dict = {}
    if diff_path.is_file():
        diff_data = json.loads(diff_path.read_text(encoding="utf-8"))
        summary = diff_data.get("summary", {}) if isinstance(diff_data, dict) else {}

    md = render_markdown(bugs, summary, run_id, app_name)
    html_doc = render_html(bugs, summary, run_id, app_name, md)

    md_path = run_dir / "report.md"
    html_path = run_dir / "index.html"

    md_path.write_text(md, encoding="utf-8")
    html_path.write_text(html_doc, encoding="utf-8")

    print(f"[generate_report] {len(bugs)} bugs")
    print(f"[generate_report] markdown → {md_path}")
    print(f"[generate_report] html     → {html_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
