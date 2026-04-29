#!/usr/bin/env python3
"""triage_console.py — filter console noise, classify the rest.

Default ignore-list strips Stripe deprecations, Sentry self-warnings, GA/GTM,
dev-mode React warnings, source-map 404s, favicon, cross-origin frame warnings.
Remaining messages are classified by category. LLM triage is OUT-OF-SCOPE for
this script — surface a list, the orchestrator skill spawns a Task subagent
for any messages flagged "unknown".

Black-box. Invoke with --help.

Usage:
    triage_console.py --input console.json
    triage_console.py --input console.json --out triaged.json --ignore-extra "myapp-warn-pattern"
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


# (regex, label, severity)
DEFAULT_NOISE = [
    (r"https?://www\.googletagmanager\.com/", "gtm", "noise"),
    (r"google-analytics\.com|googletagmanager\.com", "ga", "noise"),
    (r"\[Stripe\.js\] .* deprecated|stripe\.com/v3", "stripe-deprecation", "noise"),
    (r"sentry\.(io|wat)|@sentry/", "sentry-self", "noise"),
    (r"Failed to load resource: .* favicon", "favicon-404", "noise"),
    (r"DevTools failed to load source map|sourceMappingURL", "sourcemap-404", "noise"),
    (r"Download the React DevTools|react-devtools", "dev-react-devtools", "noise"),
    (r"Warning: ReactDOM\.render is no longer supported", "dev-react18-warn", "noise"),
    (r"Warning: %s: A component is changing", "dev-react-controlled", "noise"),
    (r"Blocked a frame with origin .* from accessing", "x-origin-frame", "noise"),
    (r"Mixed Content: The page at", "mixed-content", "warn"),
    (r"\[HMR\]|\[vite\]|\[next\]: hot-update", "hmr", "noise"),
    (r"Permission denied to access property .* on cross-origin", "x-origin-perm", "noise"),
    (r"Cookie ['\"].*['\"] has been rejected for invalid domain", "cookie-domain", "warn"),
    # Backend Pydantic warnings forwarded via streaming responses (FastAPI logs in console)
    (r"PydanticDeprecatedSince20|PydanticUserWarning", "pydantic-warning", "noise"),
    (r"DeprecationWarning: .*Pydantic", "pydantic-warning", "noise"),
    # Next.js 15 + Turbopack dev signals
    (r"\[Turbopack\] (compiled|building|HMR)", "next15-turbopack", "noise"),
    (r"\[next-auth\]\[debug\]", "next-auth-debug", "noise"),
    (r"\[Fast Refresh\]|fast-refresh", "next-fast-refresh", "noise"),
    # Supabase realtime client noise
    (r"\[Supabase\].*realtime|supabase.*subscribe", "supabase-realtime-debug", "noise"),
    # Browser-extension injection (common on dev machines, not the app)
    (r"chrome-extension://|moz-extension://", "browser-extension", "noise"),
    # ResizeObserver loop limit (chromium quirk, not a real bug)
    (r"ResizeObserver loop (limit exceeded|completed with undelivered notifications)",
     "resizeobserver-loop", "noise"),
    # AbortError from fetch unmount races
    (r"AbortError: signal is aborted|The user aborted a request",
     "abort-on-unmount", "noise"),
]

# Real-bug categories — listeners report these as plain text
BUG_PATTERNS = [
    (r"Hydration failed|Text content does not match server-rendered", "hydration-mismatch", "S1"),
    (r"Uncaught \(in promise\) TypeError|Cannot read prop", "js-typeerror", "S0"),
    (r"Uncaught ReferenceError", "js-reference-error", "S0"),
    (r"Uncaught SyntaxError", "js-syntax-error", "S0"),
    (r"net::ERR_FAILED|net::ERR_NAME_NOT_RESOLVED", "network-failure", "S1"),
    (r"CORS .* blocked|Cross-Origin Request Blocked", "cors", "S1"),
    (r"Refused to load .* Content Security Policy", "csp-violation", "S1"),
    (r"Refused to execute inline script", "csp-inline", "S2"),
    (r"WebSocket connection .* failed", "websocket-fail", "S1"),
    (r"Service worker registration failed", "sw-fail", "S2"),
    (r" 5\d\d ", "5xx-response", "S0"),
    (r" 4\d\d ", "4xx-response", "S2"),
]


def compile_patterns(extra: list[str]) -> tuple[list, list]:
    noise = [(re.compile(pat, re.I), label, sev) for pat, label, sev in DEFAULT_NOISE]
    for pat in extra:
        noise.append((re.compile(pat, re.I), "user-ignore", "noise"))
    bugs = [(re.compile(pat, re.I), label, sev) for pat, label, sev in BUG_PATTERNS]
    return noise, bugs


def classify(text: str, noise_pats, bug_pats) -> dict:
    for pat, label, sev in noise_pats:
        if pat.search(text):
            return {"category": label, "severity": sev, "decision": "ignore"}
    for pat, label, sev in bug_pats:
        if pat.search(text):
            return {"category": label, "severity": sev, "decision": "report"}
    return {"category": "unknown", "severity": "unknown", "decision": "needs-llm"}


def triage(messages: list, noise_pats, bug_pats) -> dict:
    ignored: list = []
    reported: list = []
    needs_llm: list = []
    for msg in messages:
        text = msg if isinstance(msg, str) else (msg.get("text") or msg.get("message") or "")
        cls = classify(text, noise_pats, bug_pats)
        record = {**(msg if isinstance(msg, dict) else {"text": text}), **cls}
        if cls["decision"] == "ignore":
            ignored.append(record)
        elif cls["decision"] == "report":
            reported.append(record)
        else:
            needs_llm.append(record)
    return {
        "ignored": ignored,
        "reported": reported,
        "needsLlm": needs_llm,
        "stats": {
            "total": len(messages),
            "ignored": len(ignored),
            "reported": len(reported),
            "needsLlm": len(needs_llm),
        },
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Triage browser console messages.")
    p.add_argument("--input", required=True, help="JSON file: array of messages or {messages: [...]}")
    p.add_argument("--out", help="Output JSON (default: stdout)")
    p.add_argument(
        "--ignore-extra",
        action="append",
        default=[],
        help="Additional regex patterns to treat as noise (repeatable)",
    )
    args = p.parse_args(argv)

    in_path = Path(args.input)
    if not in_path.is_file():
        print(f"input not found: {in_path}", file=sys.stderr)
        return 1

    data = json.loads(in_path.read_text(encoding="utf-8"))
    messages = data if isinstance(data, list) else data.get("messages", [])

    noise_pats, bug_pats = compile_patterns(args.ignore_extra)
    result = triage(messages, noise_pats, bug_pats)

    payload = json.dumps(result, indent=2, ensure_ascii=False)
    if args.out:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"[triage_console] {result['stats']} → {args.out}")
    else:
        sys.stdout.write(payload)
        sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
