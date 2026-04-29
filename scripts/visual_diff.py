#!/usr/bin/env python3
"""visual_diff.py — locate failed toHaveScreenshot diffs in a run, prepare vision tasks.

Black-box. Invoke with --help.

`toHaveScreenshot()` writes pixel-diff data into Playwright JSON output as
attachments. This script extracts them, optionally filters by min diff %, and
emits a vision-tasks.json file: a list of {imagePath, expectedPath, diffPath,
viewport, specFile, suggestedPrompt}. The orchestrator skill then dispatches
ONE Task subagent per task — see Image budget protection.

This script does NOT call any LLM itself, does NOT read images. It only points
at them and prepares the prompt.

Usage:
    visual_diff.py --run-dir reports/run-2026-04-28-1430
    visual_diff.py --run-dir reports/<run-id> --min-diff-pct 0.5
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


VISION_PROMPT_TEMPLATE = """Read this image with the Read tool: {image_path}

This is a pixel-diff failure from a Playwright visual regression test.
Spec file: {spec_file}
Project: {project}
Viewport: {viewport}

Output ONE line in this exact format:
<verdict>: <one-sentence reason>

Where <verdict> is one of:
  noise        — antialiasing, font rendering jitter, animation timing — not a real change
  redesign     — intentional UI update, baseline should be regenerated
  bug-S0       — page broken, content missing, layout shattered
  bug-S1       — major regression, primary element broken
  bug-S2       — minor regression, secondary element wrong
  bug-S3       — cosmetic, alignment, color shift

DO NOT include the image inline in your response. DO NOT paste base64. ONE line only.
"""


def find_visual_failures(results_path: Path) -> list[dict]:
    """Return a list of failed visual-diff records from Playwright JSON results."""
    if not results_path.is_file():
        return []
    data = json.loads(results_path.read_text(encoding="utf-8"))
    failures: list = []
    _walk_for_visual(data.get("suites", []), failures)
    return failures


def _walk_for_visual(suites: list, failures: list) -> None:
    for s in suites:
        for spec in s.get("specs", []):
            for tc in spec.get("tests", []):
                for r in tc.get("results", []):
                    if r.get("status") not in ("failed", "timedOut"):
                        continue
                    err_msg = ((r.get("error") or {}).get("message") or "")
                    if "toHaveScreenshot" not in err_msg and "snapshot" not in err_msg.lower():
                        continue
                    actual = expected = diff = None
                    for a in r.get("attachments", []) or []:
                        name = (a.get("name") or "").lower()
                        if "actual" in name:
                            actual = a.get("path")
                        elif "expected" in name:
                            expected = a.get("path")
                        elif "diff" in name:
                            diff = a.get("path")
                    failures.append({
                        "specFile": spec.get("file"),
                        "specTitle": spec.get("title"),
                        "project": tc.get("projectName"),
                        "actual": actual,
                        "expected": expected,
                        "diff": diff,
                        "errorMessage": err_msg[:500],
                    })
        _walk_for_visual(s.get("suites", []), failures)


def make_task(failure: dict) -> dict | None:
    img = failure.get("diff") or failure.get("actual")
    if not img:
        return None
    project = failure.get("project") or "unknown"
    viewport_hint = {
        "chromium-desktop": "1920×1080",
        "chromium-laptop": "1366×768",
        "chromium-mobile": "390×844",
        "pixel5": "393×851",
        "mobile-safari": "390×844",
    }.get(project, "unknown viewport")

    prompt = VISION_PROMPT_TEMPLATE.format(
        image_path=str(Path(img).resolve()),
        spec_file=failure.get("specFile") or "?",
        project=project,
        viewport=viewport_hint,
    )

    return {
        "imagePath": str(Path(img).resolve()),
        "actualPath": failure.get("actual"),
        "expectedPath": failure.get("expected"),
        "diffPath": failure.get("diff"),
        "specFile": failure.get("specFile"),
        "specTitle": failure.get("specTitle"),
        "project": project,
        "viewport": viewport_hint,
        "errorExcerpt": (failure.get("errorMessage") or "")[:200],
        "suggestedPrompt": prompt,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    p.add_argument("--run-dir", required=True, help="reports/<run-id> directory containing results.json")
    p.add_argument("--out", help="Output vision-tasks.json (default: <run-dir>/vision-tasks.json)")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    results_path = run_dir / "results.json"
    if not results_path.is_file():
        # search recursively
        candidates = list(run_dir.glob("**/results.json"))
        if candidates:
            results_path = candidates[0]
    if not results_path.is_file():
        print(f"results.json not found under {run_dir}", file=sys.stderr)
        return 1

    failures = find_visual_failures(results_path)
    tasks = [t for t in (make_task(f) for f in failures) if t]

    out_path = Path(args.out) if args.out else (run_dir / "vision-tasks.json")
    out_path.write_text(
        json.dumps({"runId": run_dir.name, "tasks": tasks}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"[visual_diff] {len(tasks)} vision tasks → {out_path}")
    if tasks:
        print()
        print("NEXT STEP: orchestrator dispatches ONE Task subagent per task,")
        print("using `suggestedPrompt` field. Subagent returns ONE text line.")
        print("Never read these images in the parent context.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
