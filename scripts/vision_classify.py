#!/usr/bin/env python3
"""vision_classify.py — validate a vision-classification verdict from a Task subagent.

This script does NOT call any LLM. The orchestrator skill dispatches a Task
subagent (general-purpose) using the prompt produced by visual_diff.py and
captures the subagent's text response. Pipe that response into this script
to validate the format and append it to the bugs.json record.

Black-box. Invoke with --help.

Usage:
    echo "bug-S2: horizontal overflow in .product-grid at 390×844" | \\
      vision_classify.py --task-id img-checkout-001 --bugs reports/<run-id>/bugs.json

    vision_classify.py --verdict-file verdict.txt --task-id img-001 --bugs ...
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


VALID_VERDICTS = ("noise", "redesign", "bug-S0", "bug-S1", "bug-S2", "bug-S3")
VERDICT_PATTERN = re.compile(
    r"^\s*(noise|redesign|bug-(S0|S1|S2|S3))\s*:\s*(.+?)\s*$",
    re.IGNORECASE,
)


def parse_verdict(text: str) -> dict:
    if not text:
        return {"valid": False, "reason": "empty input"}
    # Take first non-empty line
    lines = [ln for ln in text.splitlines() if ln.strip()]
    if not lines:
        return {"valid": False, "reason": "no non-empty lines"}
    first = lines[0].strip()
    m = VERDICT_PATTERN.match(first)
    if not m:
        return {
            "valid": False,
            "reason": f"could not parse verdict line; expected '<verdict>: <reason>', got: {first[:80]}",
            "rawFirstLine": first,
        }
    verdict = m.group(1).lower()
    reason = m.group(3).strip()
    severity = None
    decision = "ignore"
    if verdict.startswith("bug-"):
        severity = verdict.split("-", 1)[1].upper()
        decision = "report"
    elif verdict == "redesign":
        decision = "regenerate-baseline"
    return {
        "valid": True,
        "verdict": verdict,
        "severity": severity,
        "decision": decision,
        "reason": reason,
        "rawFirstLine": first,
    }


def append_to_bugs(bugs_path: Path, task_id: str, parsed: dict) -> int:
    if not bugs_path.is_file():
        print(f"bugs file not found: {bugs_path}", file=sys.stderr)
        return 1
    data = json.loads(bugs_path.read_text(encoding="utf-8"))
    bugs = data.get("bugs", []) if isinstance(data, dict) else data
    bugs.append({
        "id": f"VIS-{task_id}",
        "title": f"Visual: {parsed.get('reason', '')[:60]}",
        "severity": parsed.get("severity") or "S3",
        "priority": {"S0": "P0", "S1": "P1", "S2": "P2", "S3": "P3"}.get(parsed.get("severity") or "S3", "P3"),
        "category": "visual",
        "visionVerdict": parsed.get("verdict"),
        "visionDecision": parsed.get("decision"),
        "visionReason": parsed.get("reason"),
    })
    if isinstance(data, dict):
        data["bugs"] = bugs
    else:
        data = bugs
    bugs_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"[vision_classify] appended VIS-{task_id} → {bugs_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--task-id", required=True, help="Identifier for this verdict (e.g. img-001)")
    p.add_argument("--verdict-file", help="File with subagent's text response (default: stdin)")
    p.add_argument("--bugs", help="bugs.json to append the verdict to (optional)")
    p.add_argument(
        "--strict",
        action="store_true",
        help="Exit non-zero if the verdict can't be parsed",
    )
    args = p.parse_args(argv)

    if args.verdict_file:
        text = Path(args.verdict_file).read_text(encoding="utf-8")
    else:
        text = sys.stdin.read()

    parsed = parse_verdict(text)

    sys.stdout.write(json.dumps(parsed, indent=2, ensure_ascii=False))
    sys.stdout.write("\n")

    if not parsed["valid"]:
        if args.strict:
            return 2
        return 0

    if args.bugs:
        rc = append_to_bugs(Path(args.bugs), args.task_id, parsed)
        return rc

    return 0


if __name__ == "__main__":
    sys.exit(main())
