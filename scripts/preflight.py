#!/usr/bin/env python3
"""preflight.py — quick environment + target-URL checks before a test run.

Black-box. Invoke with --help.

Validates:
- TEST_BASE_URL is reachable (HEAD or GET, 1.5s timeout)
- .env.test or TEST_CREDENTIALS_FILE is loadable when auth is required
- Required env vars present for the chosen auth flow

Exits 0 if all preflights pass, non-zero otherwise. Prints actionable hints.
"""
from __future__ import annotations

import argparse
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    except (AttributeError, ValueError):
        pass


def load_env_test(project_root: Path) -> dict[str, str]:
    """Load <project>/.env.test and TEST_CREDENTIALS_FILE if pointed."""
    env: dict[str, str] = {}
    for var, val in os.environ.items():
        env[var] = val
    p = project_root / ".env.test"
    if p.is_file():
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    creds_file = env.get("TEST_CREDENTIALS_FILE")
    if creds_file and Path(creds_file).is_file():
        for line in Path(creds_file).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            env.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    return env


def check_url(url: str, timeout: float = 2.0) -> tuple[bool, str]:
    if not url:
        return False, "TEST_BASE_URL is empty"
    if not url.startswith(("http://", "https://")):
        return False, f"TEST_BASE_URL must start with http(s):// — got: {url!r}"
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return True, f"HTTP {resp.status} {url}"
    except urllib.error.HTTPError as e:
        # Even 4xx/5xx means the host responded
        return True, f"HTTP {e.code} {url} (host responded)"
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return False, f"unreachable: {url} — {e}"


def auth_flow_label(env: dict[str, str]) -> str:
    if env.get("SUPABASE_URL") and env.get("SUPABASE_ANON_KEY"):
        return "supabase"
    if env.get("TEST_API_LOGIN_PATH"):
        return "custom-api"
    if env.get("TEST_USER_EMAIL") and env.get("TEST_USER_PASSWORD"):
        return "ui-fallback"
    return "public"


def check_auth_env(env: dict[str, str]) -> list[str]:
    """Return list of warnings (empty if all good)."""
    warnings: list[str] = []
    flow = auth_flow_label(env)
    if flow == "public":
        return []
    if not env.get("TEST_USER_EMAIL"):
        warnings.append("TEST_USER_EMAIL missing")
    if not env.get("TEST_USER_PASSWORD"):
        warnings.append("TEST_USER_PASSWORD missing")
    if flow == "supabase":
        if not env.get("SUPABASE_URL", "").startswith("https://"):
            warnings.append("SUPABASE_URL must be https://<ref>.supabase.co")
        if not env.get("SUPABASE_ANON_KEY", "").startswith("eyJ"):
            warnings.append("SUPABASE_ANON_KEY does not look like a JWT (should start with 'eyJ')")
    return warnings


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Preflight checks before a test run.")
    p.add_argument("--cwd", default=".", help="Project root (where .env.test lives)")
    p.add_argument("--timeout", type=float, default=2.0, help="HEAD-request timeout (sec)")
    args = p.parse_args(argv)

    project_root = Path(args.cwd).resolve()
    env = load_env_test(project_root)

    base_url = env.get("TEST_BASE_URL", "")
    flow = auth_flow_label(env)

    print(f"[preflight] project root:     {project_root}")
    print(f"[preflight] TEST_BASE_URL:    {base_url or '(not set)'}")
    print(f"[preflight] auth flow:        {flow}")

    failed = False

    ok, detail = check_url(base_url, timeout=args.timeout)
    print(f"[preflight] URL reachable:    {'OK' if ok else 'FAIL'} — {detail}")
    if not ok:
        failed = True

    auth_warns = check_auth_env(env)
    if auth_warns:
        print("[preflight] auth env issues:")
        for w in auth_warns:
            print(f"  ! {w}")
        if flow != "public":
            failed = True
    else:
        print("[preflight] auth env:         OK")

    if failed:
        print()
        print("[preflight] ❌ blocked. Fix the issues above before running the suite.")
        return 1
    print("[preflight] ✅ all checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
